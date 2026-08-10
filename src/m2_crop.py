"""
src/m2_crop.py   (Member 2 - Image Processing)
==============================================
Takes an *aligned* sheet (output of Member 1) and crops out the six signature
bounding boxes - one per student row.

Because Member 1 has already warped the sheet onto the fixed template canvas,
the grid is close to its known template position. Member 2 still *detects* the
grid so the crop is driven by the actual ruled lines rather than blind
coordinates:

1. Threshold (inverse) so ink + ruled lines become white on black.
2. Morphological opening with a long horizontal kernel isolates horizontal
   ruled lines; a long vertical kernel isolates vertical ruled lines.
3. Project each line image onto an axis and cluster the peaks to recover the
   y-positions of the horizontal rules and the x-positions of the vertical rules.
4. The signature column is the right-most column band; the six student rows are
   the row bands below the header. Crop each (row x signature-column) cell.

If detection is unreliable (too few lines found), the module falls back to the
exact template rectangles from geometry.signature_cells(), so cropping never
fails outright.

Public API
----------
    crop_signatures(aligned_bgr) -> {row: crop_bgr}          # row 1..6
    crop_file(aligned_path)      -> {row: crop_bgr}
    crop_all()                   -> writes crops to data/output/crops/
"""

import os
import sys
from typing import Dict, List

import cv2
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "src", "common")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config          # noqa: E402
import geometry        # noqa: E402
import io_utils        # noqa: E402


# --------------------------------------------------------------------------- #
# Line detection
# --------------------------------------------------------------------------- #
def _binary_lines(gray: np.ndarray, v_kernel_len: int = None):
    """
    Return (horizontal_lines, vertical_lines) as binary images.

    `v_kernel_len` sizes the vertical opening kernel. It defaults to a
    page-scale estimate, but the table's column rules are only continuous for
    one row's height (~30px) at a time -- a kernel sized off the full page
    height demands more contiguous ink than a single row provides and erases
    the (perfectly real) rule entirely. Callers who know the row height should
    pass a kernel sized against *that* instead.
    """
    bw = cv2.threshold(gray, 0, 255,
                       cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    h, w = gray.shape

    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w // 15), 1))
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, h_kernel, iterations=1)

    if v_kernel_len is None:
        v_kernel_len = max(20, h // 15)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))
    vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN, v_kernel, iterations=1)
    return horiz, vert


def _cluster(positions: List[int], min_gap: int) -> List[int]:
    """Merge positions closer than min_gap; return the mean of each cluster."""
    if not positions:
        return []
    positions = sorted(positions)
    clusters = [[positions[0]]]
    for p in positions[1:]:
        if p - clusters[-1][-1] <= min_gap:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    return [int(round(sum(c) / len(c))) for c in clusters]


def _line_coords(line_img: np.ndarray, axis: int, min_frac: float) -> List[int]:
    """
    Positions (indices) where a ruled line runs along `axis`.
    axis=1 -> horizontal lines (project onto rows / y).
    axis=0 -> vertical lines   (project onto cols / x).
    """
    proj = line_img.sum(axis=axis) / 255.0
    length = line_img.shape[axis]
    threshold = min_frac * length
    hits = [int(i) for i, v in enumerate(proj) if v >= threshold]
    gap = max(6, int(0.02 * length))
    return _cluster(hits, gap)


def _measure_step(lines: List[int], expected_step: float, tol_frac: float = 0.3) -> float:
    """
    Median spacing between consecutive detected lines close to
    `expected_step`, falling back to `expected_step` itself when there isn't
    enough signal to measure it. Member 1's homography rectifies each photo
    individually and isn't pixel-perfect in scale, so the true on-page row
    pitch can drift a few percent from the template's row height sheet to
    sheet. Fitting a grid with the *template's* fixed step compounds that
    drift over 7 rows enough to anchor a whole row off; measuring the pitch
    from the sheet's own lines keeps the fit locked to what's actually there.
    """
    lines = sorted(set(lines))
    diffs = [b - a for a, b in zip(lines, lines[1:])]
    good = [d for d in diffs
            if (1 - tol_frac) * expected_step <= d <= (1 + tol_frac) * expected_step]
    if not good:
        return expected_step
    return float(np.median(good))


