"""Planted failures: real clean renders, deliberately damaged. Each one must be caught."""
from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image

from .regions import Regions


def chair_painted_out(src, res, reg: Regions):
    """Paint every wheel out with the surrounding background."""
    mask = cv2.dilate(reg.wheel_mask.astype(np.uint8), np.ones((15, 15), np.uint8))
    return cv2.inpaint(res, mask, 9, cv2.INPAINT_TELEA)


def wheels_covered(src, res, reg: Regions):
    """Extend the garment over the wheels, using its own colour, as a long hem would."""
    delta = np.abs(res.astype(int) - src.astype(int)).sum(axis=2) > 40
    colour = np.median(res[delta], axis=0).astype(np.uint8)
    out = res.copy()
    out[reg.wheel_mask] = colour
    return out


def garment_unchanged(src, res, reg: Regions):
    """The service handed the photo back untouched, after an ordinary JPEG round trip."""
    buf = io.BytesIO()
    Image.fromarray(src).save(buf, "JPEG", quality=90)
    return np.array(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"))


def face_altered(src, res, reg: Regions):
    """Blur the face past recognition."""
    x, y, w, h = reg.face
    out = res.copy()
    out[y:y + h, x:x + w] = cv2.GaussianBlur(out[y:y + h, x:x + w], (0, 0), 16)
    return out


def hand_altered(src, res, reg: Regions):
    """Scramble one hand, leaving the sleeve alone."""
    x0, y0, x1, y1 = reg.hands[0]
    out = res.copy()
    box = out[y0:y1, x0:x1]
    out[y0:y1, x0:x1] = cv2.GaussianBlur(np.flipud(box), (0, 0), 9)
    return out


# name -> (damage, check that must catch it, status it must reach)
PLANTS = {
    "chair_painted_out": (chair_painted_out, "chair", "fail"),
    "wheels_covered": (wheels_covered, "clearance", "fail"),
    "garment_unchanged": (garment_unchanged, "change", "fail"),
    "face_altered": (face_altered, "person", "fail"),
    "hand_altered": (hand_altered, "person", "fail"),
}
