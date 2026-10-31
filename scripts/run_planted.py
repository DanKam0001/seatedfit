"""Plant each failure in clean real renders and record whether the check catches it.
Writes proof_results/planted_failures.json and example images. Spends nothing."""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from seatedfit import checks, overlay, regions  # noqa: E402
from seatedfit.catalogue import GARMENTS, PROOF, model_path, render_path  # noqa: E402
from seatedfit.planted import PLANTS  # noqa: E402

OUT = PROOF / "planted"


def main():
    matrix = json.loads((PROOF / "matrix.json").read_text(encoding="utf-8"))
    clean = [c for c in matrix["cells"] if c["verdict"] == "pass" and GARMENTS[c["garment"]]["length"] == "short"]
    OUT.mkdir(exist_ok=True)
    rows = []
    for c in clean:
        m, g = c["model"], c["garment"]
        src = np.array(Image.open(model_path(m)).convert("RGB"))
        res = np.array(Image.open(render_path(m, g, c["category"])).convert("RGB"))
        if res.shape != src.shape:
            res = np.array(Image.fromarray(res).resize(src.shape[1::-1]))
        reg = regions.locate_marked(m, src)
        base = checks.run_checks(src, res, reg)
        rows.append({"model": m, "garment": g, "plant": "none", "expect_check": None, "expect": "pass",
                     "verdict": base.verdict, "caught": base.verdict == "pass",
                     "statuses": {x.id: x.status for x in base.checks}})
        for name, (fn, check_id, want) in PLANTS.items():
            bad = fn(src, res, reg)
            rep = checks.run_checks(src, bad, reg)
            got = next(x for x in rep.checks if x.id == check_id)
            rows.append({"model": m, "garment": g, "plant": name, "expect_check": check_id, "expect": want,
                         "got": got.status, "value": got.value, "verdict": rep.verdict,
                         "caught": got.status == want and rep.verdict == "fail",
                         "statuses": {x.id: x.status for x in rep.checks}})
            if m == "m2_studio" and g == "g4_crop_jacket":
                Image.fromarray(overlay.draw(bad, reg, rep)).save(OUT / f"{name}.jpg", quality=85)
    summary = {}
    for name in ["none", *PLANTS]:
        sub = [r for r in rows if r["plant"] == name]
        summary[name] = {"runs": len(sub), "caught": sum(r["caught"] for r in sub),
                         "missed": [f"{r['model']} {r['garment']}" for r in sub if not r["caught"]]}
    (PROOF / "planted_failures.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
