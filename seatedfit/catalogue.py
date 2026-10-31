"""The sample models, the garment catalogue, and the paid render cache."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
PROOF = ROOT / "proof_results"
RENDERS = PROOF / "renders"
LEDGER = PROOF / "youcam_calls.jsonl"
FAILURES = PROOF / "render_failures.json"

MODELS = {
    "m1_studio": "Woman with long dark hair in a white T-shirt and black leggings, manual wheelchair, pale studio",
    "m2_studio": "Man in a grey T-shirt and black trousers, sports wheelchair, grey studio",
    "m3_home": "Older woman in a navy top and grey trousers, power wheelchair, living room",
    "m4_home": "Young man in a white T-shirt and jeans, sports wheelchair, hallway",
    "m5_outdoor": "Woman in a black top and navy trousers, manual wheelchair, outdoors on a pavement",
    "m6_side": "Older man in a blue T-shirt and grey trousers, manual wheelchair, three-quarter view",
}

# length is what a shopper would call it; category is what the API is told.
GARMENTS = {
    "g1_long_wool_coat": {"name": "Long wool coat", "length": "long", "category": "full_body"},
    "g2_maxi_dress": {"name": "Maxi dress", "length": "long", "category": "full_body"},
    "g3_trench": {"name": "Trench coat", "length": "long", "category": "full_body"},
    "g4_crop_jacket": {"name": "Cropped jacket", "length": "short", "category": "upper_body"},
    "g5_shirt": {"name": "Shirt", "length": "short", "category": "upper_body"},
    "g6_knit": {"name": "Knit jumper", "length": "short", "category": "upper_body"},
    "g7_blazer": {"name": "Blazer", "length": "short", "category": "upper_body"},
    "g8_puffer_long": {"name": "Long puffer coat", "length": "long", "category": "full_body"},
}


def model_path(model: str) -> Path:
    return ASSETS / "models" / f"{model}.png"


def garment_path(garment: str) -> Path:
    return ASSETS / "garments" / f"{garment}.png"


def render_path(model: str, garment: str, category: str) -> Path:
    return RENDERS / f"{model}__{garment}__{category}.jpg"


def load_failures() -> dict:
    return json.loads(FAILURES.read_text(encoding="utf-8")) if FAILURES.exists() else {}


def _save_failure(key: str, code: str):
    f = load_failures()
    f[key] = code
    FAILURES.parent.mkdir(parents=True, exist_ok=True)
    FAILURES.write_text(json.dumps(f, indent=1, sort_keys=True), encoding="utf-8")


def render_cached(model: str, garment: str, category: str, client=None) -> dict:
    """Return a saved render, or pay for one. Input errors are cached as well,
    because the same input fails the same way and each attempt costs money."""
    from .youcam import SpendStop, YouCamClient, YouCamError

    out = render_path(model, garment, category)
    key = out.stem
    if out.exists():
        return {"status": "cached", "path": str(out)}
    if key in load_failures():
        return {"status": "failed", "error": load_failures()[key], "cached": True}
    client = client or YouCamClient(ledger=LEDGER, task_cap=int(os.environ.get("BUILD_TASK_CAP", "120")))
    ctx = {"model": model, "garment": garment, "category": category}
    try:
        res = client.try_on(model_path(model), garment_path(garment), category, ctx)
    except SpendStop:
        raise
    except YouCamError as e:
        if e.code not in ("network", "poll_timeout") and not e.code.startswith("http_5"):
            _save_failure(key, e.code)
        return {"status": "failed", "error": e.code}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(res.image)
    return {"status": "rendered", "path": str(out), "seconds": res.seconds, "task_id": res.task_id}
