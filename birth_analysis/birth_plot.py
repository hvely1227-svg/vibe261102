"""대한민국 출생아수 1970 ~ 2025 라인그래프."""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from birth_analysis import DEFAULT_XLSX, OUT_DIR, load_and_clean

plt.rcParams["font.family"] = "Malgun Gothic"   # 한글 폰트 (Windows)
plt.rcParams["axes.unicode_minus"] = False

LINE = "#1f5fbf"
INK, MUTED = "#222222", "#777777"


def plot_births(df, start=1970, end=2025) -> Path:
    s = df.loc[start:end, "출생아수"].astype(float)
    prelim = df.loc[start:end, "잠정치"]

    fig, ax = plt.subplots(figsize=(14, 6))
    final = s[~prelim.values]
    ax.plot(final.index, final.values, color=LINE, linewidth=2, marker="o", markersize=3.5)

    # 잠정치(2025 p)는 점선 + 속 빈 마커로 구분
    if prelim.any():
        p = s.index[prelim.values][0]
        ax.plot([p - 1, p], [s[p - 1], s[p]], color=LINE, linewidth=2, linestyle="--", zorder=1)
        ax.plot(p, s[p], marker="o", markersize=7, markerfacecolor="white", markeredgecolor=LINE, markeredgewidth=2)

    # 최다·최소·마지막 해만 직접 라벨
    peak, low, last = s.idxmax(), s.idxmin(), s.index[-1]
    notes = [(peak, f"최다 {peak}년\n{s[peak]:,.0f}명", (40, 10)),
             (low, f"최소 {low}년\n{s[low]:,.0f}명", (-30, -45)),
             (last, f"{last}년{' (잠정)' if prelim.iloc[-1] else ''}\n{s[last]:,.0f}명", (0, 30))]
    for x, text, offset in notes:
        ax.annotate(text, (x, s[x]), textcoords="offset points", xytext=offset, ha="center",
                    fontsize=10, color=INK, arrowprops=dict(arrowstyle="-", color=MUTED, lw=.8))

    # 기준선: 50만 / 30만 명
    for y in (500_000, 300_000):
        ax.axhline(y, color=MUTED, linewidth=.8, linestyle=":")
        ax.text(s.index[0] + .3, y + 12_000, f"{y // 10_000}만 명", color=MUTED, fontsize=9)

    ax.set_title(f"대한민국 출생아수 추이 ({s.index[0]}~{s.index[-1]})", fontsize=15, color=INK, loc="left")
    ax.set_xlabel("연도", color=MUTED)
    ax.set_ylabel("출생아수 (명)", color=MUTED)
    ax.set_xlim(s.index[0] - 1, s.index[-1] + 1)
    ax.set_ylim(0, s.max() * 1.12)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(5))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v / 10_000:,.0f}만" if v else "0"))
    ax.grid(axis="y", alpha=.25)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED)
    fig.text(.99, .01, "자료: 통계청 「인구동향조사」 (KOSIS)  ·  2025년은 잠정치",
             ha="right", fontsize=8, color=MUTED)
    fig.tight_layout()

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
