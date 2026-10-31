"""Order garments by colour contrast against a skin tone.

This is arithmetic on two colours, CIEDE2000 colour difference, and nothing more.
It says how far apart two colours are, not what looks good on anyone.
"""
from __future__ import annotations

import io
import json
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image
from skimage.color import deltaE_ciede2000, rgb2lab

from .catalogue import GARMENTS, PROOF, garment_path, model_path
from .regions import find_faces, to_work

FACE_SHARE = 0.72  # YouCam asks for a face wider than 60% of the image
MIN_SIDE = 640


def hex_to_lab(hex_colour: str) -> np.ndarray:
    h = hex_colour.lstrip("#")
    rgb = np.array([[[int(h[i:i + 2], 16) for i in (0, 2, 4)]]], np.uint8)
    return rgb2lab(rgb)[0, 0]


def rgb_to_hex(rgb) -> str:
    return "#" + "".join(f"{int(round(v)):02x}" for v in rgb)


def face_crop(rgb: np.ndarray, face: tuple) -> bytes:
    """A square around the face alone, as a JPEG. The rest of the photo stays here."""
    x, y, w, h = face
    side = round(max(w, h) / FACE_SHARE)
    cx, cy = x + w / 2, y + h / 2
    x0 = int(np.clip(cx - side / 2, 0, max(0, rgb.shape[1] - side)))
    y0 = int(np.clip(cy - side / 2, 0, max(0, rgb.shape[0] - side)))
    crop = Image.fromarray(rgb[y0:y0 + side, x0:x0 + side])
    if crop.width < MIN_SIDE:
        crop = crop.resize((MIN_SIDE, MIN_SIDE), Image.LANCZOS)
    buf = io.BytesIO()
    crop.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def local_skin(rgb: np.ndarray, face: tuple) -> str:
    """The median colour of the middle of the face: a free reading from the pixels."""
    x, y, w, h = face
    patch = rgb[y + h // 4:y + 3 * h // 4, x + w // 4:x + 3 * w // 4].reshape(-1, 3)
    return rgb_to_hex(np.median(patch, axis=0))


@lru_cache(maxsize=None)
def garment_hex(garment: str) -> str:
    """The garment's main colour: the biggest colour group that isn't the white backdrop."""
    im = Image.open(garment_path(garment)).convert("RGB")
    im.thumbnail((256, 256))
    px = np.array(im)
    corners = np.vstack([px[:8, :8].reshape(-1, 3), px[-8:, -8:].reshape(-1, 3)])
    backdrop = np.median(corners, axis=0)
    # a white shirt on a white backdrop is still a garment, so only join-to-the-edge pixels are backdrop
    near = (np.abs(px.astype(int) - backdrop).max(axis=2) < 10).astype(np.uint8)
    _, labels = cv2.connectedComponents(near)
    edge = set(labels[0]) | set(labels[-1]) | set(labels[:, 0]) | set(labels[:, -1])
    outside = np.isin(labels, [v for v in edge if near[labels == v].any()])
    pts = px[~outside].astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5)
    cv2.setRNGSeed(7)
    _, lab, centres = cv2.kmeans(pts, 3, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    return rgb_to_hex(centres[np.bincount(lab.ravel(), minlength=3).argmax()])


def rank(skin_hex: str) -> list:
    """Every garment, highest colour difference first."""
    skin = hex_to_lab(skin_hex)
    out = []
    for g in GARMENTS:
        hex_ = garment_hex(g)
        out.append({"garment": g, "colour": hex_, "contrast": round(float(deltaE_ciede2000(skin, hex_to_lab(hex_))), 1)})
    return sorted(out, key=lambda r: -r["contrast"])


def _saved() -> dict:
    p = PROOF / "skin_tone.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


@lru_cache(maxsize=None)
def sample_reading(model: str) -> dict:
    """YouCam's measured colour if one is saved for this sample, otherwise the free reading."""
    saved = _saved().get(model)
    if saved:
        return {"skin": saved["skin_color"], "source": "youcam", "garments": rank(saved["skin_color"])}
    rgb = to_work(np.array(Image.open(model_path(model)).convert("RGB")))
    faces = find_faces(rgb)
    skin = local_skin(rgb, faces[0])
    return {"skin": skin, "source": "local", "garments": rank(skin)}
