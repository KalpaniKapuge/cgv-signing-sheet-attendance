"""
investigate.py   (Member 7 - Data Visualization)
=================================================
Scatter plot of one student's signature match confidence (SSIM similarity
%) against their genuine template, one point per session, via
src/m7_investigate.py.

Usage
-----
    python investigate.py <student>

    <student> can be a short id ("001"), a full index number, or part of a
    name. Requires src/m1_alignment.py through src/m2_crop.py to have
    already been run.

IMPORTANT: read src/m7_investigate.py's module docstring before trusting
any "possible forgery" flag here -- the technique's real-world separation
was measured at only ~65% accuracy on this project's real photos (56% is
guessing). This chart is a demonstration of the mechanism, not a reliable
forgery detector; the caveat is also stamped on the chart itself.

Writes data/output/charts/m7_scatter_<id>.png.
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in (_ROOT, os.path.join(_ROOT, "src"), os.path.join(_ROOT, "src", "common")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config              # noqa: E402
import m7_investigate      # noqa: E402

# Same reserved status palette used across the dashboard (Members 4 and 5).
BASELINE_COLOUR = "#52514e"
GOOD, CRITICAL = "#0ca30c", "#d03b3b"
UNSCORED_COLOUR = "#c3c2b7"

_STATUS_COLOUR = {
    "baseline": BASELINE_COLOUR,
    "genuine": GOOD,
    "possible-forgery": CRITICAL,
}
_STATUS_LABEL = {
    "baseline": "Baseline (enrolled)",
    "genuine": "Genuine match",
    "possible-forgery": "Possible forgery",
    "absent": "Absent",
    "not-cropped": "Not yet processed",
}


def make_figure(student_key: str):
    result = m7_investigate.investigate_student(student_key)
    student, rows = result["student"], result["rows"]

    fig, ax = plt.subplots(figsize=(9, 5.2))
    threshold_pct = config.SSIM_MATCH_THRESHOLD * 100
    ax.axhline(threshold_pct, ls="--", lw=1, color=CRITICAL, zorder=1)
    ax.text(0.15, threshold_pct + 2, f"match threshold {threshold_pct:.0f}%",
            ha="left", fontsize=8, color=CRITICAL)

    xs = list(range(len(rows)))
    labels = [r["date"] for r in rows]
    for x, r in zip(xs, rows):
        if r["score"] is None:
            ax.scatter(x, 2, marker="x", s=60, color=UNSCORED_COLOUR, zorder=3)
            ax.annotate(_STATUS_LABEL[r["status"]], (x, 2), textcoords="offset points",
                        xytext=(0, -14), ha="center", fontsize=8, color=UNSCORED_COLOUR)
            continue
        pct = r["score"] * 100
        colour = _STATUS_COLOUR[r["status"]]
        ax.scatter(x, pct, s=110, color=colour, edgecolor="white",
                   linewidth=1.3, zorder=3)
        # Labels default above the point; points sitting close to the
        # threshold line get pushed further away from it (down if the point
        # is below the line, up if above), so the label text never sits on
        # top of the dashed line.
        near_threshold = abs(pct - threshold_pct) < 6
        below_line = pct < threshold_pct
        dy = -16 if (near_threshold and below_line) else \
             18 if (near_threshold and not below_line) else 11
        va = "top" if dy < 0 else "bottom"
        ax.annotate(f"{pct:.0f}%", (x, pct), textcoords="offset points",
                    xytext=(0, dy), ha="center", va=va, fontsize=9,
                    color="#0b0b0b", fontweight="bold")

    handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=c,
                           markersize=9, label=_STATUS_LABEL[k])
               for k, c in _STATUS_COLOUR.items()]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.14),
              ncol=3, frameon=False, fontsize=9)

    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 112)
    ax.set_ylabel("Match confidence vs. genuine template (%)")
    ax.set_title(f"Signature Match Confidence  -  {student['name']} "
                 f"(Index {student['indexNo']})", fontsize=12, weight="bold")
    ax.grid(axis="y", ls=":", alpha=0.5, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)

    fig.text(0.5, 0.045,
              "Caveat: ~65% real-world separation accuracy on this dataset "
              "(one baseline/student, no true forged samples) -- see src/m7_investigate.py.",
              ha="center", fontsize=7.5, color="#898781", style="italic")
    fig.text(0.5, 0.015, "Indicative, not authoritative.",
              ha="center", fontsize=7.5, color="#898781", style="italic")
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    return fig


def main():
    if len(sys.argv) < 2:
        print("Usage: python investigate.py <student>   e.g. python investigate.py 001")
        sys.exit(1)
    key = sys.argv[1]
    try:
        fig = make_figure(key)
    except ValueError as e:
        print(f"[M7] {e}")
        sys.exit(1)

    out = config.OUTPUT_DIR / "charts" / f"m7_scatter_{key}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"[M7] scatter -> {out}")


if __name__ == "__main__":
    main()