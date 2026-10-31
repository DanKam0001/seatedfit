"""Measure the automatic wheel finder used for uploads against the hand-marked wheels.
Writes proof_results/locator_eval.json. Spends nothing."""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from seatedfit import regions  # noqa: E402
from seatedfit.catalogue import MODELS, PROOF, model_path  # noqa: E402


def main():
    rows = []
    for m in MODELS:
        rgb = np.array(Image.open(model_path(m)).convert("RGB"))
        marked = regions.locate_marked(m, rgb)
        auto = regions.Regions(marked.shape, "auto", wheels=regions.find_wheels(rgb))
        truth = [w for w in marked.wheels]
        found = 0
        for w in truth:
            tm = w.mask(marked.shape)
            best = max((((tm & a.mask(marked.shape)).sum() / (tm | a.mask(marked.shape)).sum()) for a in auto.wheels), default=0)
            found += best >= 0.5
        false_pos = sum(max(((a.mask(marked.shape) & w.mask(marked.shape)).sum() / a.mask(marked.shape).sum() for w in truth), default=0) < 0.5
                        for a in auto.wheels)
        rows.append({"model": m, "marked_wheels": len(truth), "auto_found": int(found), "auto_returned": len(auto.wheels),
                     "false_positives": int(false_pos)})
    out = {"decision": "Too unreliable to use. Uploads report wheel checks as not measured and can never pass.",
           "match_rule":"overlap over union of at least 0.5 with a hand-marked wheel",
           "marked": sum(r["marked_wheels"] for r in rows), "found": sum(r["auto_found"] for r in rows),
           "false_positives": sum(r["false_positives"] for r in rows), "rows": rows}
    (PROOF / "locator_eval.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
