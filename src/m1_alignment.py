"""
src/m1_alignment.py   (Member 1 - Image Processing)
===================================================
Detects the four corners of a smartphone-captured signing sheet, straightens
it, and warps it onto the fixed template canvas so that every downstream member
(Member 2 onward) can rely on signatures always being in the same place.

Technique
---------
1. Grayscale + Gaussian blur to suppress texture/noise.
2. Otsu threshold: the bright sheet separates from the darker desk background.
3. Morphological close so text inside the sheet does not fragment the blob.
4. Largest external contour = the sheet; approxPolyDP to a 4-point quad
   (falls back to minAreaRect if the polygon is not clean).
5. Order the corners (TL, TR, BR, BL) and getPerspectiveTransform onto the
   canonical template corners, then warpPerspective to TEMPLATE_W x TEMPLATE_H.

If no convincing quad is found (e.g. an already-flat scan that fills the frame),
the image is simply resized to the template - a safe identity-like fallback.

Public API
----------
    align_sheet(bgr)  -> (aligned_bgr, corners_or_None)
    align_file(path)  -> aligned_bgr
    align_all()       -> writes aligned sheets to data/output/aligned/
"""

import os
import sys

import cv2
import numpy as np

# --- bootstrap imports (works whether run directly or imported) -------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "src", "common")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config          # noqa: E402
import geometry        # noqa: E402
import io_utils        # noqa: E402


# --------------------------------------------------------------------------- #
# Corner geometry helpers
# --------------------------------------------------------------------------- #
def order_corners(pts: np.ndarray) -> np.ndarray:
    """
    Order four points as [top-left, top-right, bottom-right, bottom-left].
    TL has the smallest (x+y), BR the largest; TR the smallest (y-x), BL largest.
    """
    pts = np.array(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    diff = (pts[:, 1] - pts[:, 0])
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def _largest_quad(mask: np.ndarray, h: int, w: int):
    """Largest external contour of a binary mask, simplified to 4 points.
    Returns None if there's no contour or it's implausibly small/large to be
    the sheet (min-area cases are noise; near-100% usually means the mask
    merged the sheet with its background)."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea)
    area_frac = cv2.contourArea(c) / (h * w)
    if area_frac < 0.15 or area_frac > 0.985:
        return None
    peri = cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, 0.02 * peri, True)
    quad = approx.reshape(4, 2) if len(approx) == 4 else cv2.boxPoints(cv2.minAreaRect(c))
    return order_corners(quad)


def find_document_corners(bgr: np.ndarray):
    """Return the 4 ordered corners of the sheet, or None if not found.

    Tries two colour cues, since which one separates sheet from background
    depends on the shot:
      1. Saturation: works when the sheet (near-neutral white) sits against
         a warm-toned background (a desk/wall) -- typical of real phone
         photos, where the two surfaces can be similarly *bright* and a
         plain brightness split grabs the background too.
      2. Brightness (Otsu on grayscale): works when the sheet is simply
         brighter than its background -- typical of the synthetic test
         photos, which use a darker, low-saturation desk backdrop where the
         saturation cue is too weak to separate.
    Saturation is tried first; brightness is the fallback when it doesn't
    yield a plausible quad.
    """
    h, w = bgr.shape[:2]

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    sat = cv2.GaussianBlur(hsv[:, :, 1], (5, 5), 0)
    _, sat_mask = cv2.threshold(sat, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    quad = _largest_quad(sat_mask, h, w)
    if quad is not None:
        return quad

    gray = cv2.GaussianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    _, gray_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return _largest_quad(gray_mask, h, w)


# --------------------------------------------------------------------------- #
# Alignment
# --------------------------------------------------------------------------- #
def align_sheet(bgr: np.ndarray):
    """
    Warp a photo onto the canonical template canvas.
    Returns (aligned_bgr, corners) where corners is None if the fallback
    resize path was used.
    """
    corners = find_document_corners(bgr)
    W, H = config.TEMPLATE_W, config.TEMPLATE_H
    if corners is None:
        return cv2.resize(bgr, (W, H), interpolation=cv2.INTER_AREA), None

    dst = np.array(geometry.template_corners(), dtype=np.float32)
    M = cv2.getPerspectiveTransform(corners, dst)
    aligned = cv2.warpPerspective(bgr, M, (W, H), flags=cv2.INTER_LINEAR,
                                  borderValue=(255, 255, 255))
    aligned = deskew(aligned)
    return aligned, corners


def _residual_skew_deg(bgr: np.ndarray) -> float:
    """Median angle of long near-horizontal lines (table rulings). A perfect
    perspective warp would leave this at 0, but small corner-detection error
    still leaves a few degrees of rotation behind."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 30, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 720, threshold=150,
                             minLineLength=300, maxLineGap=20)
    if lines is None:
        return 0.0
    angles = []
    for x1, y1, x2, y2 in lines[:, 0]:
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        ang = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if length > 300 and abs(ang) < 15:
            angles.append(ang)
    return float(np.median(angles)) if angles else 0.0


def deskew(bgr: np.ndarray) -> np.ndarray:
    """Correct the small residual rotation left after the perspective warp,
    so the fixed cell coordinates in geometry.py line up across the whole
    width (error otherwise grows with distance from the rotation axis and is
    worst in the rightmost -- signature -- column)."""
    angle = _residual_skew_deg(bgr)
    if abs(angle) < 0.2 or abs(angle) > 10:   # too small to matter / not trustworthy
        return bgr
    h, w = bgr.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(bgr, M, (w, h), flags=cv2.INTER_LINEAR,
                          borderValue=(255, 255, 255))


def align_file(path) -> np.ndarray:
    aligned, _ = align_sheet(io_utils.load_bgr(path))
    return aligned


def draw_debug(bgr: np.ndarray, corners) -> np.ndarray:
    """Overlay the detected quad + corner labels for a visual sanity check."""
    vis = bgr.copy()
    if corners is None:
        cv2.putText(vis, "no quad -> resized", (30, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        return vis
    pts = corners.astype(int)
    cv2.polylines(vis, [pts.reshape(-1, 1, 2)], True, (0, 200, 0), 4)
    for i, (x, y) in enumerate(pts):
        cv2.circle(vis, (x, y), 12, (0, 0, 255), -1)
        cv2.putText(vis, ["TL", "TR", "BR", "BL"][i], (x + 15, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 3)
    return vis


def align_all(save_debug: bool = True):
    """Align every input sheet and write results to data/output/aligned/."""
    out_dir = config.OUTPUT_DIR / "aligned"
    dbg_dir = config.OUTPUT_DIR / "align_debug"
    out_dir.mkdir(parents=True, exist_ok=True)
    if save_debug:
        dbg_dir.mkdir(parents=True, exist_ok=True)

    sheets = io_utils.list_input_sheets()
    if not sheets:
        print("No input sheets. Run tools/generate_synthetic_sheets.py first.")
        return []

    results = []
    for path in sheets:
        bgr = io_utils.load_bgr(path)
        aligned, corners = align_sheet(bgr)
        io_utils.save_bgr(out_dir / path.name, aligned)
        if save_debug:
            io_utils.save_bgr(dbg_dir / path.name, draw_debug(bgr, corners))
        status = "warped" if corners is not None else "resized(fallback)"
        print(f"[M1] {path.name:28s} -> aligned ({status})")
        results.append(out_dir / path.name)
    print(f"[M1] {len(results)} sheets aligned -> {out_dir}")
    return results


if __name__ == "__main__":
    align_all()