"""
src/common/geometry.py
======================
THE canonical description of the signing-sheet template.

This module is the backbone of the whole project. It defines, in normalized
[0, 1] coordinates, where every text label and every table cell sits on the
sheet. Two very different consumers use it and must agree exactly:

  * tools/generate_synthetic_sheets.py  -> draws the template from this spec
  * src/m2_crop.py (Member 2)           -> crops signature cells from this spec

Because both derive pixel coordinates from the same normalized numbers, a
cropped cell always lands on the right place after Member 1 warps a photo onto
the fixed TEMPLATE_W x TEMPLATE_H canvas.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from config import TEMPLATE_W, TEMPLATE_H

Rect = Tuple[int, int, int, int]  # (x0, y0, x1, y1) in pixels

# --------------------------------------------------------------------------- #
# Normalized layout constants
# --------------------------------------------------------------------------- #
HEADER_LEFT_FX = 0.06
HEADER_TOP_FY  = 0.055

# Info table (Date | Time | Lecturer name | Lecturer signature)
# Measured directly off the lecturer's real signing sheets (aligned+deskewed
# 1000x1400 canvas), not the earlier fabricated synthetic template -- see
# tools/measure_geometry.py for how these were derived. Expect +-1-2% jitter
# sheet-to-sheet from Member 1's corner-detection precision; crop with a
# small margin rather than assuming exact pixel edges.
INFO_LEFT_FX   = 0.120
INFO_RIGHT_FX  = 0.800
INFO_TOP_FY    = 0.281
INFO_BOTTOM_FY = 0.326
INFO_MID_FY    = 0.314
INFO_COL_FX    = [0.120, 0.330, 0.400, 0.731, 0.800]   # Date, Time, Lecturer, Signature

# Main student table
TABLE_LEFT_FX   = 0.118
TABLE_RIGHT_FX  = 0.783
TABLE_TOP_FY    = 0.326   # == INFO_BOTTOM_FY: the info table's bottom border is the table's top border
TABLE_BOTTOM_FY = 0.487
N_STUDENTS      = 6
N_ROWS          = N_STUDENTS + 1                  # +1 header row

# Column x-boundaries: No | Student No | Title | Student Name | Signature
COL_FX        = [0.118, 0.199, 0.331, 0.402, 0.692, 0.783]
COL_NAMES     = ["No", "Student No", "Title", "Student Name", "Signature"]
SIGNATURE_COL = 4


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _px(fx: float, fy: float) -> Tuple[int, int]:
    return round(fx * TEMPLATE_W), round(fy * TEMPLATE_H)


def _row_bounds(row: int) -> Tuple[float, float]:
    step = (TABLE_BOTTOM_FY - TABLE_TOP_FY) / N_ROWS
    top = TABLE_TOP_FY + row * step
    return top, top + step


def _col_bounds(col: int) -> Tuple[float, float]:
    return COL_FX[col], COL_FX[col + 1]


# --------------------------------------------------------------------------- #
# Public geometry API
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TableCell:
    row: int          # 0 = header, 1..6 = students
    col: int          # column index
    rect: Rect        # pixel rectangle on the canonical canvas


def main_table_outline() -> Rect:
    x0, y0 = _px(TABLE_LEFT_FX, TABLE_TOP_FY)
    x1, y1 = _px(TABLE_RIGHT_FX, TABLE_BOTTOM_FY)
    return (x0, y0, x1, y1)


def all_main_cells() -> List[TableCell]:
    cells: List[TableCell] = []
    for r in range(N_ROWS):
        top_fy, bot_fy = _row_bounds(r)
        for c in range(len(COL_NAMES)):
            l_fx, r_fx = _col_bounds(c)
            x0, y0 = _px(l_fx, top_fy)
            x1, y1 = _px(r_fx, bot_fy)
            cells.append(TableCell(r, c, (x0, y0, x1, y1)))
    return cells


def signature_cells() -> Dict[int, Rect]:
    """
    Map each student row (1..6) to the pixel rectangle of their signature cell.
    Member 2 crops exactly these rectangles.
    """
    out: Dict[int, Rect] = {}
    l_fx, r_fx = _col_bounds(SIGNATURE_COL)
    for student in range(1, N_STUDENTS + 1):
        top_fy, bot_fy = _row_bounds(student)     # row 0 is the header
        x0, y0 = _px(l_fx, top_fy)
        x1, y1 = _px(r_fx, bot_fy)
        out[student] = (x0, y0, x1, y1)
    return out


def info_table_cells() -> Dict[str, Rect]:
    """Return the header/value cells of the info table for drawing."""
    cells = {}
    labels = ["Date", "Time", "Lecturer", "LecSig"]
    for i, key in enumerate(labels):
        lx, rx = INFO_COL_FX[i], INFO_COL_FX[i + 1]
        hx0, hy0 = _px(lx, INFO_TOP_FY)
        hx1, hy1 = _px(rx, INFO_MID_FY)
        vx0, vy0 = _px(lx, INFO_MID_FY)
        vx1, vy1 = _px(rx, INFO_BOTTOM_FY)
        cells[key + "_head"] = (hx0, hy0, hx1, hy1)
        cells[key + "_val"] = (vx0, vy0, vx1, vy1)
    return cells


def lecturer_signature_cell() -> Rect:
    l_fx, r_fx = INFO_COL_FX[3], INFO_COL_FX[4]
    x0, y0 = _px(l_fx, INFO_MID_FY)
    x1, y1 = _px(r_fx, INFO_BOTTOM_FY)
    return (x0, y0, x1, y1)


def template_corners() -> List[Tuple[int, int]]:
    """Four corners [top-left, top-right, bottom-right, bottom-left]."""
    return [(0, 0), (TEMPLATE_W - 1, 0),
            (TEMPLATE_W - 1, TEMPLATE_H - 1), (0, TEMPLATE_H - 1)]


if __name__ == "__main__":
    print(f"Canvas: {TEMPLATE_W} x {TEMPLATE_H}")
    for row, rect in signature_cells().items():
        print(f"  student {row}: {rect}")
    print("Lecturer cell:", lecturer_signature_cell())
