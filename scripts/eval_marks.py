"""How much does a shopper's marking error move the verdict? Spends nothing.

Reruns every saved render with wheels only (no footplates, no hands), as an upload
would have, with the eye-marked ellipses jittered as a shopper's hand might. Also
measures how well a mark must sit on a real outline, which sets mark_support.
"""
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from seatedfit import checks, regions  # noqa: E402
from seatedfit.catalogue import GARMENTS, MODELS, PROOF, model_path, render_path  # noqa: E402

JITTERS = [0.0, 0.01, 0.02, 0.04]  # share of the picture, position; size moves by four times this
TRIES = 4


def as_marks(reg, jitter, rnd):
    h, w = reg.shape[:2]
    out = []
    for e in reg.wheels:
        d = lambda: rnd.uniform(-jitter, jitter)
        s = lambda: 1 + rnd.uniform(-4 * jitter, 4 * jitter)
        out.append({"kind": e.kind, "x": e.cx / w + d(), "y": e.cy / h + d(), "w": 2 * e.a / w * s(), "h": 2 * e.b / h * s()})
    return out


def support_study(rnd):
    """Real wheels against the same ellipses thrown at places that aren't wheels."""
    real, stray = [], []
    for m in MODELS:
        src = np.array(Image.open(model_path(m)).convert("RGB"))
        reg = regions.locate_marked(m, src)
        edges = cv2.Canny(cv2.GaussianBlur(cv2.cvtColor(src, cv2.COLOR_RGB2GRAY), (3, 3), 0), 50, 150)
        wheel_zone = cv2.dilate(reg.wheel_mask.astype(np.uint8), np.ones((31, 31), np.uint8)) > 0
        h, w = reg.shape[:2]
        for e in reg.wheels:
            real.append({"model": m, "kind": e.kind, "support": round(regions.mark_support(edges, e), 3)})
            tries = 0
            while tries < 8:
                cx, cy = rnd.uniform(e.a, w - e.a), rnd.uniform(e.b, h - e.b)
                moved = regions.Ellipse(cx, cy, e.a, e.b, e.kind)
                if (moved.mask(reg.shape) & wheel_zone).mean() == 0:
                    stray.append(round(regions.mark_support(edges, moved), 3))
                    tries += 1
    return real, stray


def main():
    rnd = random.Random(7)
    real, stray = support_study(rnd)
    vals = sorted(r["support"] for r in real if r["kind"] == "wheel")
    print("real wheels", vals)
    print("real casters", sorted(r["support"] for r in real if r["kind"] == "caster"))
    print("stray pct", np.percentile(stray, [50, 75, 90, 95]).round(3), "n", len(stray))
    table = {str(j): {"runs": 0, "same_verdict": 0, "fail_became_pass": 0, "pass_became_fail": 0} for j in JITTERS}
    for m in MODELS:
        src = np.array(Image.open(model_path(m)).convert("RGB"))
        hand = regions.locate_marked(m, src)
        for g, info in GARMENTS.items():
            path = render_path(m, g, info["category"])
            if not path.exists():
                continue
            res = np.array(Image.open(path).convert("RGB"))
            base = checks.run_checks(src, res, regions.locate_shopper(src, as_marks(hand, 0, rnd))).verdict
            for j in JITTERS:
                for _ in range(1 if j == 0 else TRIES):
                    got = checks.run_checks(src, res, regions.locate_shopper(src, as_marks(hand, j, rnd))).verdict
                    t = table[str(j)]
                    t["runs"] += 1
                    t["same_verdict"] += got == base
                    t["fail_became_pass"] += base == "fail" and got == "pass"
                    t["pass_became_fail"] += base == "pass" and got == "fail"
    out = {"what": "Saved renders rechecked with wheels only, as an upload has, using jittered copies of the eye marks",
           "jitter_is": "largest move as a share of the picture; size changes by up to four times that",
           "mark_support": {"threshold": checks.THRESHOLDS["mark_support"], "real_wheels": real, "stray_marks": len(stray),
                            "stray_percentiles_50_75_90_95": [round(float(x), 3) for x in np.percentile(stray, [50, 75, 90, 95])],
                            "stray_passing_threshold": sum(s >= checks.THRESHOLDS["mark_support"] for s in stray)},
           "by_jitter": table}
    (PROOF / "marked_wheels_eval.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(table, indent=0))


if __name__ == "__main__":
    main()
