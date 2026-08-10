"""
viz/m2_line.py   (Data Visualization)
================================================
Line chart showing how the class attendance percentage changes over time
(session by session). A dashed trend context line marks the mean.

    make_figure()  -> matplotlib Figure   (used by the Member 8 dashboard)
    main()         -> saves data/output/charts/m2_line.png
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config     # noqa: E402
import _data      # noqa: E402

LINE_COLOR = "#0d9488"


def make_figure():
    df = _data.load_attendance()
    g = _data.per_session(df).sort_values("date")
    x = g["date"].dt.strftime("%d %b").tolist()
    y = g["pct"].tolist()
    mean_pct = sum(y) / len(y)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(x, y, marker="o", ms=8, lw=2.5, color=LINE_COLOR, zorder=3)
    ax.fill_between(range(len(x)), y, alpha=0.12, color=LINE_COLOR, zorder=1)
    for xi, yi in zip(range(len(x)), y):
        ax.annotate(f"{yi:.0f}%", (xi, yi), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=9, color="#111")
    ax.axhline(mean_pct, ls="--", lw=1, color="#6b7280", zorder=2)
    ax.text(len(x) - 1, mean_pct + 1.5, f"mean {mean_pct:.0f}%",
            ha="right", fontsize=8, color="#6b7280")

    ax.set_ylim(0, 112)
    ax.set_ylabel("Attendance (%)")
    ax.set_title("Attendance Trend Over Time  -  BSc SE 2016.1 (CGV)",
                 fontsize=12, weight="bold")
    ax.grid(axis="y", ls=":", alpha=0.5)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig


def main():
    out = config.OUTPUT_DIR / "charts" / "m2_line.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig = make_figure()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"[M2] line chart -> {out}")


if __name__ == "__main__":
    main()