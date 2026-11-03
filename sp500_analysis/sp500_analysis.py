"""S&P 500 과거 데이터 클렌징 + 다각도 분석 + 2000-01 ~ 2019-12 종가 라인그래프."""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

DEFAULT_CSV = Path(r"C:\Users\user\Desktop\S&P 500 과거 데이터.csv")
OUT_DIR = Path(__file__).parent

plt.rcParams["font.family"] = "Malgun Gothic"   # 한글 폰트 (Windows)
plt.rcParams["axes.unicode_minus"] = False
pd.set_option("display.width", 120)


# ---------------------------------------------------------------- 1. 클렌징
def load_and_clean(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, encoding="utf-8-sig", thousands=",")
    print(f"[원본] {raw.shape[0]}행 x {raw.shape[1]}열")
    print(raw.dtypes, "\n")

    df = raw.rename(columns={
        "날짜": "Date", "종가": "Close", "시가": "Open", "고가": "High",
        "저가": "Low", "거래량": "Volume", "변동 %": "ChangePct",
    })

    # 날짜 파싱
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # 가격 컬럼: 천 단위 쉼표가 섞여 있어도 확실히 숫자로
    for col in ["Close", "Open", "High", "Low"]:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")

    # 변동 % 문자열 -> 실수
    df["ChangePct"] = pd.to_numeric(df["ChangePct"].astype(str).str.rstrip("%"), errors="coerce")

    # 거래량은 전부 비어 있으면 제거
    if df["Volume"].isna().all():
        print("[클렌징] 거래량 컬럼이 전부 비어 있어 제거")
        df = df.drop(columns="Volume")

    before = len(df)
    df = df.dropna(subset=["Date", "Close"])
    df = df.drop_duplicates(subset="Date", keep="first")
    print(f"[클렌징] 날짜/종가 결측 및 중복 제거: {before - len(df)}행")

    # 논리 검증: 고가 >= max(시가, 종가, 저가), 저가 <= min(...)
    bad = (df["High"] < df[["Open", "Close", "Low"]].max(axis=1)) | \
          (df["Low"] > df[["Open", "Close", "High"]].min(axis=1))
    print(f"[클렌징] 고가/저가 논리 오류 행: {bad.sum()}개")
    if bad.any():
        print(df.loc[bad].to_string(index=False), "\n")

    # 오름차순 정렬 + 날짜 인덱스
    df = df.sort_values("Date").set_index("Date")

    # 변동률 재계산해서 원본 값과 비교
    df["Return"] = df["Close"].pct_change() * 100
    diff = (df["Return"] - df["ChangePct"]).abs()
    print(f"[검증] 원본 변동%와 재계산 수익률 차이 > 0.05%p 인 행: {(diff > 0.05).sum()}개")

    print(f"[정제 후] {len(df)}행, 기간 {df.index.min():%Y-%m-%d} ~ {df.index.max():%Y-%m-%d}")
    print(f"[결측치]\n{df.isna().sum()}\n")
    return df


# ---------------------------------------------------------------- 2. 분석
# GUI 에서도 쓰도록 각 분석을 DataFrame/dict 를 돌려주는 함수로 분리
def performance(df: pd.DataFrame) -> dict:
    close = df["Close"]
    years = (close.index[-1] - close.index[0]).days / 365.25
    total = close.iloc[-1] / close.iloc[0] - 1
    peak = close.cummax()
    dd = close / peak - 1
    trough = dd.idxmin()
    peak_date = close[:trough].idxmax()
    recovered = close[trough:][close[trough:] >= close[peak_date]]
    return {
        "start": close.iloc[0], "end": close.iloc[-1],
        "total_pct": total * 100,
        "cagr_pct": ((1 + total) ** (1 / years) - 1) * 100 if years > 0 else float("nan"),
        "vol_pct": close.pct_change().std() * 252 ** 0.5 * 100,
        "mdd_pct": dd.min() * 100,
        "mdd_peak": peak_date, "mdd_trough": trough,
        "recovered": recovered.index[0] if len(recovered) else None,
    }


