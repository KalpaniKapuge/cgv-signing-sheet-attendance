"""
src/m5_mapping.py   (Member 5 - Image Processing / Data Mapping)
==================================================================
Parses info.xml (subject info, student roster, session list) and maps each
student's table row to their actual attendance status for every session --
derived by running the real image-processing pipeline (Member 2's crops,
Member 4's present/absent decision, Member 3's ink colour), not the
synthetic ground-truth CSV the other charts bootstrap from.

info.xml gives each student a `row` (1..6, their fixed position on every
sheet) and an `id` (001..006, the short local index infovis.py takes on the
command line). Member 2 already crops data/output/crops/sheet_<date>/
row_<row>.png for every sheet; this module is the glue that says "row 3 on
2019-06-28" is actually "B A K M Chithrananda" and asks Members 3/4 whether
that specific cell was signed.

Public API
----------
    load_info()                    -> (subject: dict, students: list[dict], sessions: list[dict])
    find_student(key)              -> student dict, or None (key = id "001", index_no, or name substring)
    session_status(student, sess)  -> (present: bool|None, ink_colour: str|None, reason: str)
                                       present/ink_colour are None if that sheet hasn't been cropped yet
    attendance_summary(key)        -> dict(student, rows=[...], attended, total, pct)
    build_all()                    -> list[dict], one row per (student, session) -- every student
"""

import os
import sys
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "src", "common")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config          # noqa: E402
import io_utils        # noqa: E402
import m3_preprocess   # noqa: E402
import m4_detect       # noqa: E402


# --------------------------------------------------------------------------- #
# info.xml
# --------------------------------------------------------------------------- #
def load_info() -> Tuple[Dict, List[Dict], List[Dict]]:
    """(subject, students, sessions). students/sessions are lists of dict(**attrib)."""
    root = ET.parse(config.INFO_XML).getroot()
    subject = {c.tag: (c.text or "").strip() for c in root.find("subject")}
    students = [dict(s.attrib) for s in root.find("students")]
    sessions = [dict(s.attrib) for s in root.find("sessions")]
    return subject, students, sessions


def find_student(key: str) -> Optional[Dict]:
    """Look up a student by short id ("001"), full index number, or a name
    substring (case-insensitive) -- whatever infovis.py was given on the CLI."""
    _, students, _ = load_info()
    key = str(key).strip()
    for s in students:
        if key == s["id"] or key.lstrip("0") == s["id"].lstrip("0"):
            return s
    for s in students:
        if key == s["indexNo"]:
            return s
    key_low = key.lower()
    for s in students:
        if key_low in s["name"].lower():
            return s
    return None


# --------------------------------------------------------------------------- #
# Row -> signature status
# --------------------------------------------------------------------------- #
def session_status(student: Dict, session: Dict) -> Tuple[Optional[bool], Optional[str], str]:
    """
    (present, ink_colour, reason) for one student on one session, read from
    Member 2's crop of that student's row. present/ink_colour are None (with
    reason "not-cropped") if that sheet hasn't reached data/output/crops/ yet
    -- run src/m1_alignment.py + src/m2_crop.py first.
    """
    crop_path = (config.OUTPUT_DIR / "crops" / f"sheet_{session['date']}"
                 / f"row_{student['row']}.png")
    if not crop_path.exists():
        return None, None, "not-cropped"

    crop = io_utils.load_bgr(crop_path)
    present, reason = m4_detect.detect_presence(crop)
    ink_colour = m3_preprocess.classify_ink_colour(crop) if present else None
    return present, ink_colour, reason


def attendance_summary(key: str) -> Dict:
    """Full attendance record for one student across every session in info.xml."""
    student = find_student(key)
    if student is None:
        raise ValueError(f"No student matches '{key}' (try an id like '001', "
                          f"a full index number, or part of their name)")
    _, _, sessions = load_info()

    rows = []
    for sess in sorted(sessions, key=lambda s: s["date"]):
        present, ink_colour, reason = session_status(student, sess)
        rows.append({"date": sess["date"], "present": present,
                      "ink_colour": ink_colour, "reason": reason})

    scored = [r for r in rows if r["present"] is not None]
    attended = sum(1 for r in scored if r["present"])
    total = len(scored)
    pct = round(attended / total * 100, 1) if total else 0.0
    return {"student": student, "rows": rows, "attended": attended,
            "total": total, "pct": pct}


def build_all() -> List[Dict]:
    """One row per (student, session) for every student -- the same shape as
    viz/_data.py's attendance table, but sourced from the real pipeline."""
    _, students, sessions = load_info()
    out = []
    for student in sorted(students, key=lambda s: s["id"]):
        for sess in sorted(sessions, key=lambda s: s["date"]):
            present, ink_colour, reason = session_status(student, sess)
            out.append({
                "date": sess["date"], "student_id": student["id"],
                "index_no": student["indexNo"], "name": student["name"],
                "present": present, "ink_colour": ink_colour, "reason": reason,
            })
    return out


# --------------------------------------------------------------------------- #
# Batch demo / testing
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    rows = build_all()
    by_student: Dict[str, List[Dict]] = {}
    for r in rows:
        by_student.setdefault(r["student_id"], []).append(r)

    for sid, recs in sorted(by_student.items()):
        name = recs[0]["name"]
        cells = []
        for r in recs:
            if r["present"] is None:
                cells.append(f"{r['date']}:?")
            else:
                mark = "P" if r["present"] else "A"
                cells.append(f"{r['date']}:{mark}")
        print(f"[M5] {sid} {name:32s} {'  '.join(cells)}")
