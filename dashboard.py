"""(Member 8 - Data Visualization Dashboard)
==========================================================
Main UI: one Streamlit page integrating every chart the other members
built, reusing each one's own make_figure() rather than re-implementing any
plotting logic here.

    Overview tab      -- class-wide charts (Members 1, 2, 3, 4, 6)
    Student Lookup    -- per-student charts (Members 5, 7), student picked
                          from a single shared selector

Run:
    streamlit run dashboard.py

"""
import os
import sys

import streamlit as st

ROOT = os.path.dirname(os.path.abspath(file_))
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