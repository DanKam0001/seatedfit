"""SeatedFit web service. Serves saved renders; a capped upload path calls YouCam."""
from __future__ import annotations

import base64
import io
import json
import os
import tempfile
import threading
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError

from . import checks, overlay, regions, tone
from .catalogue import GARMENTS, MODELS, PROOF, ROOT, garment_path, model_path, render_path
from .photo_check import check_photo
from .youcam import SpendStop, YouCamClient, YouCamError

load_dotenv(ROOT / ".env")

MAX_UPLOAD = 10 * 1024 * 1024
STATIC = ROOT / "static"
app = FastAPI(title="SeatedFit")
_lock = threading.Lock()

_matrix: dict | None = None


def matrix() -> dict:
    global _matrix
    if _matrix is None:
        path = PROOF / "matrix.json"
        _matrix = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"cells": [], "counts": {}}
    return _matrix


def _cap_file() -> Path:
    return Path(os.environ.get("LIVE_CAP_FILE") or Path(tempfile.gettempdir()) / "seatedfit_live_cap.json")


def daily_cap() -> int:
    return int(os.environ.get("LIVE_DAILY_CAP", "10"))


def tone_cap() -> int:
    return int(os.environ.get("LIVE_TONE_DAILY_CAP", "2"))  # a reading costs ten try-ons


def _today_counts() -> dict:
    try:
        d = json.loads(_cap_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if d.get("day") == date.today().isoformat() else {}


def _used_today() -> int:
    return _today_counts().get("used", 0)


def take_live_slot(key="used", cap=None) -> bool:
    """Atomically reserve one paid call for today."""
    with _lock:
        counts = _today_counts()
        if counts.get(key, 0) >= (daily_cap() if cap is None else cap):
            return False
        counts |= {"day": date.today().isoformat(), key: counts.get(key, 0) + 1}
        _cap_file().write_text(json.dumps(counts), encoding="utf-8")
        return True


def live_client() -> YouCamClient | None:
    """Live calls are logged next to the cap file unless LIVE_LEDGER names another."""
    if not os.environ.get("YOURCAM_API_KEY"):
        return None
    return YouCamClient(ledger=os.environ.get("LIVE_LEDGER") or _cap_file().with_suffix(".jsonl"),
                        task_cap=int(os.environ.get("LIVE_TASK_CAP", "120")))


FALLBACK = "Live try-ons are paused for today, so here are saved results from our sample models. Your photo was not stored."


def _decode(data: bytes) -> np.ndarray:
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "That photo is over 10 MB. Please use a smaller one.")
    try:
        im = Image.open(io.BytesIO(data))
        if im.format not in ("JPEG", "PNG"):
            raise HTTPException(415, "Please upload a JPG or PNG photo.")
        # upright, as the browser shows it, so a shopper's marks land where they were placed
        return np.array(ImageOps.exif_transpose(im).convert("RGB"))
    except (UnidentifiedImageError, OSError):
        raise HTTPException(415, "Please upload a JPG or PNG photo.")


def parse_marks(raw: str) -> list:
    """The shopper's wheels, as fractions of the picture. Empty means none were marked."""
    if not raw:
        return []
    bad = HTTPException(422, "Those wheel marks could not be read. Please mark your wheels again.")
    try:
        marks = json.loads(raw)
        marks = [{"kind": m["kind"], **{k: float(m[k]) for k in "xywh"}} for m in marks]
    except (ValueError, TypeError, KeyError):
        raise bad
    if not 1 <= len(marks) <= 6 or not any(m["kind"] == "wheel" for m in marks):
        raise HTTPException(422, "Please mark at least one big wheel, and no more than six wheels in all.")
    for m in marks:
        if m["kind"] not in ("wheel", "caster") or not (0 <= m["x"] <= 1 and 0 <= m["y"] <= 1):
            raise bad
        if not (0.02 <= m["w"] <= 0.8 and 0.02 <= m["h"] <= 0.8):
            raise HTTPException(422, "A wheel mark is too small or too big. Please resize it.")
    return marks


def _report(src: np.ndarray, result: np.ndarray, marks: list, info: dict, photo_report: dict) -> dict:
    reg = regions.locate_shopper(src, marks) if marks else regions.locate_auto(src)
    rep = checks.run_checks(src, result, reg)
    d = rep.to_dict()
    payload = d | {"mode": "live", "photo": photo_report, "wheels_marked": len(marks),
                   "overlay": _data_url(overlay.draw(result, reg, rep)),
                   "alt": overlay.alt_text(info["name"], "your photo", d)}
    if d["verdict"] != "fail":
        payload["render"] = _data_url(result)
    return payload


