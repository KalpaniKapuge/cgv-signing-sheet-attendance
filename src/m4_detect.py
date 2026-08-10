import os
import sys
from typing import Tuple

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "src", "common")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config          
import io_utils        
import m3_preprocess   


def detect_presence(crop_bgr: np.ndarray) -> Tuple[bool, str]:
    if m3_preprocess.ink_ratio(crop_bgr) < config.INK_PIXEL_RATIO_THRESHOLD:
        return False, "blank"
    return True, "signature"


def detect_file(crop_path) -> Tuple[bool, str]:
    return detect_presence(io_utils.load_bgr(crop_path))


def detect_all():
    crops_root = config.OUTPUT_DIR / "crops"
    if not crops_root.exists():
        print("No crops. Run: python src/m2_crop.py first.")
        return {}

    results = {}
    for sheet_dir in sorted(p for p in crops_root.iterdir() if p.is_dir()):
        rows = []
        for row in range(1, 7):
            f = sheet_dir / f"row_{row}.png"
            if not f.exists():
                continue
            present, reason = detect_file(f)
            results[(sheet_dir.name, row)] = (present, reason)
            mark = "P" if present else "A"
            rows.append(f"{row}:{mark}({reason})")
        print(f"[M4] {sheet_dir.name:24s} {'  '.join(rows)}")
    return results


if __name__ == "__main__":
    detect_all()
