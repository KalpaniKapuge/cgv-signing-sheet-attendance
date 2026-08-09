"""
src/m7_investigate.py   (Member 7 - Image Processing / Investigate)
=====================================================================
Forgery check: compares a student's signature on a given session against
their "genuine" reference template using the Structural Similarity Index
(SSIM), flagging low-similarity matches as possible forgeries.

Genuine template
----------------
data/genuine_signatures/<indexNo>.png is empty in this project -- no
separate enrollment photos exist, since these are real photographed sheets
rather than the synthetic generator's output (which would have rendered one
reference per student). Bootstrapped instead from each student's EARLIEST
signed session (their first Present row, via Members 4/5), saved once into
data/genuine_signatures/ and reused on every later run -- an "enrolled"
reference, the same fallback a real system would use if no separate
enrollment record exists: the first on-file signature becomes the baseline
everything else is checked against.

Technique
---------
SSIM (skimage.metrics.structural_similarity) on the two crops, first
Otsu-binarized (Member 3's binarize(), which cleans stroke shape via
morphology) and resized to a common canonical size -- so the score reflects
stroke *shape*, not incidental scale/lighting/paper-colour differences
between the crops (which come from independently grid-detected cells on
different photos, so are rarely pixel-identical in size even for the same
student). Score >= config.SSIM_MATCH_THRESHOLD -> genuine; below -> flagged
as a possible forgery.

Known limitation -- read before trusting a "possible-forgery" verdict
-----------------------------------------------------------------------
This scores *consistency with the student's own earlier signature*, not
true forgery in the legal sense -- with no independently-collected
enrollment sample (every real photo in this project is a genuine signature,
never an actual forgery), that's the best available ground truth here.

More importantly, the technique's real-world separation was measured, not
assumed: every (student, later-session) pair was scored against that
student's own baseline (24 genuine-variation comparisons) and against every
OTHER student's baseline (30 different-signer comparisons). The best
achievable single threshold split them with only ~65% accuracy (vs. 56%
from guessing "genuine" every time) -- tight-cropping to the ink's own
bounding box first, Hu-moment shape matching (cv2.matchShapes, translation/
scale/rotation-invariant by construction), and ORB feature matching were
all tried too and did no better (ORB found too few keypoints on thin binary
strokes to match at all). With only one bootstrapped baseline per student
and real handwriting's natural session-to-session variation running about
as large as the gap between two different people's signatures at this
sample size, no threshold on this signal reliably separates the two.
Ship this as a demonstration of the correct mechanism (compare, score,
flag), not as a trustworthy forgery detector -- config.SSIM_MATCH_THRESHOLD
documents the calibration in full.

Public API
----------
    ensure_genuine_template(student) -> (Path, date) | (None, None)
    compare_signature(crop_bgr, genuine_bgr) -> float          # SSIM, 0..1
    investigate_student(key)          -> dict(student, template_path,
                                               baseline_date, rows=[...])
"""

import os
import sys
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "src", "common")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config          # noqa: E402
import io_utils        # noqa: E402
import m3_preprocess   # noqa: E402
import m5_mapping      # noqa: E402

_COMPARE_SIZE = (220, 70)   # (w, h) canonical size for SSIM comparison


def _prep_for_compare(crop_bgr: np.ndarray) -> np.ndarray:
    """Binary stroke silhouette, normalized to a fixed size."""
    binary = m3_preprocess.binarize(crop_bgr)
    return cv2.resize(binary, _COMPARE_SIZE, interpolation=cv2.INTER_AREA)


def compare_signature(crop_bgr: np.ndarray, genuine_bgr: np.ndarray) -> float:
    a = _prep_for_compare(crop_bgr)
    b = _prep_for_compare(genuine_bgr)
    return float(ssim(a, b, data_range=255))


def _earliest_signed_date(student: Dict) -> Optional[str]:
    """The date used to bootstrap this student's genuine template -- computed
    fresh every call (deterministic: earliest session Member 4 found a
    signature) rather than read back from ensure_genuine_template, so it's
    still known even on a run where the template file already existed."""
    _, _, sessions = m5_mapping.load_info()
    for sess in sorted(sessions, key=lambda s: s["date"]):
        present, _, _ = m5_mapping.session_status(student, sess)
        if present:
            return sess["date"]
    return None


def ensure_genuine_template(student: Dict) -> Tuple[Optional[str], Optional[str]]:
    """
    (template_path, source_date). Bootstraps data/genuine_signatures/
    <indexNo>.png from the earliest session where Member 4 found a
    signature if it doesn't exist yet; reuses it as-is otherwise. Returns
    (None, None) if the student has no signed session at all.
    """
    out = config.GENUINE_SIG_DIR / f"{student['indexNo']}.png"
    source_date = _earliest_signed_date(student)
    if out.exists():
        return str(out), source_date
    if source_date is None:
        return None, None

    crop_path = (config.OUTPUT_DIR / "crops" / f"sheet_{source_date}"
                 / f"row_{student['row']}.png")
    io_utils.save_bgr(out, io_utils.load_bgr(crop_path))
    return str(out), source_date


def investigate_student(key: str) -> Dict:
    student = m5_mapping.find_student(key)
    if student is None:
        raise ValueError(f"No student matches '{key}'")

    template_path, baseline_date = ensure_genuine_template(student)
    if template_path is None:
        raise ValueError(f"{student['name']} has no signed session yet -- "
                          f"nothing available to enrol as a genuine template")
    genuine = io_utils.load_bgr(template_path)

    _, _, sessions = m5_mapping.load_info()
    rows = []
    for sess in sorted(sessions, key=lambda s: s["date"]):
        present, ink_colour, reason = m5_mapping.session_status(student, sess)
        if present is None:
            rows.append({"date": sess["date"], "score": None, "status": "not-cropped"})
            continue
        if not present:
            rows.append({"date": sess["date"], "score": None, "status": "absent"})
            continue

        crop_path = (config.OUTPUT_DIR / "crops" / f"sheet_{sess['date']}"
                     / f"row_{student['row']}.png")
        crop = io_utils.load_bgr(crop_path)
        score = compare_signature(crop, genuine)
        if sess["date"] == baseline_date:
            status = "baseline"
        else:
            status = "genuine" if score >= config.SSIM_MATCH_THRESHOLD else "possible-forgery"
        rows.append({"date": sess["date"], "score": score, "status": status})

    return {"student": student, "template_path": template_path,
            "baseline_date": baseline_date, "rows": rows}


# --------------------------------------------------------------------------- #
# Batch demo / testing
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    _, students, _ = m5_mapping.load_info()
    for student in sorted(students, key=lambda s: s["id"]):
        try:
            result = investigate_student(student["id"])
        except ValueError as e:
            print(f"[M7] {student['id']} {student['name']:32s} {e}")
            continue
        cells = []
        for r in result["rows"]:
            if r["score"] is None:
                cells.append(f"{r['date']}:{r['status']}")
            else:
                cells.append(f"{r['date']}:{r['score']:.2f}({r['status']})")
        print(f"[M7] {student['id']} {student['name']:32s} {'  '.join(cells)}")