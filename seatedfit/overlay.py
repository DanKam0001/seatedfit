"""Draw what the check found on top of the render."""
from __future__ import annotations

import cv2
import numpy as np

from .checks import Report
from .regions import Regions

RED = np.array([214, 26, 26], float)
OK = (255, 255, 255)
BAD = (214, 26, 26)


def draw(res_rgb: np.ndarray, regions: Regions, report: Report) -> np.ndarray:
    """A failed render becomes grey evidence with the problem in red, so nobody
    can mistake it for a try-on picture."""
    base = res_rgb
    if report.verdict == "fail":
        grey = cv2.cvtColor(res_rgb, cv2.COLOR_RGB2GRAY)
        base = np.dstack([grey] * 3)
    out = base.astype(float)
    hit = report.masks["covered"] & regions.wheel_mask
    out[hit] = out[hit] * 0.3 + RED * 0.7
    out = out.clip(0, 255).astype(np.uint8)
    for w in regions.wheels:
        m = w.mask(regions.shape)
        touched = (hit & m).sum() > 0.05 * m.sum()
        centre, axes = (round(w.cx), round(w.cy)), (round(w.a), round(w.b))
        cv2.ellipse(out, centre, axes, 0, 0, 360, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.ellipse(out, centre, axes, 0, 0, 360, BAD if touched else OK, 3, cv2.LINE_AA)
    return out


def alt_text(garment: str, person: str, report_dict: dict) -> str:
    """What the check found, for someone who can't see the overlay."""
    v = report_dict["verdict"]
    lead = {"pass": "Approved try-on", "warn": "Try-on that needs a closer look", "fail": "Refused render, shown in grey as evidence"}[v]
    found = " ".join(c["message"] for c in report_dict["checks"] if c["status"] != "pass")
    person_msg = next((c["message"] for c in report_dict["checks"] if c["id"] == "person"), "")
    who = "the face matches" if "Hands were not" in person_msg else "face and hands match"
    return f"{lead}: {garment} on {person}. {found or f'All four checks passed: it clears the wheels and the chair, {who} the photo.'}"
