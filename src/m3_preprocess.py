"""
src/m3_preprocess.py   (Member 3 - Image Processing)
====================================================
Refines a cropped signature cell so later stages get a clean signal, and
classifies the pen ink colour (Blue / Black / Green).

Preprocessing pipeline (per crop)
---------------------------------
1. Grayscale.
2. Otsu binarization (inverse): ink becomes white (255) on a black (0)
   background - the natural form for pixel counting and morphology.
3. Morphological opening (remove speckle noise) then closing (bridge small
   gaps in strokes), with a small kernel so the signature shape is preserved.

The intermediate stages are returned as a dict so Member 8's OpenCV live
preview can show Grayscale -> Otsu -> Morphology.

Ink-colour classification
-------------------------
Convert the crop to HSV, build an "ink" mask (everything not near-white), and
count how many ink pixels fall into each colour's HSV band
(config.INK_COLOUR_HSV_RANGES). The band with the most pixels wins; an empty
cell returns None.

Public API
----------
    preprocess(crop_bgr)          -> dict(gray, otsu, morph, stages_list)
    binarize(crop_bgr)            -> clean binary (ink=255)
    classify_ink_colour(crop_bgr) -> "Blue" | "Black" | "Green" | None
    process(crop_bgr)             -> (binary, colour)
"""

import os
import sys
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "src", "common")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config          # noqa: E402
import io_utils        # noqa: E402


# --------------------------------------------------------------------------- #
# Preprocessing
# --------------------------------------------------------------------------- #
def preprocess(crop_bgr: np.ndarray) -> Dict[str, np.ndarray]:
    """Return every intermediate stage keyed by name (for previews + reuse)."""
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)

    # Otsu, inverse -> ink = 255 (foreground), paper = 0.
    _, otsu = cv2.threshold(gray, 0, 255,
                            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Opening and closing serve different jobs and need different-sized
    # kernels: these crops are small (~25x150px) and a real pen stroke is
    # often only 1-2px wide there, so a 3x3 opening (this module's original
    # kernel for both steps) erodes thin strokes away before dilation can
    # restore them -- verified on a real crop, it fragmented a signature's
    # thin trailing flourish into disconnected speckles. A 2x2 opening still
    # removes isolated noise pixels without eating a 2px-wide stroke, while
    # closing can stay at 3x3 since dilating-then-eroding never deletes
    # existing ink, only bridges small gaps.
    open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    opened = cv2.morphologyEx(otsu, cv2.MORPH_OPEN, open_kernel, iterations=1)
    morph = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, close_kernel, iterations=1)

    return {"gray": gray, "otsu": otsu, "morph": morph,
            "stages": [("Grayscale", gray), ("Otsu", otsu), ("Morphology", morph)]}


def binarize(crop_bgr: np.ndarray) -> np.ndarray:
    """Clean binary image where ink = 255."""
    return preprocess(crop_bgr)["morph"]


# --------------------------------------------------------------------------- #
# Ink colour classification
# --------------------------------------------------------------------------- #
def ink_mask(crop_bgr: np.ndarray) -> np.ndarray:
    """
    Boolean mask of non-paper (ink) pixels, via a fixed brightness cutoff.

    Deliberately NOT Otsu: Otsu always finds *a* split, even across an
    almost-uniform blank cell with no real bimodal structure -- on a
    genuinely blank crop from this project's photos it classified 51% of the
    (paper-only, uneven-lighting) pixels as "ink". binarize()'s Otsu mask is
    the right tool once you know there's a stroke to clean up and shape, but
    the wrong one for deciding *whether* a cell has ink at all. This fixed
    threshold is shared by Member 4's presence check so the two decisions
    ("is this blank" / "is this signed") never disagree on the same cell.
    """
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    return gray < 200


def ink_ratio(crop_bgr: np.ndarray) -> float:
    mask = ink_mask(crop_bgr)
    return float(mask.sum()) / mask.size


def classify_ink_colour(crop_bgr: np.ndarray) -> Optional[str]:
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    ink = ink_mask(crop_bgr)
    # Ratio, not a flat pixel count: crop cells vary in size (grid-detected
    # cells differ sheet to sheet), and a fixed 20px cutoff let a few dozen
    # stray pixels -- grid-line bleed from a neighbouring row, JPEG noise --
    # through as "signed" on cells that are otherwise blank. Sharing
    # Member 4's own signed/absent threshold keeps the two decisions
    # consistent: a cell too faint to count as signed shouldn't be assigned
    # an ink colour either.
    if ink_ratio(crop_bgr) < config.INK_PIXEL_RATIO_THRESHOLD:
        return None

    counts = {}
    for name, (lo, hi) in config.INK_COLOUR_HSV_RANGES.items():
        band = cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8)) > 0
        counts[name] = int(np.logical_and(band, ink).sum())

    if sum(counts.values()) == 0:
        return None
    return max(counts, key=counts.get)


def process(crop_bgr: np.ndarray) -> Tuple[np.ndarray, Optional[str]]:
    """Convenience: (clean binary, ink colour)."""
    return binarize(crop_bgr), classify_ink_colour(crop_bgr)


# --------------------------------------------------------------------------- #
# Batch demo / testing
# --------------------------------------------------------------------------- #
def process_all():
    """Binarize every crop and report the detected ink colour per cell."""
    crops_root = config.OUTPUT_DIR / "crops"
    if not crops_root.exists():
        print("No crops. Run: python src/m2_crop.py first.")
        return
    bin_root = config.OUTPUT_DIR / "binarized"
    bin_root.mkdir(parents=True, exist_ok=True)

    for sheet_dir in sorted(p for p in crops_root.iterdir() if p.is_dir()):
        out_dir = bin_root / sheet_dir.name
        out_dir.mkdir(parents=True, exist_ok=True)
        colours = []
        for row in range(1, 7):
            f = sheet_dir / f"row_{row}.png"
            if not f.exists():
                continue
            crop = io_utils.load_bgr(f)
            binary, colour = process(crop)
            io_utils.save_bgr(out_dir / f"row_{row}.png", binary)
            colours.append(f"{row}:{colour or '-'}")
        print(f"[M3] {sheet_dir.name:24s} {'  '.join(colours)}")
    print(f"[M3] binarized cells -> {bin_root}")


if __name__ == "__main__":
    process_all()