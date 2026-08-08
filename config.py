"""
config.py
=========
Single source of truth for paths and tuning constants used across the whole
signature-attendance pipeline. Every member's module imports from here so that
nobody hard-codes a path or a magic number in two different places.
"""

from pathlib import Path

# --------------------------------------------------------------------------- #
# Project paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent

DATA_DIR        = ROOT / "data"
TEMPLATE_DIR    = DATA_DIR / "templates"
RAW_DIR         = DATA_DIR / "raw"                 # user's phone photos go here
GENERATED_DIR   = DATA_DIR / "generated"           # synthetic test sheets
GENUINE_SIG_DIR = DATA_DIR / "genuine_signatures"  # reference sigs (Member 7)
OUTPUT_DIR      = DATA_DIR / "output"              # crops, debug images, exports

TEMPLATE_IMAGE  = TEMPLATE_DIR / "sheet_template.png"
INFO_XML        = ROOT / "info.xml"
DATABASE_FILE   = DATA_DIR / "attendance.db"

# --------------------------------------------------------------------------- #
# Canonical template geometry
# --------------------------------------------------------------------------- #
# The aligned template is always rendered at this fixed resolution. Member 1
# warps every phone photo onto this exact canvas, so Member 2 can crop cells
# using fixed coordinates with confidence.
TEMPLATE_W = 1000
TEMPLATE_H = 1400

# --------------------------------------------------------------------------- #
# Member 4 - signature present/absent decision
# --------------------------------------------------------------------------- #
# A cropped, binarized signature cell is "signed" if the fraction of ink
# (non-white) pixels exceeds this threshold.
INK_PIXEL_RATIO_THRESHOLD = 0.012   # ~1.2% of the cell must be ink

# --------------------------------------------------------------------------- #
# Member 3 - ink colour classification (HSV ranges, OpenCV H in 0..179)
# --------------------------------------------------------------------------- #
INK_COLOUR_HSV_RANGES = {
    "Blue":  ((90, 60, 40),  (140, 255, 255)),
    "Green": ((40, 40, 40),  (89,  255, 255)),
    "Black": ((0,  0,  0),   (180, 255, 90)),   # low value = dark
}

# --------------------------------------------------------------------------- #
# Member 7 - forgery / similarity check
# --------------------------------------------------------------------------- #
# Empirically the best achievable single threshold on this project's real
# photos: computed SSIM for every (student, session) pair against that
# student's own baseline signature (24 genuine-variation comparisons) and
# against every other student's baseline (30 different-signer comparisons),
# then swept every threshold 0-1 for the best split. Best split: 0.61,
# 65% accuracy -- only modestly above chance (56% from guessing the majority
# class). See src/m7_investigate.py's module docstring for why: with one
# bootstrapped baseline per student and no true forged samples, natural
# session-to-session handwriting variation is roughly the same size as the
# gap between different people's signatures. Treat any single verdict from
# this threshold as indicative, not authoritative.
SSIM_MATCH_THRESHOLD = 0.61

# --------------------------------------------------------------------------- #
# Ensure runtime directories exist on import
# --------------------------------------------------------------------------- #
for _d in (TEMPLATE_DIR, RAW_DIR, GENERATED_DIR, GENUINE_SIG_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