def _fit_grid(lines: List[int], step: float, n_points: int, tol: int,
              prior: float = None) -> List[float]:
    """
    Fit an evenly-spaced n_points grid (fixed spacing `step`) against noisy,
    possibly-incomplete `lines` -- a lightweight Hough-style vote: every
    detected line is tried as each possible grid position, and the candidate
    origin whose predicted points land closest to the most *other* detected
    lines wins. This recovers the full row grid even when a couple of rules
    (typically the outermost table border) are too faint to clear the
    intensity threshold on their own, as long as enough interior rules are
    intact to fix the pitch. `step` should be measured from the sheet itself
    (see _measure_step) rather than taken from the template.
    """
    lines = sorted(set(lines))
    if len(lines) < 3:
        return None

    best_support, best_origin = -1, None
    for anchor in lines:
        for k in range(n_points):
            origin = anchor - k * step
            support = sum(
                1 for k2 in range(n_points)
                if any(abs(l - (origin + k2 * step)) <= tol for l in lines)
            )
            better = support > best_support or (
                support == best_support and prior is not None
                and best_origin is not None
                and abs(origin - prior) < abs(best_origin - prior)
            )
            if better:
                best_support, best_origin = support, origin

    if best_support < max(3, n_points // 2):
        return None

    grid = [best_origin + k * step for k in range(n_points)]
    snapped = []
    for g in grid:
        nearest = min(lines, key=lambda l: abs(l - g))
        snapped.append(float(nearest) if abs(nearest - g) <= tol else g)
    return snapped


# --------------------------------------------------------------------------- #
# Grid -> signature cells
# --------------------------------------------------------------------------- #
def _strongest_near(profile: np.ndarray, expected: float, search: int,
                     min_strength: float):
    """Index of the strongest column/row in `profile` within `search` px of
    `expected`, or None if nothing there clears `min_strength`."""
    lo = max(0, int(expected - search))
    hi = min(len(profile), int(expected + search))
    window = profile[lo:hi]
    if window.size == 0 or window.max() < min_strength:
        return None
    return lo + int(window.argmax())


def _detect_column_bounds(aligned_bgr: np.ndarray):
    """
    (x0, x1) of the signature column's left/right rules, each independently
    Optional[int] -- None means that particular edge wasn't found near its
    expected position. Split out from detect_signature_cells so crop_all can
    survey every sheet's column width before deciding how to fill in sheets
    that only find one edge (see crop_all).
    """
    gray = io_utils.to_gray(aligned_bgr)
    h, w = gray.shape
    top = geometry.TABLE_TOP_FY * config.TEMPLATE_H
    bot = geometry.TABLE_BOTTOM_FY * config.TEMPLATE_H
    band_top, band_bot = max(0, int(top - 40)), min(h, int(bot + 40))
    row_h = (bot - top) / geometry.N_ROWS
    v_kernel_len = max(8, int(0.6 * row_h))
    _, vert = _binary_lines(gray, v_kernel_len=v_kernel_len)
    vert_band = vert[band_top:band_bot, :]
    v_profile = vert_band.sum(axis=0) / 255.0 / max(1, vert_band.shape[0])

    exp_x0 = geometry.COL_FX[geometry.SIGNATURE_COL] * config.TEMPLATE_W
    exp_x1 = geometry.COL_FX[geometry.SIGNATURE_COL + 1] * config.TEMPLATE_W
    # Wide enough to tolerate a real sheet's local scale drift (a phone-photo
    # homography is rectified per photo and isn't uniformly accurate -- one
    # test sheet's true column border sits 54px from the template position)
    # while staying far short of the ~280px to the nearest interior column
    # divider, so a wider window doesn't risk latching onto the wrong column.
    search = max(40, int(0.07 * config.TEMPLATE_W))
    min_strength = 0.25
    x0 = _strongest_near(v_profile, exp_x0, search, min_strength)
    x1 = _strongest_near(v_profile, exp_x1, search, min_strength)
    return x0, x1


def detect_signature_cells(aligned_bgr: np.ndarray, width_hint: float = None):
    """
    Return ({row: (x0, y0, x1, y1)}, source) for the six signature cells.
    `source` is one of "grid-detection" (both axes detected), "partial-grid"
    (only rows or only columns detected, the other axis used the template),
    or "template-fallback" (neither axis could be detected).

    Rows: horizontal rules are detected globally then fit to an evenly-spaced
    grid (see _fit_grid) so a faint or missing outer border doesn't sink the
    whole sheet as long as enough interior dividers are intact.

    Signature column: after warping+resampling a photographed sheet, faint or
    partially-antialiased vertical rules are common, and blindly picking "the
    two right-most detected vertical lines" can silently latch onto the wrong
    column pair (e.g. an interior divider) when the true column border is too
    weak to pass a flat threshold. Instead we search a small jitter window
    around each *expected* column-boundary position (from the template
    geometry) and take the strongest vertical line found there (see
    _detect_column_bounds). If only one border is found, the other is derived
    from `width_hint` if the caller supplied one (crop_all measures this
    across the batch -- see there for why the template's own column width
    turned out not to be trustworthy), else from the template's column width.

    Rows and columns are detected independently and each axis falls back to
    the template on its own: a sheet with a clean row grid but too faint a
    column border still benefits from the detected rows, rather than losing
    them by collapsing to the fully-fixed template rectangle.
    """
    gray = io_utils.to_gray(aligned_bgr)
    h, w = gray.shape

    # Restrict to the main-table band using the template as a prior.
    top = geometry.TABLE_TOP_FY * config.TEMPLATE_H
    bot = geometry.TABLE_BOTTOM_FY * config.TEMPLATE_H
    band_top = max(0, int(top - 40))
    band_bot = min(h, int(bot + 40))

    # Column rules are only continuous for one row's height at a time -- size
    # the vertical kernel off that instead of the full page (see _binary_lines).
    row_h = (bot - top) / geometry.N_ROWS
    v_kernel_len = max(8, int(0.6 * row_h))
    horiz, _ = _binary_lines(gray, v_kernel_len=v_kernel_len)

    # --- rows -------------------------------------------------------------
    # Horizontal rules span most of the table width when fully intact, but a
    # lenient threshold is used here because _fit_grid's voting rejects the
    # noise that a low threshold lets through far better than a high
    # threshold survives a partially-faint rule.
    y_lines = _line_coords(horiz, axis=1, min_frac=0.30)
    y_lines = [y for y in y_lines if band_top <= y <= band_bot]

    # Need 8 boundaries (header top + 7 row-bottoms) -> 7 row bands. The step
    # is measured off this sheet's own lines (see _measure_step) rather than
    # trusted from the template, so a per-sheet scale error can't accumulate
    # into an off-by-one-row grid.
    measured_row_h = _measure_step(y_lines, row_h)
    tol = max(6, int(0.25 * measured_row_h))
    y_grid = _fit_grid(y_lines, step=measured_row_h, n_points=geometry.N_ROWS + 1,
                        tol=tol, prior=top)
    rows_detected = y_grid is not None
    if not rows_detected:
        template_bands = [geometry.signature_cells()[r] for r in range(1, 7)]
        student_bands = [(rect[1], rect[3]) for rect in template_bands]
    else:
        row_bands = list(zip(y_grid[:-1], y_grid[1:]))
        student_bands = row_bands[1:7]        # skip header row

    # --- signature column ---------------------------------------------------
    x0, x1 = _detect_column_bounds(aligned_bgr)
    cols_detected = x0 is not None or x1 is not None

    exp_x0 = geometry.COL_FX[geometry.SIGNATURE_COL] * config.TEMPLATE_W
    exp_x1 = geometry.COL_FX[geometry.SIGNATURE_COL + 1] * config.TEMPLATE_W
    width = width_hint if width_hint is not None else (exp_x1 - exp_x0)
    if x0 is None and x1 is None:
        # No vertical signal at all to anchor on -- pad the template rectangle
        # outward (rather than cropping to its exact edges) since every sheet
        # observed so far drifts from the template position by tens of
        # pixels; an exact-template crop reliably clips real ink at the edges
        # when there's nothing detected to correct for that drift.
        margin = max(40, int(0.07 * config.TEMPLATE_W)) // 2
        sig_x0, sig_x1 = exp_x0 - margin, exp_x1 + margin
    else:
        sig_x0 = x0 if x0 is not None else x1 - width
        sig_x1 = x1 if x1 is not None else x0 + width
    if sig_x1 <= sig_x0:
        return None, "template-fallback"

    if rows_detected and cols_detected:
        source = "grid-detection"
    elif rows_detected or cols_detected:
        source = "partial-grid"
    else:
        return None, "template-fallback"

    cells = {}
    for i, (y0, y1) in enumerate(student_bands, start=1):
        cells[i] = (int(sig_x0), int(y0), int(sig_x1), int(y1))
    return cells, source


def _pad(rect, dx, dy, w, h):
    x0, y0, x1, y1 = rect
    return (max(0, x0 + dx), max(0, y0 + dy),
            min(w, x1 - dx), min(h, y1 - dy))


def crop_signatures(aligned_bgr: np.ndarray, inset: int = 3,
                     width_hint: float = None) -> Dict[int, np.ndarray]:
    """
    Crop the six signature cells. Uses detected grid lines when possible,
    otherwise the exact template rectangles. `width_hint`: see crop_all.
    """
    h, w = aligned_bgr.shape[:2]
    cells, source = detect_signature_cells(aligned_bgr, width_hint=width_hint)
    if cells is None:
        cells = geometry.signature_cells()

    crops = {}
    for row, rect in cells.items():
        x0, y0, x1, y1 = _pad(rect, inset, inset, w, h)
        if x1 > x0 and y1 > y0:
            crops[row] = aligned_bgr[y0:y1, x0:x1].copy()
    crops["_source"] = source            # small annotation for debugging
    return crops


def crop_file(aligned_path, width_hint: float = None) -> Dict[int, np.ndarray]:
    return crop_signatures(io_utils.load_bgr(aligned_path), width_hint=width_hint)


_SOURCE_COLOURS = {
    "grid-detection": (0, 180, 0),
    "partial-grid": (0, 165, 255),
    "template-fallback": (0, 0, 255),
}


def draw_debug(aligned_bgr: np.ndarray, width_hint: float = None) -> np.ndarray:
    vis = aligned_bgr.copy()
    cells, source = detect_signature_cells(aligned_bgr, width_hint=width_hint)
    if cells is None:
        cells, source = geometry.signature_cells(), "template-fallback"
    colour, label = _SOURCE_COLOURS[source], source
    for row, (x0, y0, x1, y1) in cells.items():
        cv2.rectangle(vis, (x0, y0), (x1, y1), colour, 2)
        cv2.putText(vis, f"{row}", (x0 - 22, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
    cv2.putText(vis, f"crop source: {label}", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, colour, 2)
    return vis


def crop_all():
    """Crop signatures from every aligned sheet in data/output/aligned/."""
    aligned_dir = config.OUTPUT_DIR / "aligned"
    sheets = sorted(p for p in aligned_dir.glob("*")
                     if p.suffix.lower() in {".png", ".jpg", ".jpeg"}) \
             if aligned_dir.exists() else []
    if not sheets:
        print("No aligned sheets. Run: python src/m1_alignment.py first.")
        return
    crops_root = config.OUTPUT_DIR / "crops"
    dbg_dir = config.OUTPUT_DIR / "crop_debug"
    crops_root.mkdir(parents=True, exist_ok=True)
    dbg_dir.mkdir(parents=True, exist_ok=True)

    aligned_imgs = {sheet: io_utils.load_bgr(sheet) for sheet in sheets}

    # The signature column's *width* is a physical property of the printed
    # sheet, constant across every session -- but the template's own
    # measurement of it (geometry.COL_FX) turns out not to match these real
    # photos (sheets where both edges are independently detected show a
    # column ~60-70px wider than the template assumes). So rather than trust
    # the template width when only one edge is found on a given sheet, learn
    # the true width from whichever sheets in this batch DID detect both
    # edges, and use that for the rest.
    widths = []
    for sheet, aligned in aligned_imgs.items():
        x0, x1 = _detect_column_bounds(aligned)
        if x0 is not None and x1 is not None:
            widths.append(x1 - x0)
    width_hint = float(np.median(widths)) if widths else None
    if width_hint is not None:
        print(f"[M2] signature column width learned from batch: {width_hint:.0f}px")

    for sheet, aligned in aligned_imgs.items():
        crops = crop_signatures(aligned, width_hint=width_hint)
        source = crops.pop("_source", "?")
        sheet_dir = crops_root / sheet.stem
        sheet_dir.mkdir(parents=True, exist_ok=True)
        for row, img in crops.items():
            io_utils.save_bgr(sheet_dir / f"row_{row}.png", img)
        io_utils.save_bgr(dbg_dir / sheet.name, draw_debug(aligned, width_hint=width_hint))
        print(f"[M2] {sheet.name:28s} -> {len(crops)} cells ({source})")
    print(f"[M2] crops -> {crops_root}")


if __name__ == "__main__":
    crop_all()