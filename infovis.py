"""
infovis.py   (Member 5 - Data Visualization)
=============================================
Speedometer-style gauge chart of one student's overall attendance
percentage, computed from the real image-processing pipeline (Members 1-4)
via src/m5_mapping.py -- not the synthetic ground-truth CSV the other charts
bootstrap from.

Usage
-----
    python infovis.py <student>

    <student> can be a short id ("001"), a full index number ("10000409"),
    or part of a name ("chithrananda"). Requires src/m1_alignment.py and
    src/m2_crop.py to have already been run (the gauge reads Member 2's
    crops), otherwise sessions show as "not yet processed".

Writes data/output/charts/m5_gauge_<id>.html (open it in a browser -- an
interactive gauge needs a browser, not a static image).
"""

import os
import sys

import plotly.graph_objects as go

_ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in (_ROOT, os.path.join(_ROOT, "src"), os.path.join(_ROOT, "src", "common")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config          # noqa: E402
import m5_mapping       # noqa: E402

# Same reserved status palette as Member 4's heatmap: attendance is a state,
# not a category, so it gets its own good/warning/critical band rather than
# the blue/black/green used for ink colour elsewhere.
GOOD, WARNING, CRITICAL = "#0ca30c", "#fab219", "#d03b3b"


def _band_colour(pct: float) -> str:
    if pct >= 80:
        return GOOD
    if pct >= 50:
        return WARNING
    return CRITICAL


def make_figure(student_key: str):
    summary = m5_mapping.attendance_summary(student_key)
    student, pct = summary["student"], summary["pct"]
    unscored = [r for r in summary["rows"] if r["present"] is None]

    # Every text element below gets an explicit colour rather than relying on
    # a default/inherited one: embedded in Streamlit, an unstyled element can
    # pick up the *page's* active theme (dark, light grey text) instead of
    # this figure's own white background, and render almost invisibly.
    INK, INK_SOFT = "#0b0b0b", "#52514e"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        domain={"x": [0.08, 0.92], "y": [0.05, 0.82]},
        number={"suffix": "%", "font": {"size": 40, "color": INK}},
        title={"text": f"<span style='color:{INK}'>{student['name']}</span><br>"
                       f"<span style='font-size:0.7em;color:{INK_SOFT}'>"
                       f"Index {student['indexNo']}  -  {summary['attended']}/"
                       f"{summary['total']} sessions signed</span>",
               "font": {"color": INK}},
        gauge={
            "axis": {"range": [0, 100], "ticksuffix": "%",
                     "tickfont": {"color": INK_SOFT}},
            "bar": {"color": _band_colour(pct)},
            "bordercolor": INK_SOFT,
            "steps": [
                {"range": [0, 50], "color": "#fbe2e2"},
                {"range": [50, 80], "color": "#fdefd2"},
                {"range": [80, 100], "color": "#d9f0d9"},
            ],
            "threshold": {"line": {"color": INK, "width": 3},
                          "thickness": 0.8, "value": pct},
        },
    ))
    note = (f"{len(unscored)} session(s) not yet processed by Members 1-2"
            if unscored else None)
    fig.update_layout(
        width=640, height=520, margin=dict(l=60, r=60, t=120, b=60),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(color=INK),
        annotations=[dict(text=note, x=0.5, y=0.0, showarrow=False,
                           font=dict(size=11, color="#d03b3b"))] if note else [],
    )
    return fig


def main():
    if len(sys.argv) < 2:
        print("Usage: python infovis.py <student>   e.g. python infovis.py 001")
        sys.exit(1)
    key = sys.argv[1]
    try:
        fig = make_figure(key)
    except ValueError as e:
        print(f"[M5] {e}")
        sys.exit(1)

    out = config.OUTPUT_DIR / "charts" / f"m5_gauge_{key}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out)
    print(f"[M5] gauge -> {out}")


if __name__ == "__main__":
    main()
