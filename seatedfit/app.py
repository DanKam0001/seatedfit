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
from PIL import Image, UnidentifiedImageError

from . import checks, overlay, regions
from .catalogue import GARMENTS, LEDGER, MODELS, PROOF, ROOT, garment_path
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


def _used_today() -> int:
    try:
        d = json.loads(_cap_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    return d["used"] if d.get("day") == date.today().isoformat() else 0


def take_live_slot() -> bool:
    """Atomically reserve one paid call for today."""
    with _lock:
        used = _used_today()
        if used >= daily_cap():
            return False
        _cap_file().write_text(json.dumps({"day": date.today().isoformat(), "used": used + 1}), encoding="utf-8")
        return True


def live_client() -> YouCamClient | None:
    """Live calls are logged next to the cap file, never in proof_results."""
    if not os.environ.get("YOURCAM_API_KEY"):
        return None
    return YouCamClient(ledger=_cap_file().with_suffix(".jsonl"), task_cap=10**9)


FALLBACK = "Live try-ons are paused for today, so here are saved results from our sample models. Your photo was not stored."


def _decode(data: bytes) -> np.ndarray:
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "That photo is over 10 MB. Please use a smaller one.")
    try:
        im = Image.open(io.BytesIO(data))
        if im.format not in ("JPEG", "PNG"):
            raise HTTPException(415, "Please upload a JPG or PNG photo.")
        return np.array(im.convert("RGB"))
    except (UnidentifiedImageError, OSError):
        raise HTTPException(415, "Please upload a JPG or PNG photo.")


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


@app.post("/api/tryon")
async def tryon(photo: UploadFile = File(...), garment: str = Form(...)):
    if garment not in GARMENTS:
        raise HTTPException(404, "Unknown garment.")
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
        res = client.try_on(buf.getvalue(), garment_path(garment), info["category"], {"garment": garment, "live": True},
                            src_name="photo.jpg")
    except SpendStop:
        return {"mode": "fallback", "message": FALLBACK}
    except YouCamError as e:
        return {"mode": "api_error", "error": e.code,
                "message": "The try-on service could not use this photo, so there is no picture to show."}
    result = np.array(Image.open(io.BytesIO(res.image)).convert("RGB"))
    if result.shape != rgb.shape:
        result = np.array(Image.fromarray(result).resize(rgb.shape[1::-1]))
    reg = regions.locate_auto(rgb)
    rep = checks.run_checks(rgb, result, reg)
    d = rep.to_dict()
    payload = d | {"mode": "live", "photo": photo_report, "overlay": _data_url(overlay.draw(result, reg, rep)),
                   "alt": overlay.alt_text(info["name"], "your photo", d)}
    if d["verdict"] != "fail":
        payload["render"] = _data_url(result)
    return payload


@app.exception_handler(HTTPException)
async def http_error(_, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


app.mount("/media", StaticFiles(directory=str(PROOF / "web"), check_dir=False), name="media")
app.mount("/static", StaticFiles(directory=str(STATIC), check_dir=False), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
