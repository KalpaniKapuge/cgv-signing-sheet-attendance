"""
viz/m6_box.py   (Member 6 - Data Visualization)
================================================
Box plot of the overall distribution of student attendance percentage
across the whole subject (one data point per student, from Member 6's
database). With only 6 students, the box alone would hide the actual
values, so every student's point is plotted directly on top of it and
labelled -- the box gives the summary (median/IQR/whiskers), the points
give the real, small-N data.

    make_figure()  -> matplotlib Figure   (used by the Member 8 dashboard)
    main()         -> saves data/output/charts/m6_box.png
"""

import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config     # noqa: E402
import _data      # noqa: E402

BOX_COLOUR = "#2563eb"
TARGET_LINE = 80.0


def make_figure():
    df = _data.load_attendance()
    per_student = _data.per_student(df)
    pct = per_student["pct"].tolist()
    names = per_student["name"].tolist()

    fig, ax = plt.subplots(figsize=(7, 5))

    bp = ax.boxplot(pct, orientation="vertical", widths=0.35, positions=[1],
                     patch_artist=True, showfliers=False, zorder=2,
                     medianprops=dict(color="#0b0b0b", linewidth=2),
                     boxprops=dict(facecolor=BOX_COLOUR, alpha=0.18,
                                   edgecolor=BOX_COLOUR, linewidth=1.5),
                     whiskerprops=dict(color=BOX_COLOUR, linewidth=1.5),
                     capprops=dict(color=BOX_COLOUR, linewidth=1.5))

    # Deterministic beeswarm: students who share the exact same percentage
    # (common here -- only 2 distinct values across 6 students) get spread
    # evenly across x instead of randomly jittered, which at this N clustered
    # points -- and their labels -- on top of each other.
    order = sorted(range(len(pct)), key=lambda i: (pct[i], names[i]))
    xs, ys, ordered_names = [0.0] * len(pct), [0.0] * len(pct), [""] * len(pct)
    for value in sorted(set(pct)):
        idxs = [i for i in order if pct[i] == value]
        n = len(idxs)
        spread = np.linspace(-0.34, 0.34, n) if n > 1 else [0.0]
        for i, dx in zip(idxs, spread):
            xs[i], ys[i], ordered_names[i] = 1 + dx, pct[i], names[i]

    ax.scatter(xs, ys, s=70, color=BOX_COLOUR, edgecolor="white",
               linewidth=1.2, zorder=3)
    for x, y, name in zip(xs, ys, ordered_names):
        ax.annotate(name.split()[-1], (x, y), textcoords="offset points",
                    xytext=(0, 11), ha="center", fontsize=8.5, color="#52514e")

    ax.axhline(TARGET_LINE, ls="--", lw=1, color="#dc2626", zorder=1)
    ax.text(1.75, TARGET_LINE - 2.5, f"target {TARGET_LINE:.0f}%",
            ha="right", va="top", fontsize=8, color="#dc2626")

    ax.set_xlim(0.5, 1.9)
    ax.set_xticks([1])
    ax.set_xticklabels(["All students"])
    ax.set_ylim(0, 112)
    ax.set_ylabel("Attendance (%)")
    ax.set_title("Distribution of Student Attendance  -  BSc SE 2016.1 (CGV)",
                 fontsize=12, weight="bold")
    ax.grid(axis="y", ls=":", alpha=0.5, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig


def main():
    out = config.OUTPUT_DIR / "charts" / "m6_box.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig = make_figure()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"[M6] box plot -> {out}")


if __name__ == "__main__":
    main()
