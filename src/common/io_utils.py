"""
src/common/io_utils.py
======================
Small shared helpers for reading and writing images and for locating input
sheets. Kept deliberately thin so member modules stay focused on their own
algorithm rather than on file plumbing.
"""

from pathlib import Path
from typing import List

import cv2
import numpy as np

import config


def load_bgr(path) -> np.ndarray:
    """Read an image as an OpenCV BGR array, raising a clear error if missing."""
    path = Path(path)
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return img


def save_bgr(path, img: np.ndarray) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)
    return path


def list_input_sheets(prefer_raw: bool = True) -> List[Path]:
    """
    Return the sheets to process. Uses real photos in data/raw if any exist,
    otherwise falls back to the synthetic set in data/generated.
    """
    raw = sorted(p for p in config.RAW_DIR.glob("*")
                 if p.suffix.lower() in {".png", ".jpg", ".jpeg"})
    if prefer_raw and raw:
        return raw
    return sorted(config.GENERATED_DIR.glob("sheet_*.png"))


def to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
