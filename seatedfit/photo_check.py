"""Plain-word checks on a photo before any money is spent on it."""
from __future__ import annotations

import numpy as np

from . import regions as R

MIN_FACE_SHARE = 0.05  # face height as a share of the frame


def _item(id_, label, ok, good, bad, soft=False):
    return {"id": id_, "label": label, "status": "pass" if ok else ("warn" if soft else "fail"),
            "message": good if ok else bad}


def check_photo(rgb: np.ndarray, size_ok=True) -> dict:
    h, w = rgb.shape[:2]
    work = R.to_work(rgb)
    faces = R.find_faces(work)
    wheels = R.find_wheels(work)
    hw = work.shape[0]
    face_share = faces[0][3] / hw if faces else 0.0
    head_in_frame = bool(faces) and faces[0][1] > hw * 0.01
    items = [
        _item("size", "Sharp enough", size_ok and min(h, w) >= 384 and max(h, w) >= 512 and max(h, w) <= 4096,
              "The photo is a usable size.", "The photo needs to be between 512 and 4096 pixels on its long side."),
        _item("one_person", "One person", len(faces) <= 1, "We can see one person.",
              "We can see more than one face. Please use a photo with just you in it."),
        _item("face", "Face visible", len(faces) >= 1, "Your face is clear.",
              "We can't see a face. Please face the camera with nothing covering your face."),
        _item("big_enough", "Big enough in the picture", face_share >= MIN_FACE_SHARE, "You fill enough of the picture.",
              "You look small in this photo. Please move closer."),
        _item("in_frame", "Head to wheels in frame", head_in_frame and len(wheels) >= 1,
              "We can see you and the wheels.",
              "We couldn't confirm your head and wheels are both in the picture, so wheel checks may be missing.",
              soft=True),
    ]
    ok = all(i["status"] != "fail" for i in items)
    return {"ok": ok, "items": items}
