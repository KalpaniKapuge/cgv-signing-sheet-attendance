"""
tools/estimate_attendance.py
=============================
Quick, honest presence check on the *real* aligned sheets in
data/output/aligned/, so Member 1's bar chart reflects the lecturer's actual
signing sheets instead of fabricated data.

This is a stand-in for Member 4's proper ink-detection module, not a
replacement for it. Two things it deliberately does NOT do:

  * Row position is *not* trusted from geometry.py's fixed fractions alone.
    Member 1's corner detection has +-15-20px jitter photo-to-photo, which is
    a big fraction of a single ~32px table row, so this script re-detects the
    actual printed row lines on every sheet individually (see
    `table_row_boundaries`) instead of assuming one global calibration holds
    for all photos.
  * It cannot distinguish a real signature from a handwritten absence note
    (one sheet has "ab" written in the signature cell instead of a
    signature) -- both are ink. That row will be misreported as present.
    Telling the two apart needs OCR/shape classification, which is out of
    scope here; flagged instead of silently ignored.

Writes data/output/attendance.csv with the schema viz/_data.py expects.
"""

import csv
import os
import sys
import xml.etree.ElementTree as ET

import cv2
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "src", "common")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config      # noqa: E402
import geometry    # noqa: E402

INK_THRESHOLD = 180        # grayscale value below which a pixel counts as ink
PRESENT_FRAC = 0.035       # ink fraction above which a cell counts as signed


def _candidate_lines(gray, y_search, x_range, min_dist=22, thresh=0.25):
    y0s, y1s = y_search
    x0, x1 = x_range
    dark = (gray[y0s:y1s, x0:x1] < 170).mean(axis=1)
    order = np.argsort(dark)[::-1]
    picked = []
    for i in order:
        if dark[i] < thresh:
            break
        if all(abs(i - p) >= min_dist for p in picked):
            picked.append(i)
    return sorted(y0s + p for p in picked)


def _best_run(lines, lo=26, hi=37):
    best, cur = [], [lines[0]]
    for y in lines[1:]:
        if lo <= y - cur[-1] <= hi:
            cur.append(y)
        else:
            if len(cur) > len(best):
                best = cur
            cur = [y]
    return cur if len(cur) > len(best) else best


def table_row_boundaries(gray):
    """8 y-coordinates: header-top, header/row1, row1/2, ..., row6/bottom."""
    lines = _candidate_lines(gray, y_search=(380, 750), x_range=(150, 680))
    run = _best_run(lines)
    step = round(np.median(np.diff(run)))
    while len(run) < 8:
        run = [run[0] - step] + run
    return run[:8]


def student_presence(aligned_bgr):
    gray = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2GRAY)
    boundaries = table_row_boundaries(gray)
    x0, x1 = geometry.signature_cells()[1][0], geometry.signature_cells()[1][2]
    result = {}
    for row in range(1, 7):
        y0, y1 = boundaries[row], boundaries[row + 1]
        crop = gray[y0 + 6:y1 - 6, x0 + 8:x1 + 45]   # +45: tolerate ink overflowing the ruled column
        frac = (crop < INK_THRESHOLD).mean() if crop.size else 0.0
        result[row] = (frac > PRESENT_FRAC, frac)
    return result


def load_students():
    root = ET.parse(config.INFO_XML).getroot()
    return [dict(s.attrib) for s in root.find("students")]


def main():
    students = load_students()
    idx_by_row = {int(s["row"]): s for s in students}
    aligned_dir = config.OUTPUT_DIR / "aligned"
    out = config.OUTPUT_DIR / "attendance.csv"

    rows_out = []
    for path in sorted(aligned_dir.glob("sheet_*.jpg")) + sorted(aligned_dir.glob("sheet_*.png")):
        date = path.stem.replace("sheet_", "")
        img = cv2.imread(str(path))
        presence = student_presence(img)
        print(f"[attendance] {path.name}")
        for row, stu in idx_by_row.items():
            present, frac = presence[row]
            print(f"    row{row} ({stu['name']}): ink_frac={frac:.3f} -> "
                  f"{'PRESENT' if present else 'absent'}")
            rows_out.append([date, stu["id"], stu["indexNo"], stu["name"],
                             int(present), "", 0])

    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "student_id", "index_no", "name", "present", "ink_colour", "forged"])
        w.writerows(rows_out)
    print(f"[attendance] -> {out}")
    print("[attendance] NOTE: ink-fraction alone can't tell a signature from a "
          "handwritten absence note (e.g. 'ab') -- verify visually if a report matters.")


if __name__ == "__main__":
    main()
