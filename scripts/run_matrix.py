"""Run the render check over every saved render and write proof_results/matrix.json,
the overlays, and the web images. Spends nothing: renders come from the cache."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from seatedfit import checks, overlay, regions  # noqa: E402
from seatedfit.catalogue import GARMENTS, MODELS, PROOF, garment_path, load_failures, model_path, render_path  # noqa: E402

OVERLAYS = PROOF / "overlays"
WEB = PROOF / "web"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def jpg(arr_or_path, out: Path, side=640, q=84):
    im = Image.fromarray(arr_or_path) if isinstance(arr_or_path, np.ndarray) else Image.open(arr_or_path).convert("RGB")
    im.thumbnail((side, side))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=q)


def main():
    for m in MODELS:
        jpg(model_path(m), WEB / "models" / f"{m}.jpg")
    for g in GARMENTS:
        jpg(garment_path(g), WEB / "garments" / f"{g}.jpg")
    fails = load_failures()
    cells = []
    for m, person in MODELS.items():
        src = np.array(Image.open(model_path(m)).convert("RGB"))
        reg = regions.locate_marked(m, src)
        for g, info in GARMENTS.items():
            cat = info["category"]
            path = render_path(m, g, cat)
            cell = {"model": m, "garment": g, "category": cat, "source_sha": sha(model_path(m)),
                    "garment_sha": sha(garment_path(g))}
            if not path.exists():
                reason = fails.get(path.stem, "no render saved")
                cell |= {"verdict": "no_render", "api_error": reason, "checks": [],
                         "alt": f"No render: the try-on service returned {reason}."}
                cells.append(cell)
                continue
            res = np.array(Image.open(path).convert("RGB"))
            rep = checks.run_checks(src, res, reg)
            d = rep.to_dict()
            if res.shape != src.shape:
                res = np.array(Image.fromarray(res).resize(src.shape[1::-1]))
            ov = overlay.draw(res, reg, rep)
            name = f"{m}__{g}.jpg"
            OVERLAYS.mkdir(exist_ok=True)
            Image.fromarray(ov).save(OVERLAYS / name, quality=88)
            jpg(ov, WEB / "overlays" / name, side=720)
            jpg(res, WEB / "renders" / name, side=720)
            cell |= d | {"render": path.relative_to(ROOT).as_posix(), "render_sha": sha(path),
                         "overlay": f"overlays/{name}", "web": name,
                         "alt": overlay.alt_text(info["name"], person, d)}
            cells.append(cell)
    counts = {k: sum(c["verdict"] == k for c in cells) for k in ("pass", "warn", "fail", "no_render")}
    out = {"thresholds": checks.THRESHOLDS, "models": len(MODELS), "garments": len(GARMENTS),
           "cells_total": len(cells), "counts": counts, "cells": cells}
    (PROOF / "matrix.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(counts)
    for c in cells:
        ch = {x["id"]: x for x in c["checks"]}
        if ch:
            print(f"{c['model']:11s}{c['garment'][:15]:16s}{c['verdict']:5s}" + " ".join(
                f"{k[:3]}={ch[k]['value']}/{ch[k]['status'][0]}" for k in ch),
                ch["chair"]["detail"].get("worst_wheel_edges_kept"), ch["person"]["detail"].get("worst_hand"))


if __name__ == "__main__":
    main()
