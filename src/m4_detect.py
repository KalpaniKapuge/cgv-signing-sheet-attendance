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


