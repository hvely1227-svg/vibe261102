"""대한민국 출생아수 1970 ~ 2025 라인그래프."""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from birth_analysis import DEFAULT_XLSX, OUT_DIR, load_and_clean

plt.rcParams["font.family"] = "Malgun Gothic"   # 한글 폰트 (Windows)
plt.rcParams["axes.unicode_minus"] = False

LINE = "#1f5fbf"
DEATH = "#c2410c"
INK, MUTED = "#222222", "#777777"

# 지표별 (y축 라벨, 값 포맷, 0 기준선을 그릴지)
METRICS = {
    "출생아수": ("출생아수 (명)", lambda v: f"{v:,.0f}명", False),
    "합계출산율": ("합계출산율 (명)", lambda v: f"{v:.3f}명", False),
    "조출생률": ("조출생률 (인구 천 명당)", lambda v: f"{v:.1f}", False),
    "자연증가": ("자연증가 (명)", lambda v: f"{v:+,.0f}명", True),
    "자연증가율": ("자연증가율 (인구 천 명당)", lambda v: f"{v:+.1f}", True),
    "출생성비": ("출생성비 (여아 100명당 남아)", lambda v: f"{v:.1f}", False),
}
# 지표별 참고 기준선: (값, 라벨)
REFERENCE_LINES = {
    "출생아수": [(500_000, "50만 명"), (300_000, "30만 명")],
    "합계출산율": [(2.1, "인구대체수준 2.1"), (1.3, "초저출산 1.3")],
    "출생성비": [(107, "정상범위 상한 107"), (103, "정상범위 하한 103")],
}


def _style(ax, title: str, ylabel: str, first: int, last: int) -> None:
    ax.set_title(title, fontsize=15, color=INK, loc="left")
    ax.set_xlabel("연도", color=MUTED)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.set_xlim(first - 1, last + 1)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(5 if last - first > 15 else 1))
    ax.grid(axis="y", alpha=.25)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED)


def _man(v, _):
    """y축 눈금을 '만' 단위로."""
    return f"{v / 10_000:,.0f}만" if v else "0"


def draw_metric(ax, df, col="출생아수", start=1970, end=2025) -> None:
    """주어진 axes 에 지표 하나의 라인그래프를 그린다 (스크립트/GUI 공용)."""
    s = df.loc[start:end, col].astype(float)
    prelim = df.loc[start:end, "잠정치"]
    ylabel, fmt, zero_line = METRICS[col]

    final = s[~prelim.values]
    ax.plot(final.index, final.values, color=LINE, linewidth=2, marker="o", markersize=3.5)

    # 잠정치(2025 p)는 점선 + 속 빈 마커로 구분
    if prelim.any():
        p = s.index[prelim.values][0]
        if p - 1 in s.index:
            ax.plot([p - 1, p], [s[p - 1], s[p]], color=LINE, linewidth=2, linestyle="--", zorder=1)
        ax.plot(p, s[p], marker="o", markersize=7, markerfacecolor="white", markeredgecolor=LINE, markeredgewidth=2)

    # 최대·최소·마지막 해만 직접 라벨 (겹치면 하나만)
    hi, lo, last = s.idxmax(), s.idxmin(), s.index[-1]
    notes = {hi: ("최대", (40, 10)), lo: ("최소", (-30, -45))}
    notes.setdefault(last, ("", (0, 30)))
    for x, (label, offset) in notes.items():
        tag = f"{label} {x}년" if label else f"{x}년"
        if x == last and prelim.iloc[-1]:
            tag += " (잠정)"
        ax.annotate(f"{tag}\n{fmt(s[x])}", (x, s[x]), textcoords="offset points", xytext=offset,
                    ha="center", fontsize=10, color=INK, arrowprops=dict(arrowstyle="-", color=MUTED, lw=.8))

    span = s.max() - min(s.min(), 0)
    for y, label in REFERENCE_LINES.get(col, []):
        ax.axhline(y, color=MUTED, linewidth=.8, linestyle=":")
        ax.text(s.index[0] - .5, y + span * .012, label, color=MUTED, fontsize=9)
    if zero_line:
        ax.axhline(0, color=INK, linewidth=.8)

    _style(ax, f"대한민국 {col} 추이 ({s.index[0]}~{s.index[-1]})", ylabel, s.index[0], s.index[-1])
    if col in ("출생아수", "자연증가"):
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_man))
    # 최대/최소 라벨이 축 밖으로 잘리지 않게 위아래 여백
    if col == "출생아수":
        ax.set_ylim(0, s.max() * 1.12)
    else:
        lo_y, hi_y = min(s.min(), 0) if zero_line else s.min(), s.max()
        pad = (hi_y - lo_y) * .15 or 1
        ax.set_ylim(lo_y - pad, hi_y + pad)


def draw_births_vs_deaths(ax, df, start=1970, end=2025) -> None:
    """출생아수와 사망자수를 같은 축에 그려 자연감소 시점을 보여 준다."""
    sub = df.loc[start:end]
    b, d = sub["출생아수"].astype(float), sub["사망자수"].astype(float)
    ax.plot(b.index, b.values, color=LINE, linewidth=2, label="출생아수")
    ax.plot(d.index, d.values, color=DEATH, linewidth=2, label="사망자수")
    ax.fill_between(b.index, b.values, d.values, where=b.values < d.values,
                    color=DEATH, alpha=.12, interpolate=True, label="자연감소 구간")

    for name, s in (("출생", b), ("사망", d)):
        ax.annotate(f"{name} {s.iloc[-1]:,.0f}명", (s.index[-1], s.iloc[-1]), textcoords="offset points",
                    xytext=(6, 0), va="center", fontsize=9, color=INK)
    cross = sub.index[(sub["자연증가"] < 0).to_numpy()]
    if len(cross):
        ax.axvline(cross[0], color=MUTED, linewidth=.8, linestyle=":")
        ax.text(cross[0] - .3, b.max() * .95, f"{cross[0]}년 자연감소 시작", ha="right", color=MUTED, fontsize=9)

    _style(ax, f"출생아수 vs 사망자수 ({b.index[0]}~{b.index[-1]})", "인원 (명)", b.index[0], b.index[-1])
    ax.set_xlim(b.index[0] - 1, b.index[-1] + 4)   # 오른쪽 끝 라벨 자리
    ax.set_ylim(0, max(b.max(), d.max()) * 1.1)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_man))
    ax.legend(frameon=False, loc="upper right")


def plot_births(df, start=1970, end=2025) -> Path:
    fig, ax = plt.subplots(figsize=(14, 6))
    draw_metric(ax, df, "출생아수", start, end)
    fig.text(.99, .01, "자료: 통계청 「인구동향조사」 (KOSIS)  ·  2025년은 잠정치",
             ha="right", fontsize=8, color=MUTED)
    fig.tight_layout()

    s = df.loc[start:end]
    out = OUT_DIR / f"births_{s.index[0]}_{s.index[-1]}.png"
    fig.savefig(out, dpi=150)
    print(f"[차트 저장] {out}")
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    xlsx = Path(args[0]) if args else DEFAULT_XLSX
    plot_births(load_and_clean(xlsx))
    if "--show" in sys.argv:
        plt.show()
