"""
네이버 증권에서 코스피200(KPI200) 지수 데이터를 크롤링합니다.

stock.naver.com/market/stock/kr 은 자바스크립트로 데이터를 그리는 페이지라
requests 로 받은 HTML에는 지수 값이 들어 있지 않습니다.
그래서 같은 데이터를 서버에서 HTML로 렌더링해 주는 모바일 지수 페이지
(m.stock.naver.com/domestic/index/KPI200/total)를 BeautifulSoup으로 파싱합니다.

수집 항목:
    현재가 / 전일대비 / 등락률 / 기준일
    52주 최저·최고, 전일 / 시가 / 고가 / 저가 / 거래량 / 거래대금
    투자자별(개인·외국인·기관), 프로그램(차익·비차익·전체), 등락종목(상승·보합·하락)

구성종목 목록은 HTML에 들어 있지 않고 화면이 열린 뒤 JSON API로 불러오므로,
같은 API(enrollStocks)를 page / pageSize 로 페이징하며 전부 수집합니다.

필요 패키지:
    pip install requests beautifulsoup4
"""

import csv
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

URL = "https://m.stock.naver.com/domestic/index/KPI200/total"
STOCKS_API = "https://m.stock.naver.com/api/index/KPI200/enrollStocks"
PAGE_SIZE = 20  # 화면과 같은 크기. 이 API는 100 이상이면 400 에러를 냅니다.
MAX_PAGES = 30  # 무한 루프 방지용 상한

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Referer": "https://stock.naver.com/market/stock/kr",
}

OUTPUT_CSV = "kospi200.csv"
STOCKS_CSV = "kospi200_stocks.csv"


def select_one(soup, prefix, root=None):
    """CSS 모듈 해시(예: DetailInfo_stock-price__9NYZz)가 바뀌어도 동작하도록 클래스 접두어로 찾습니다."""
    return (root or soup).select_one(f'[class*="{prefix}"]')


def text_of(el):
    return el.get_text(" ", strip=True) if el else ""


def parse_kospi200(html):
    soup = BeautifulSoup(html, "html.parser")
    data = {"수집시각": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    # 1) 상단 시세 영역: 지수명, 현재가, 전일대비, 등락률, 기준일
    info = select_one(soup, "DetailInfo_area-info")
    if info is None:
        raise RuntimeError("시세 영역을 찾지 못했습니다. 페이지 구조가 바뀌었을 수 있습니다.")

    data["지수명"] = text_of(select_one(soup, "DetailInfo_stock-name", info))
    data["현재가"] = text_of(select_one(soup, "DetailInfo_stock-price", info))

    fluct = select_one(soup, "FluctuationWithSign_article", info)
    values = fluct.select('[class*="FluctuationWithSign_value"]') if fluct else []
    data["전일대비"] = text_of(values[0]) if values else ""
    ratio = text_of(values[1]).strip("() %").replace(" ", "") if len(values) > 1 else ""
    # 등락률은 부호 없이 표시되므로 RISING / FALLING 클래스로 부호를 붙입니다.
    if ratio and fluct and "FALLING" in " ".join(fluct.get("class", [])):
        ratio = "-" + ratio
    data["등락률(%)"] = ratio
    data["기준일"] = text_of(info.find("time"))

    # 2) 종합 정보: 52주 최저/최고 + 전일·시가·고가·저가·거래량·거래대금
    total = soup.select_one('[data-comp-id="domestic-index-total-info"]')
    if total:
        data["52주 최저"] = text_of(select_one(soup, "TotalInfoView_lowest", total).find("b"))
        data["52주 최고"] = text_of(select_one(soup, "TotalInfoView_highest", total).find("b"))
        for li in total.select('[class*="TotalInfoView_item"]'):
            key = text_of(select_one(soup, "TotalInfoView_key", li))
            data[key] = text_of(select_one(soup, "TotalInfoView_value", li))

    # 3) 투자자별 / 프로그램 / 등락종목
    for section in soup.select('[class*="IndexTrendSection_info"]'):
        title = text_of(select_one(soup, "IndexTrendSection_title", section))
        for li in section.select('[class*="IndexTrendSection_item"]'):
            key = text_of(select_one(soup, "IndexTrendSection_desc", li))
            data[f"{title}_{key}"] = text_of(select_one(soup, "IndexTrendSection_num", li))

    return data


def crawl():
    resp = requests.get(URL, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return parse_kospi200(resp.text)


def print_progress(page, page_count, total):
    print(f"  {page}페이지: {page_count}건 (누적 {total}건)")


def crawl_stocks(progress=print_progress):
    """구성종목을 PAGE_SIZE 단위로 페이지를 넘기며 빈 페이지가 나올 때까지 수집합니다.

    progress(page, page_count, total) 는 페이지마다 호출됩니다 (GUI 진행률 표시용).
    """
    stocks = []
    seen = set()

    for page in range(1, MAX_PAGES + 1):
        resp = requests.get(
            STOCKS_API,
            params={"page": page, "pageSize": PAGE_SIZE},
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json()
        if not items:
            break

        for item in items:
            if item["itemCode"] in seen:  # 장중 순위 변동으로 페이지 경계에서 중복될 수 있음
                continue
            seen.add(item["itemCode"])
            stocks.append({
                "순위": len(stocks) + 1,
                "종목코드": item["itemCode"],
                "종목명": item["stockName"],
                "현재가": item["closePrice"],
                "전일대비": item["compareToPreviousClosePrice"],
                "등락률(%)": item["fluctuationsRatio"],
                "거래량": item["accumulatedTradingVolume"],
                "거래대금(백만)": item["accumulatedTradingValue"],
                "시가총액(억)": item["marketValue"],
                "기준시각": item["localTradedAt"],
            })

        progress(page, len(items), len(stocks))
        if len(items) < PAGE_SIZE:  # 마지막 페이지
            break
        time.sleep(0.3)

    return stocks


def save_stocks_csv(stocks, path=STOCKS_CSV):
    # 구성종목은 매번 최신 목록으로 덮어씁니다.
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(stocks[0].keys()))
        writer.writeheader()
        writer.writerows(stocks)


def save_csv(data, path=OUTPUT_CSV):
    # 실행할 때마다 한 줄씩 누적 저장 (엑셀에서 한글이 깨지지 않도록 utf-8-sig)
    try:
        with open(path, encoding="utf-8-sig") as f:
            is_new = not f.read(1)
    except FileNotFoundError:
        is_new = True

    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(data.keys()))
        if is_new:
            writer.writeheader()
        writer.writerow(data)


def main():
    data = crawl()

    print(f"[{data['지수명']}] {data['기준일']}")
    for key, value in data.items():
        print(f"  {key:<12} {value}")

    save_csv(data)
    print(f"\n{OUTPUT_CSV} 에 저장했습니다.")

    print("\n구성종목 수집 중...")
    stocks = crawl_stocks()
    save_stocks_csv(stocks)
    print(f"구성종목 {len(stocks)}건을 {STOCKS_CSV} 에 저장했습니다.")


if __name__ == "__main__":
    main()
