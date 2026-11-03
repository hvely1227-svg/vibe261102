"""대한민국 출생아수·합계출산율·자연증가 (KOSIS INH_1B8000F_01) 클렌징 + 다각도 분석."""
import sys
import warnings
from pathlib import Path

import pandas as pd

DEFAULT_XLSX = Path(r"C:\Users\user\Desktop\생산성본부_바이브코딩수업\DataSet\출생아수__합계출산율__자연증가_등_.xlsx")
OUT_DIR = Path(__file__).parent

# KOSIS 원본 행 이름 -> 분석용 컬럼명
COLUMNS = {
    "출생아수(명)": "출생아수",
    "자연증가건수(명)": "자연증가",
    "조출생률(천명당)": "조출생률",
    "자연증가율(천명당)": "자연증가율",
    "합계출산율(명)": "합계출산율",
    "출생성비(명)": "출생성비",
}

pd.set_option("display.width", 140)
pd.set_option("display.max_rows", 100)
# KOSIS 엑셀은 기본 스타일이 없어 openpyxl 경고가 뜬다 (데이터와 무관)
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


# ---------------------------------------------------------------- 1. 클렌징
def load_and_clean(path: Path) -> pd.DataFrame:
    # 첫 시트 = 데이터 (지표가 행, 연도가 열인 가로형). 두 번째 시트는 메타정보
    raw = pd.read_excel(path, sheet_name=0)
    print(f"[원본] {raw.shape[0]}행(지표) x {raw.shape[1]}열(연도) - 가로형(wide)")

    # 가로형 -> 세로형: 연도를 행으로
    df = raw.set_index(raw.columns[0]).T
    df.columns.name = None
    df = df.rename(columns=COLUMNS)

    # 연도 라벨 정리: 1970.0 같은 실수, '2025 p)' 같은 잠정치 표기
    labels = df.index.astype(str).str.strip()
    df["잠정치"] = labels.str.contains("p", case=False)
    df.index = pd.to_numeric(labels.str.extract(r"(\d{4})")[0], errors="coerce").astype("Int64")
    df.index.name = "연도"
    print(f"[클렌징] 잠정치(p) 연도: {df.index[df['잠정치']].tolist()}")

    # 숫자 변환 (천 단위 쉼표, '-' 등이 섞여 있어도 안전하게)
    for col in COLUMNS.values():
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    df[["출생아수", "자연증가"]] = df[["출생아수", "자연증가"]].round().astype("Int64")

    before = len(df)
    df = df[df.index.notna()]
    df = df[~df.index.duplicated(keep="first")].sort_index()
    print(f"[클렌징] 연도 결측/중복 제거: {before - len(df)}행")
    print(f"[결측치] {df[list(COLUMNS.values())].isna().sum().to_dict()}")

    # 연도 누락 확인
    missing = sorted(set(range(df.index.min(), df.index.max() + 1)) - set(df.index))
    print(f"[검증] 빠진 연도: {missing or '없음'}")

    # 범위 검증: 음수 출생아수, 비정상 성비, 합계출산율 범위
    bad = (df["출생아수"] <= 0) | ~df["출생성비"].between(90, 130) | ~df["합계출산율"].between(0.3, 8)
    print(f"[검증] 값 범위 이상 행: {int(bad.sum())}개")

    # 파생 변수: 사망자수 = 출생아수 - 자연증가, 전년 대비 증감
    df["사망자수"] = df["출생아수"] - df["자연증가"]
    df["출생아_증감"] = df["출생아수"].diff()
    df["출생아_증감률%"] = (df["출생아수"].pct_change() * 100).round(2)

    # 조출생률(천명당)로 연앙인구를 역산 -> 출생아수와 정합성 확인용
    df["추정인구(만명)"] = (df["출생아수"] / df["조출생률"] * 1000 / 10_000).round(0)

    print(f"[정제 후] {len(df)}행, 기간 {df.index.min()} ~ {df.index.max()}\n")
    return df


