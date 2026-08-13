"""
dashboard.py   (Member 8 - Data Visualization Dashboard)
==========================================================
Main UI: one Streamlit page integrating every chart the other members
built, reusing each one's own make_figure() rather than re-implementing any
plotting logic here.

    Overview tab      -- class-wide charts (Members 1, 2, 3, 4, 6)
    Student Lookup    -- per-student charts (Members 5, 7), student picked
                          from a single shared selector

Run:
    streamlit run dashboard.py

(Member 8's OTHER deliverable, the live OpenCV preprocessing preview
(src/m8_preview.py), is a separate native window, not a web widget -- it
can't be embedded in a browser page the way these figures can, so it's
launched as its own script; this dashboard links to it for reference.)
"""

import os
import sys

import streamlit as st

_ROOT = os.path.dirname(os.path.abspath(__file__))
for _p in (_ROOT, os.path.join(_ROOT, "viz"), os.path.join(_ROOT, "src"),
           os.path.join(_ROOT, "src", "common")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config           # noqa: E402
import m5_mapping       # noqa: E402
import m1_bar           # noqa: E402
import m2_line          # noqa: E402
import m3_pie           # noqa: E402
import m4_heatmap       # noqa: E402
import m6_box           # noqa: E402
import infovis          # noqa: E402
import investigate      # noqa: E402

st.set_page_config(page_title="CGV Signing Sheet Attendance", layout="wide")

st.title("Signing Sheet Attendance Dashboard")
st.caption("BSc (Hons) in Software Engineering 2016.1  -  Computer Graphics and Visualization")

tab_overview, tab_student = st.tabs(["Overview", "Student Lookup"])

# --------------------------------------------------------------------------- #
# Overview: class-wide charts (Members 1, 2, 3, 4, 6)
# --------------------------------------------------------------------------- #
with tab_overview:
    row1_left, row1_right = st.columns(2)
    with row1_left:
        st.subheader("Attendance per Session")
        st.pyplot(m1_bar.make_figure(), clear_figure=True)
    with row1_right:
        st.subheader("Attendance Trend Over Time")
        st.pyplot(m2_line.make_figure(), clear_figure=True)

    row2_left, row2_right = st.columns(2)
    with row2_left:
        st.subheader("Signatures by Ink Colour")
        st.pyplot(m3_pie.make_figure(), clear_figure=True)
    with row2_right:
        st.subheader("Distribution of Student Attendance")
        st.pyplot(m6_box.make_figure(), clear_figure=True)

    st.subheader("Attendance Heatmap")
    st.pyplot(m4_heatmap.make_figure(), clear_figure=True)

# --------------------------------------------------------------------------- #
# Student Lookup: per-student charts (Members 5, 7), one shared selector
# --------------------------------------------------------------------------- #
with tab_student:
    _, students, _ = m5_mapping.load_info()
    options = {f"{s['id']}  -  {s['name']}": s["id"]
               for s in sorted(students, key=lambda s: s["id"])}
    picked = st.selectbox("Student", list(options.keys()))
    student_id = options[picked]

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Overall Attendance")
        # theme=None: st.plotly_chart's default "streamlit" theme re-colours
        # the figure's text to match Streamlit's active theme (light grey in
        # dark mode), which clashes with the gauge's own explicit white
        # background from infovis.py and reads as washed-out/illegible.
        # theme=None keeps the figure's own colours as designed.
        st.plotly_chart(infovis.make_figure(student_id), width="stretch", theme=None)
    with col_right:
        st.subheader("Signature Match Confidence")
        try:
            st.pyplot(investigate.make_figure(student_id), clear_figure=True)
        except ValueError as e:
            st.info(str(e))

st.divider()
st.caption(
    "Image-processing live preview (Grayscale -> Otsu -> Morphology) opens "
    "as its own OpenCV window, not a web widget -- run it separately:  "
    "`python src/m8_preview.py [student_id] [date]`"
)
