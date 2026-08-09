"""
viz/m1_bar.py   (Member 1 - Data Visualization)
===============================================
Bar chart of the overall class attendance for the whole batch: one bar per
signing session, height = percentage of the class that signed that day.

    make_figure()  -> matplotlib Figure   (used by the Member 8 dashboard)
    main()         -> saves data/output/charts/m1_bar.png
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")                      # safe for headless / saving to file
import matplotlib.pyplot as plt

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import config                              # noqa: E402
import _data                               # noqa: E402

BAR_COLOR = "#2563eb"
TARGET_LINE = 80.0                         # illustrative attendance target


def make_figure():
    df = _data.load_attendance()
    g = _data.per_session(df)
    labels = g["date"].dt.strftime("%d %b").tolist()
    pct = g["pct"].tolist()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(labels, pct, color=BAR_COLOR, width=0.6, zorder=3)

    for bar, p, present, total in zip(bars, pct, g["present"], g["total"]):
        ax.text(bar.get_x() + bar.get_width() / 2, p + 1.5,
                f"{p:.0f}%\n({present}/{total})", ha="center", va="bottom",
                fontsize=9, color="#111")

    ax.axhline(TARGET_LINE, ls="--", lw=1, color="#dc2626", zorder=2)
    ax.text(len(labels) - 0.5, TARGET_LINE + 1, f"target {TARGET_LINE:.0f}%",
            ha="right", va="bottom", fontsize=8, color="#dc2626")

    ax.set_ylim(0, 112)
    ax.set_ylabel("Attendance (%)")
    ax.set_title("Class Attendance per Session  -  BSc SE 2016.1 (CGV)",
                 fontsize=12, weight="bold")
    ax.grid(axis="y", ls=":", alpha=0.5, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig


def main():
    out = config.OUTPUT_DIR / "charts" / "m1_bar.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig = make_figure()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"[M1] bar chart -> {out}")


if __name__ == "__main__":
    main()