"""One real paid upload through the app's own /api/tryon route, using a synthetic sample
as the upload. Logged to the build ledger; writes proof_results/live_path_check.json."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LIVE_LEDGER"] = str(ROOT / "proof_results" / "youcam_calls.jsonl")
os.environ["LIVE_CAP_FILE"] = str(Path(tempfile.mkdtemp()) / "cap.json")

from fastapi.testclient import TestClient  # noqa: E402

from seatedfit.app import app  # noqa: E402
from seatedfit.catalogue import PROOF, model_path  # noqa: E402

r = TestClient(app).post("/api/tryon", data={"garment": "g4_crop_jacket"},
                         files={"photo": ("m3.png", model_path("m3_home").read_bytes(), "image/png")})
j = r.json()
out = {"http": r.status_code, "mode": j.get("mode"), "verdict": j.get("verdict"), "error": j.get("error"),
       "render_returned": "render" in j, "checks": [{k: c[k] for k in ("id", "status", "value")} for c in j.get("checks", [])]}
(PROOF / "live_path_check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(out)
