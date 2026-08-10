"""
src/m8_preview.py   (Member 8 - Image Processing UI)
======================================================
Live OpenCV window that steps through the image-processing pipeline for a
signature cell in real time: Original crop -> Grayscale -> Otsu
binarization -> Morphology. Reuses Member 3's preprocess(), whose "stages"
list exists specifically for this (see its docstring).

Usage
-----
    python src/m8_preview.py                    cycles every signed cell,
                                                  every sheet
    python src/m8_preview.py 001                 one student, every sheet
    python src/m8_preview.py 001 2019-05-31       one specific cell

Controls: any key advances to the next stage immediately; 'q' quits.
Each stage auto-advances after STAGE_DELAY_MS if no key is pressed.

Public API
----------
    preview_crop(crop_bgr, title, delay_ms) -> bool   (False = user quit)
    run_live_preview(student_key=None, date=None, delay_ms=...)
"""

import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(file_)))
for _p in (_ROOT, os.path.join(_ROOT, "src", "common")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config          # noqa: E402
import io_utils        # noqa: E402
import m3_preprocess   # noqa: E402
import m5_mapping      # noqa: E402

WINDOW = "Member 8 - Live Preprocessing Preview"
STAGE_DELAY_MS = 900
SCALE = 4   # signature crops are tiny (~30x150px) -- scale up for visibility


def _labelled_frame(img: np.ndarray, text: str) -> np.ndarray:
    """Scale a stage image up and stamp a label bar above it."""
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    h, w = img.shape[:2]
    big = cv2.resize(img, (w * SCALE, h * SCALE), interpolation=cv2.INTER_NEAREST)
    bar = np.zeros((36, big.shape[1], 3), dtype=np.uint8)
    cv2.putText(bar, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                (255, 255, 255), 2, cv2.LINE_AA)
    return np.vstack([bar, big])


def preview_crop(crop_bgr: np.ndarray, title: str, delay_ms: int = STAGE_DELAY_MS) -> bool:
    """
    Cycle Original -> Grayscale -> Otsu -> Morphology for one crop in the
    live window. Returns False if the user pressed 'q' (caller should stop
    the whole run), True otherwise.
    """
    stages = m3_preprocess.preprocess(crop_bgr)
    frames = [("Original", crop_bgr)] + stages["stages"]
    for name, img in frames:
        cv2.imshow(WINDOW, _labelled_frame(img, f"{title}  |  {name}"))
        key = cv2.waitKey(delay_ms) & 0xFF
        if key == ord("q"):
            return False
    return True


def run_live_preview(student_key: str = None, date: str = None,
                      delay_ms: int = STAGE_DELAY_MS):
    """Walk every signed (student, session) cell -- or a filtered subset --
    showing its processing stages live. Skips sessions Member 2 hasn't
    cropped yet and cells Member 4 found blank (nothing to preprocess)."""
    _, students, sessions = m5_mapping.load_info()

    if student_key:
        target = m5_mapping.find_student(student_key)
        if target is None:
            print(f"[M8] No student matches '{student_key}'")
            return
        students = [target]
    if date:
        sessions = [s for s in sessions if s["date"] == date]
        if not sessions:
            print(f"[M8] No session on '{date}'")
            return

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    try:
        for student in sorted(students, key=lambda s: s["id"]):
            for sess in sorted(sessions, key=lambda s: s["date"]):
                present, _, reason = m5_mapping.session_status(student, sess)
                if present is None:
                    print(f"[M8] {student['name']} / {sess['date']}: "
                          f"skipped ({reason}, not yet cropped)")
                    continue
                if not present:
                    print(f"[M8] {student['name']} / {sess['date']}: "
                          f"skipped (blank cell, nothing to preprocess)")
                    continue

                crop_path = (config.OUTPUT_DIR / "crops" / f"sheet_{sess['date']}"
                             / f"row_{student['row']}.png")
                crop = io_utils.load_bgr(crop_path)
                title = f"{student['name']} - {sess['date']}"
                print(f"[M8] previewing {title}")
                if not preview_crop(crop, title, delay_ms):
                    print("[M8] stopped by user")
                    return
    finally:
        cv2.destroyAllWindows()


if _name_ == "_main_":
    _key = sys.argv[1] if len(sys.argv) > 1 else None
    _date = sys.argv[2] if len(sys.argv) > 2 else None
    run_live_preview(_key, _date)