# ---------------------------------------------------------------- 2. 분석
def decade_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby((df.index // 10) * 10)
    out = pd.DataFrame({
        "평균 출생아수": g["출생아수"].mean().round(0),
        "최소 출생아수": g["출생아수"].min(),
        "평균 합계출산율": g["합계출산율"].mean().round(2),
        "평균 출생성비": g["출생성비"].mean().round(1),
        "자연증가 합계": g["자연증가"].sum(),
    })
    out.index = [f"{d}년대" for d in out.index]
    out.index.name = "연대"
    return out


def milestones(df: pd.DataFrame) -> list[tuple[str, int | None]]:
    """특정 기준을 처음 밑돈 해."""
    def first(mask):
        hit = df.index[mask.fillna(False)]
        return int(hit[0]) if len(hit) else None

    b, tfr = df["출생아수"], df["합계출산율"]
    return [
        ("출생아수 80만 명 미만", first(b < 800_000)),
        ("출생아수 60만 명 미만", first(b < 600_000)),
        ("출생아수 50만 명 미만", first(b < 500_000)),
        ("출생아수 40만 명 미만", first(b < 400_000)),
        ("출생아수 30만 명 미만", first(b < 300_000)),
        ("합계출산율 2.1(인구대체수준) 미만", first(tfr < 2.1)),
        ("합계출산율 1.3(초저출산) 미만", first(tfr < 1.3)),
        ("합계출산율 1.0 미만", first(tfr < 1.0)),
        ("자연증가 마이너스(데드크로스)", first(df["자연증가"] < 0)),
    ]


def period_cagr(df: pd.DataFrame, periods=((1970, 1985), (1985, 2000), (2000, 2015), (2015, 2025))) -> pd.DataFrame:
    rows = []
    for a, b in periods:
        if a in df.index and b in df.index:
            s, e = df.at[a, "출생아수"], df.at[b, "출생아수"]
            rows.append({"구간": f"{a}~{b}", "시작": s, "종료": e,
                         "총변화%": round((e / s - 1) * 100, 1),
                         "연평균증감률%": round(((e / s) ** (1 / (b - a)) - 1) * 100, 2)})
    return pd.DataFrame(rows, columns=["구간", "시작", "종료", "총변화%", "연평균증감률%"]).set_index("구간")


def declining_streaks(df: pd.DataFrame) -> pd.DataFrame:
    """출생아수가 연속으로 감소한 구간."""
    # Int64 비교 결과는 nullable boolean 이라 shift 의 NA 와 비교하면 첫 구간이 사라진다
    down = (df["출생아_증감"] < 0).fillna(False).astype(bool)
    grp = (down != down.shift()).cumsum()
    rows = []
    for _, s in df[down].groupby(grp[down]):
        rows.append({"시작": int(s.index[0]), "종료": int(s.index[-1]), "연속(년)": len(s),
                     "누적감소": int(s["출생아_증감"].sum())})
    out = pd.DataFrame(rows, columns=["시작", "종료", "연속(년)", "누적감소"])
    return out.sort_values("연속(년)", ascending=False).reset_index(drop=True)


def yoy_table(df: pd.DataFrame) -> pd.DataFrame:
    return df[["출생아수", "출생아_증감", "출생아_증감률%", "합계출산율"]].dropna()


def analyze(df: pd.DataFrame) -> None:
    sep = "=" * 70
    cols = list(COLUMNS.values()) + ["사망자수"]

    print(sep, "\n① 기술통계\n", sep)
    print(df[cols].astype(float).describe().round(2).to_string(), "\n")

    print(sep, "\n② 연대별 요약\n", sep)
    print(decade_summary(df).to_string(), "\n")

    b = df["출생아수"]
    print(sep, "\n③ 최대/최소 및 전체 변화\n", sep)
    print(f"최다 출생: {b.idxmax()}년 {b.max():,}명  /  최소 출생: {b.idxmin()}년 {b.min():,}명")
    print(f"{b.index[0]}년 {b.iloc[0]:,}명 → {b.index[-1]}년 {b.iloc[-1]:,}명 "
          f"({(b.iloc[-1] / b.iloc[0] - 1) * 100:.1f}%, 약 {b.iloc[0] / b.iloc[-1]:.1f}분의 1)")
    tfr = df["합계출산율"]
    print(f"합계출산율 최고 {tfr.idxmax()}년 {tfr.max()} / 최저 {tfr.idxmin()}년 {tfr.min()}\n")

    print(sep, "\n④ 구간별 출생아수 연평균 증감률\n", sep)
    print(period_cagr(df).to_string(), "\n")

    print(sep, "\n⑤ 전년 대비 증감 TOP 5\n", sep)
    yoy = df[["출생아수", "출생아_증감", "출생아_증감률%"]]
    print("증가:\n", yoy.nlargest(5, "출생아_증감").to_string())
    print("감소:\n", yoy.nsmallest(5, "출생아_증감").to_string(), "\n")

    print(sep, "\n⑥ 연속 감소 구간 (상위 5)\n", sep)
    print(declining_streaks(df).head(5).to_string(), "\n")

    print(sep, "\n⑦ 주요 이정표 (처음 기준 아래로 내려간 해)\n", sep)
    for name, year in milestones(df):
        print(f"{name:<28} {year if year else '해당 없음'}")
    print()

    print(sep, "\n⑧ 출생 vs 사망 (자연증가)\n", sep)
    cross = df.loc[2015:, ["출생아수", "사망자수", "자연증가", "자연증가율"]]
    print(cross.to_string())
    neg = df[df["자연증가"] < 0]
    print(f"\n자연감소 {len(neg)}년 연속, 누적 {int(neg['자연증가'].sum()):,}명\n")

    print(sep, "\n⑨ 출생성비 (여아 100명당 남아, 정상범위 103~107)\n", sep)
    sr = df["출생성비"]
    print(f"최고 {sr.idxmax()}년 {sr.max()}  /  정상범위 초과 연도 {int((sr > 107).sum())}개")
    over = df.index[sr > 107]
    print(f"정상범위 초과 마지막 해: {int(over[-1])}" if len(over) else "")
    print(sr.groupby((sr.index // 5) * 5).mean().round(1).rename("5년 평균").to_string(), "\n")

    print(sep, "\n⑩ 지표 간 상관계수\n", sep)
    print(df[cols].astype(float).corr().round(3).to_string(), "\n")

    print(sep, "\n⑪ 최근 10년 추이\n", sep)
    recent = df.loc[df.index.max() - 9:, ["출생아수", "출생아_증감률%", "합계출산율", "자연증가", "잠정치"]]
    print(recent.to_string(), "\n")


if __name__ == "__main__":
    xlsx = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    data = load_and_clean(xlsx)
    analyze(data)

    out = OUT_DIR / "birth_cleaned.csv"
    data.to_csv(out, encoding="utf-8-sig")
    print(f"[정제 데이터 저장] {out}")