def _data_url(rgb: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


@app.get("/api/health")
def health():
    return {"status": "ok", "saved_cells": len(matrix().get("cells", []))}


@app.get("/api/catalogue")
def catalogue():
    return {"models": [{"id": k, "description": v} for k, v in MODELS.items()],
            "garments": [{"id": k, **v} for k, v in GARMENTS.items()],
            "live": {"available": bool(os.environ.get("YOURCAM_API_KEY")) and _used_today() < daily_cap()}}


@app.get("/api/matrix")
def get_matrix():
    return matrix()


@app.get("/api/tone/{model}")
def sample_tone(model: str):
    """Needs no key: the saved YouCam reading, or a free one from the pixels."""
    if model not in MODELS:
        raise HTTPException(404, "Unknown model.")
    return tone.sample_reading(model)


@app.get("/api/sample-photo/{model}")
def sample_photo(model: str):
    if model not in MODELS:
        raise HTTPException(404, "Unknown model.")
    return FileResponse(model_path(model))


@app.get("/api/gallery.zip")
def gallery():
    """Approved renders only."""
    buf = io.BytesIO()
    names = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for c in matrix().get("cells", []):
            if c["verdict"] == "pass":
                name = f"{c['model']}__{c['garment']}.jpg"
                z.write(ROOT / c["render"], name)
                names.append({"file": name, "description": c["alt"]})
        z.writestr("descriptions.json", json.dumps(names, indent=1))
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="seatedfit-approved-gallery.zip"'})


@app.post("/api/photo-check")
async def photo_check(photo: UploadFile = File(...)):
    # read, judge, forget: the bytes never touch the disk
    return check_photo(_decode(await photo.read()))


@app.post("/api/tone")
async def measure_tone(photo: UploadFile = File(...)):
    """Only the face crop leaves this server, and only when the shopper asks."""
    rgb = regions.to_work(_decode(await photo.read()))
    faces = regions.find_faces(rgb)
    if not faces:
        raise HTTPException(422, "We could not find a face in this photo, so there is no skin tone to read.")
    local = tone.local_skin(rgb, faces[0])
    free = {"skin": local, "source": "local", "garments": tone.rank(local)}
    client = live_client()
    if client is None or not take_live_slot("tone", tone_cap()):
        return free | {"message": "YouCam skin tone readings are paused for today, so this is our estimate from the photo's pixels."}
    try:
        colours = client.skin_tone(tone.face_crop(rgb, faces[0]), {"live": True})
    except YouCamError as e:
        return free | {"error": e.code, "message": "YouCam could not read this face, so this is our estimate from the photo's pixels."}
    return {"skin": colours["skin_color"], "source": "youcam", "garments": tone.rank(colours["skin_color"])}


def _saved_sample(sample: str, garment: str, marks: list) -> dict:
    """A sample photo with a saved render: the shopper's marks, the real check, no paid call."""
    info = GARMENTS[garment]
    src = regions.to_work(np.array(Image.open(model_path(sample)).convert("RGB")))
    path = render_path(sample, garment, info["category"])
    if not path.exists():
        return {"mode": "api_error", "message": "The try-on service refused this pair, so there is no picture to show."}
    result = np.array(Image.open(path).convert("RGB"))
    if result.shape != src.shape:
        result = np.array(Image.fromarray(result).resize(src.shape[1::-1]))
    return _report(src, result, marks, info, check_photo(src)) | {"saved": True}


@app.post("/api/tryon")
async def tryon(photo: UploadFile | None = File(None), garment: str = Form(...), wheels: str = Form(""), sample: str = Form("")):
    if garment not in GARMENTS:
        raise HTTPException(404, "Unknown garment.")
    marks = parse_marks(wheels)
    if sample:
        if sample not in MODELS:
            raise HTTPException(404, "Unknown model.")
        return _saved_sample(sample, garment, marks)
    if photo is None:
        raise HTTPException(422, "Please choose a photo.")
    data = await photo.read()
    rgb = regions.to_work(_decode(data))
    photo_report = check_photo(rgb)
    if not photo_report["ok"]:
        return {"mode": "refused_photo", "photo": photo_report}
    client = live_client()
    if client is None or not take_live_slot():
        return {"mode": "fallback", "message": FALLBACK}
    info = GARMENTS[garment]
    try:
        buf = io.BytesIO()
        Image.fromarray(rgb).save(buf, "JPEG", quality=92)  # re-encoded: strips metadata from the photo
        res = client.try_on(buf.getvalue(), garment_path(garment), info["category"],
                            {"garment": garment, "live": True, "wheels_marked": len(marks)}, src_name="photo.jpg")
    except SpendStop:
        return {"mode": "fallback", "message": FALLBACK}
    except YouCamError as e:
        return {"mode": "api_error", "error": e.code,
                "message": "The try-on service could not use this photo, so there is no picture to show."}
    result = np.array(Image.open(io.BytesIO(res.image)).convert("RGB"))
    if result.shape != rgb.shape:
        result = np.array(Image.fromarray(result).resize(rgb.shape[1::-1]))
    return _report(rgb, result, marks, info, photo_report)


@app.exception_handler(HTTPException)
async def http_error(_, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


app.mount("/media", StaticFiles(directory=str(PROOF / "web"), check_dir=False), name="media")
app.mount("/static", StaticFiles(directory=str(STATIC), check_dir=False), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