def yearly_summary(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"]
    yearly = close.groupby(close.index.year).agg(["first", "last", "min", "max", "mean"])
    yearly.columns = ["시작", "종료", "최저", "최고", "평균"]
    yearly["연수익률%"] = (yearly["종료"] / yearly["시작"] - 1) * 100
    yearly["연변동성%"] = df["Return"].groupby(df.index.year).std() * (252 ** 0.5)
    yearly.index.name = "연도"
    return yearly.round(2)


def monthly_seasonality(df: pd.DataFrame) -> pd.DataFrame:
    monthly = df["Close"].resample("ME").last().pct_change() * 100
    out = monthly.groupby(monthly.index.month).agg(["mean", "median", lambda s: (s > 0).mean() * 100])
    out.columns = ["평균%", "중앙값%", "상승확률%"]
    out.index.name = "월"
    return out.round(2)


def weekday_returns(df: pd.DataFrame) -> pd.DataFrame:
    names = ["월", "화", "수", "목", "금"]
    wd = df["Return"].groupby(df.index.dayofweek).agg(["mean", "count"])
    wd.index = [names[i] for i in wd.index]
    wd.columns = ["평균수익률%", "거래일수"]
    wd.index.name = "요일"
    return wd.round(3)


def ma_crosses(df: pd.DataFrame) -> pd.Series:
    close = df["Close"]
    ma50, ma200 = close.rolling(50).mean(), close.rolling(200).mean()
    valid = ma200.notna()                     # 200일선이 생긴 이후만 비교
    sig = (ma50[valid] > ma200[valid]).astype(int).diff()
    cross = sig[sig.fillna(0) != 0]
    return cross.map(lambda v: "골든크로스" if v > 0 else "데드크로스")


def analyze(df: pd.DataFrame) -> None:
    sep = "=" * 70

    print(sep, "\n① 기술통계\n", sep)
    print(df[["Open", "High", "Low", "Close", "Return"]].describe().round(2), "\n")

    print(sep, "\n② 연도별 요약 (종가 기준)\n", sep)
    print(yearly_summary(df), "\n")

    p = performance(df)
    print(sep, "\n③ 전체 성과\n", sep)
    print(f"시작 {p['start']:,.2f} → 종료 {p['end']:,.2f}")
    print(f"누적수익률 {p['total_pct']:.2f}% / 연평균(CAGR) {p['cagr_pct']:.2f}% / "
          f"연환산 변동성 {p['vol_pct']:.2f}%\n")

    print(sep, "\n④ 최대 낙폭 (MDD)\n", sep)
    close = df["Close"]
    print(f"MDD {p['mdd_pct']:.2f}%  (고점 {p['mdd_peak']:%Y-%m-%d} {close[p['mdd_peak']]:,.2f}"
          f" → 저점 {p['mdd_trough']:%Y-%m-%d} {close[p['mdd_trough']]:,.2f})")
    print(f"회복일: {p['recovered']:%Y-%m-%d}" if p["recovered"] is not None else "회복일: 데이터 내 미회복")
    print()

    print(sep, "\n⑤ 일간 등락 TOP 5\n", sep)
    print("상승:\n", df["Return"].nlargest(5).round(2).to_string())
    print("하락:\n", df["Return"].nsmallest(5).round(2).to_string(), "\n")

    print(sep, "\n⑥ 월별 평균 수익률 (계절성)\n", sep)
    print(monthly_seasonality(df), "\n")

    print(sep, "\n⑦ 요일별 평균 일간 수익률\n", sep)
    print(weekday_returns(df), "\n")

    print(sep, "\n⑧ 이동평균 골든/데드크로스 (50일 vs 200일)\n", sep)
    for d, v in ma_crosses(df).items():
        print(f"{d:%Y-%m-%d}  {v}")
    print()


# ---------------------------------------------------------------- 3. 차트
def draw_close(ax, df: pd.DataFrame, start="2000-01-01", end="2019-12-31") -> None:
    """주어진 axes 에 종가 라인그래프를 그린다 (스크립트/GUI 공용)."""
    s = df.loc[start:end, "Close"]
    # 200일선은 구간 이전 데이터까지 써서 계산해야 구간 시작부터 이어진다
    ma200 = df["Close"].rolling(200).mean().loc[start:end]
    ax.plot(s.index, s.values, color="#1f5fbf", linewidth=1.2, label="종가")
    ax.plot(ma200.index, ma200.values, color="#e07b00", linewidth=1, alpha=.8, label="200일 이동평균")

    # 최고점은 왼쪽, 최저점은 오른쪽에 화살표로 표시 (축 밖으로 안 나가게)
    for d, label, offset in [(s.idxmax(), "최고", (-80, -10)), (s.idxmin(), "최저", (70, -5))]:
        ax.annotate(f"{label} {d:%Y-%m-%d}\n{s[d]:,.0f}", (d, s[d]), textcoords="offset points",
                    xytext=offset, ha="center", fontsize=9,
                    arrowprops=dict(arrowstyle="->", color="gray"))

    ax.set_title(f"S&P 500 종가 추이 ({s.index.min():%Y.%m} ~ {s.index.max():%Y.%m})", fontsize=15)
    ax.set_xlabel("날짜")
    ax.set_ylabel("종가 (pt)")
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    ax.grid(alpha=.3)
    ax.legend()


def plot_close(df: pd.DataFrame, start="2000-01-01", end="2019-12-31") -> Path:
    fig, ax = plt.subplots(figsize=(14, 6))
    draw_close(ax, df, start, end)
    fig.tight_layout()

    out = OUT_DIR / "sp500_close_2000_2019.png"
    fig.savefig(out, dpi=150)
    print(f"[차트 저장] {out}")
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    csv = Path(args[0]) if args else DEFAULT_CSV
    data = load_and_clean(csv)
    data.to_csv(OUT_DIR / "sp500_cleaned.csv", encoding="utf-8-sig")
    analyze(data)
    plot_close(data)
    if "--no-show" not in sys.argv:
        plt.show()
