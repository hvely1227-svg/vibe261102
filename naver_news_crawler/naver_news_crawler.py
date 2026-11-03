"""
네이버 검색 결과 페이지에서 뉴스 기사 링크를 수집하고,
각 기사(n.news.naver.com)의 제목 / 언론사 / 작성일 / 본문을 크롤링합니다.

필요 패키지:
    pip install requests beautifulsoup4
"""

import csv
import re
import time

from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

SEARCH_URL = (
    "https://search.naver.com/search.naver"
    "?where=nexearch&sm=top_hty&fbm=0&ie=utf8"
    "&query=%EB%B0%98%EB%8F%84%EC%B2%B4&ackey=gxc5qd8m"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Referer": "https://www.naver.com/",
}

# 네이버뉴스 기사 주소 형식: https://n.news.naver.com/mnews/article/{언론사ID}/{기사ID}
ARTICLE_RE = re.compile(r"https://n\.news\.naver\.com/(?:mnews/)?article/(\d+)/(\d+)")


def build_search_url(keyword):
    """검색어로 네이버 통합검색 주소 생성"""
    return (
        "https://search.naver.com/search.naver"
        f"?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={quote(keyword)}"
    )


def get_soup(url):
    res = requests.get(url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    return BeautifulSoup(res.text, "html.parser")


def collect_article_links(search_url):
    """검색 결과 페이지에서 네이버뉴스 기사 링크를 중복 없이 수집"""
    soup = get_soup(search_url)

    links = []
    seen = set()

    # 1) <a href="..."> 태그에서 수집
    for a in soup.select('a[href*="n.news.naver.com"]'):
        m = ARTICLE_RE.search(a["href"])
        if m and m.groups() not in seen:
            seen.add(m.groups())
            links.append(f"https://n.news.naver.com/mnews/article/{m.group(1)}/{m.group(2)}")

    # 2) 검색 페이지는 일부 결과를 <script> 안의 JSON으로 렌더링하므로 전체 HTML에서도 검색
    for m in ARTICLE_RE.finditer(str(soup)):
        if m.groups() not in seen:
            seen.add(m.groups())
            links.append(f"https://n.news.naver.com/mnews/article/{m.group(1)}/{m.group(2)}")

    return links


def text_of(soup, selector):
    tag = soup.select_one(selector)
    return tag.get_text(" ", strip=True) if tag else ""


def parse_article(url):
    """네이버뉴스 기사 페이지에서 제목, 언론사, 작성일, 본문 추출"""
    soup = get_soup(url)

    title = text_of(soup, "#title_area") or text_of(soup, "h2.media_end_head_headline")

    press_img = soup.select_one("a.media_end_head_top_logo img")
    press = press_img.get("title") or press_img.get("alt", "") if press_img else ""

    date_tag = soup.select_one("span.media_end_head_info_datestamp_time")
    date = date_tag.get("data-date-time", date_tag.get_text(strip=True)) if date_tag else ""

    body = soup.select_one("#dic_area") or soup.select_one("#newsct_article")
    content = ""
    if body:
        # 사진 설명, 광고, 스크립트 등 본문이 아닌 요소 제거
        for tag in body.select("script, style, em.img_desc, span.end_photo_org, div.ab_photo"):
            tag.decompose()
        for br in body.find_all("br"):
            br.replace_with("\n")
        content = body.get_text()
        content = re.sub(r"\n\s*\n+", "\n\n", content).strip()

    return {"url": url, "title": title, "press": press, "date": date, "content": content}


def main():
    links = collect_article_links(SEARCH_URL)
    print(f"수집된 기사 링크: {len(links)}개\n")

    articles = []
    for i, url in enumerate(links, 1):
        try:
            art = parse_article(url)
        except requests.RequestException as e:
            print(f"[{i}] 실패: {url} ({e})")
            continue

        articles.append(art)
        print(f"[{i}] {art['title']}")
        print(f"    언론사: {art['press']} | 작성일: {art['date']}")
        print(f"    {url}")
        print(f"    {art['content'][:150].replace(chr(10), ' ')}...\n")
        time.sleep(0.5)  # 서버 부하를 줄이기 위한 요청 간격

    # 엑셀에서 한글이 깨지지 않도록 utf-8-sig로 저장
    with open("naver_news.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "press", "date", "url", "content"])
        writer.writeheader()
        writer.writerows(articles)
    print(f"naver_news.csv 에 {len(articles)}건 저장 완료")


if __name__ == "__main__":
    main()
