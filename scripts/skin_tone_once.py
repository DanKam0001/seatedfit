"""One paid AI Face Skin Tone Analysis (20 units) on the face region of a sample.
Refuses to run if that sample already has a saved reading. Failed tasks aren't charged."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from PIL import Image  # noqa: E402

from seatedfit import regions, tone  # noqa: E402
from seatedfit.catalogue import LEDGER, PROOF, model_path  # noqa: E402
from seatedfit.youcam import YouCamClient, YouCamError  # noqa: E402

load_dotenv(ROOT / ".env")
model = sys.argv[1] if len(sys.argv) > 1 else "m2_studio"
out = PROOF / "skin_tone.json"
saved = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
if model in saved:
    sys.exit(f"{model} already measured: {saved[model]['skin_color']}")

rgb = regions.to_work(np.array(Image.open(model_path(model)).convert("RGB")))
face = regions.find_faces(rgb)[0]
crop = tone.face_crop(rgb, face)
client = YouCamClient(ledger=LEDGER, task_cap=120)
attempts = []
for level in sys.argv[2:] or ["low"]:
    try:
        colours = client.skin_tone(crop, {"model": model}, level)
    except YouCamError as e:
        attempts.append({"strictness": level, "error": e.code, "detail": str(e)[:300]})
        print(attempts[-1])
        continue
    saved[model] = {"skin_color": colours["skin_color"], "colours": colours, "strictness": level,
                    "attempts_before": attempts, "local_reading": tone.local_skin(rgb, face),
                    "units": 20, "api": "POST /s2s/v2.0/task/skin-tone-analysis"}
    out.write_text(json.dumps(saved, indent=1), encoding="utf-8")
    print(saved[model])
    break
else:
    print("no reading", attempts)
