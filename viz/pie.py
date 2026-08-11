"""
viz/m3_pie.py   (Member 3 - Data Visualization)
===============================================
Pie chart separating student attendance by the pen ink colour used
(Blue / Black / Green), counted over every signed cell in all sessions.

    make_figure()  -> matplotlib Figure   (used by the Member 8 dashboard)
    main()         -> saves data/output/charts/m3_pie.png
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

# slice colours chosen to match the ink they represent
SLICE_COLOURS = {"Blue": "#2563eb", "Black": "#374151", "Green": "#16a34a"}
ORDER = ["Blue", "Black", "Green"]


def make_figure():
    df = _data.load_attendance()
    signed = df[df["present"] == 1]
    counts = signed["ink_colour"].value_counts()
    labels = [c for c in ORDER if counts.get(c, 0) > 0]
    sizes = [int(counts.get(c, 0)) for c in labels]
    colours = [SLICE_COLOURS[c] for c in labels]

    fig, ax = plt.subplots(figsize=(6.5, 5))
    # The donut ring only spans radius 0.58-1.0 (wedgeprops width=0.42 below),
    # but autopct's default pctdistance=0.6 places labels just inside that --
    # right at the ring's inner edge, so they render half over the empty
    # hole and look clipped. Center them in the ring instead.
    wedges, _texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colours, autopct=lambda p: f"{p:.0f}%",
        startangle=90, counterclock=False, pctdistance=0.79,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
        textprops=dict(fontsize=11),
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontweight("bold")

    total = sum(sizes)
    ax.text(0, 0, f"{total}\nsignatures", ha="center", va="center",
            fontsize=13, weight="bold", color="#111")
    ax.legend(wedges, [f"{l}: {s}" for l, s in zip(labels, sizes)],
              loc="lower center", bbox_to_anchor=(0.5, -0.08), ncol=len(labels),
              frameon=False, fontsize=10)
    ax.set_title("Signatures by Ink Colour  -  BSc SE 2016.1 (CGV)",
                 fontsize=12, weight="bold")
    ax.set_aspect("equal")
    fig.tight_layout()
    return fig


def main():
    out = config.OUTPUT_DIR / "charts" / "m3_pie.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig = make_figure()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"[M3] pie chart -> {out}")


if __name__ == "__main__":
    main()