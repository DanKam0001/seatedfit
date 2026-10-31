"""Find the regions the render check looks at, from the source photo alone.

Sample models use regions marked by eye (assets/regions.json). Uploads get a
face, plus the wheels the shopper marks. find_wheels scored too poorly to trust
(proof_results/locator_eval.json), so with no marks the wheel checks on an upload
say "not measured" rather than guess.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

WORK = 1024
MARKS = Path(__file__).resolve().parents[1] / "assets" / "regions.json"
_FRONT = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_PROFILE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")

MIN_RIM_SUPPORT = 0.55


@dataclass
class Ellipse:
    cx: float
    cy: float
    a: float  # half-width
    b: float  # half-height
    kind: str = "wheel"  # "wheel" or "caster"

    def mask(self, shape) -> np.ndarray:
        m = np.zeros(shape[:2], np.uint8)
        cv2.ellipse(m, (round(self.cx), round(self.cy)), (round(self.a), round(self.b)), 0, 0, 360, 255, -1)
        return m > 0


@dataclass
class Regions:
    shape: tuple
    source: str  # "marked", "shopper" or "auto"
    face: tuple | None = None  # (x, y, w, h)
    wheels: list = field(default_factory=list)  # Ellipse
    footplates: list = field(default_factory=list)  # (x0, y0, x1, y1)
    hands: list = field(default_factory=list)  # (x0, y0, x1, y1)

    @property
    def wheel_mask(self) -> np.ndarray:
        m = np.zeros(self.shape[:2], bool)
        for w in self.wheels:
            m |= w.mask(self.shape)
        return m

    @property
    def chair_mask(self) -> np.ndarray:
        m = self.wheel_mask
        for x0, y0, x1, y1 in self.footplates:
            m[y0:y1, x0:x1] = True
        return m


def to_work(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    if max(h, w) == WORK:
        return rgb
    s = WORK / max(h, w)
    return cv2.resize(rgb, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)


def find_faces(rgb: np.ndarray) -> list:
    """Largest first. Only the upper 60% of the frame counts: a seated person's
    face is never down by the wheels, and spokes trip the cascade there."""
    gray = cv2.equalizeHist(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
    side = int(max(rgb.shape[:2]) * 0.05)
    found = list(_FRONT.detectMultiScale(gray, 1.1, 6, minSize=(side, side)))
    if not len(found):
        found = list(_PROFILE.detectMultiScale(gray, 1.1, 5, minSize=(side, side)))
    if not len(found):
        flipped = _PROFILE.detectMultiScale(cv2.flip(gray, 1), 1.1, 5, minSize=(side, side))
        found = [(rgb.shape[1] - x - w, y, w, h) for x, y, w, h in flipped]
    faces = [tuple(int(v) for v in f) for f in found if f[1] + f[3] / 2 < rgb.shape[0] * 0.6]
    return sorted(faces, key=lambda f: -f[2])


def rim_support(edges: np.ndarray, e: Ellipse, samples=72) -> float:
    """Share of the ellipse's outline that lies on a real edge in the photo."""
    near = cv2.dilate(edges, np.ones((5, 5), np.uint8)) > 0
    t = np.linspace(0, 2 * np.pi, samples, endpoint=False)
    xs = (e.cx + e.a * np.cos(t)).round().astype(int)
    ys = (e.cy + e.b * np.sin(t)).round().astype(int)
    inside = (xs >= 0) & (xs < edges.shape[1]) & (ys >= 0) & (ys < edges.shape[0])
    return float(near[ys[inside], xs[inside]].sum() / samples)


def mark_support(edges: np.ndarray, e: Ellipse, reach=12, step=6) -> float:
    """rim_support, forgiving a hand that lands a few pixels off the wheel."""
    return max(rim_support(edges, Ellipse(e.cx + dx, e.cy + dy, e.a, e.b, e.kind))
               for dx in range(-reach, reach + 1, step) for dy in range(-reach, reach + 1, step))


def _candidates(gray: np.ndarray) -> list:
    h, w = gray.shape
    out = []
    circles = cv2.HoughCircles(cv2.medianBlur(gray, 5), cv2.HOUGH_GRADIENT, dp=1.2, minDist=h * 0.06, param1=120,
                               param2=30, minRadius=int(h * 0.03), maxRadius=int(h * 0.25))
    if circles is not None:
        for cx, cy, r in circles[0]:
            out.append(Ellipse(float(cx), float(cy), float(r), float(r), "wheel" if r > h * 0.12 else "caster"))
    edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    for c in contours:
        if len(c) < 60:
            continue
        (cx, cy), (d1, d2), ang = cv2.fitEllipse(c)
        tilt = min(ang % 180, 180 - ang % 180)
        if tilt < 12 and d2 > h * 0.25 and d1 / d2 < 0.3:  # standing on edge: a big wheel seen from the front
            out.append(Ellipse(cx, cy, max(d1 / 2, 10), d2 / 2, "wheel"))
    return out


def find_wheels(rgb: np.ndarray) -> list:
    h = rgb.shape[0]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 50, 150)
    good = []
    for e in _candidates(gray):
        if e.cy < h * 0.5 or e.cy + e.b > h * 1.03:
            continue
        score = rim_support(edges, e)
        if score >= MIN_RIM_SUPPORT:
            good.append((score, e))
    kept: list[Ellipse] = []
    for _, e in sorted(good, key=lambda s: -s[0]):
        if not any(abs(e.cx - k.cx) < max(k.a, e.a) and abs(e.cy - k.cy) < max(k.b, e.b) for k in kept):
            kept.append(e)
    return kept


def locate_auto(rgb: np.ndarray) -> Regions:
    faces = find_faces(rgb)
    return Regions(rgb.shape, "auto", face=faces[0] if faces else None)


def locate_shopper(rgb: np.ndarray, marks: list) -> Regions:
    """Marks are fractions of the picture: centre x and y, full width w and height h."""
    h, w = rgb.shape[:2]
    wheels = [Ellipse(m["x"] * w, m["y"] * h, m["w"] * w / 2, m["h"] * h / 2, m["kind"]) for m in marks]
    faces = find_faces(rgb)
    return Regions(rgb.shape, "shopper", face=faces[0] if faces else None, wheels=wheels)


def locate_marked(model: str, rgb: np.ndarray) -> Regions:
    m = json.loads(MARKS.read_text(encoding="utf-8"))[model]
    wheels = [Ellipse(*w, "wheel") for w in m["wheels"]] + [Ellipse(*c, "caster") for c in m["casters"]]
    faces = find_faces(rgb)
    return Regions(rgb.shape, "marked", face=faces[0] if faces else None, wheels=wheels,
                   footplates=[tuple(b) for b in m["footplates"]], hands=[tuple(b) for b in m.get("hands", [])])
