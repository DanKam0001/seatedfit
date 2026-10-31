"""Start the app, run one command against it, stop the app.
Usage: python scripts/with_server.py PORT node scripts/a11y.mjs URL   (URL becomes the server's address)
Live calls land in the proof ledger; the daily cap file stays out of the repo."""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
port, cmd = sys.argv[1], sys.argv[2:]
url = f"http://127.0.0.1:{port}"
env = {**os.environ, "LIVE_LEDGER": str(ROOT / "proof_results" / "youcam_calls.jsonl"),
       "LIVE_CAP_FILE": str(Path(tempfile.mkdtemp()) / "cap.json")}
if os.environ.get("NO_KEY"):
    env["YOURCAM_API_KEY"] = ""
server = subprocess.Popen([sys.executable, "-m", "uvicorn", "seatedfit.app:app", "--port", port], cwd=ROOT, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{url}/api/health", timeout=2)
            break
        except OSError:
            time.sleep(1)
    code = subprocess.run([url if c == "URL" else c for c in cmd], cwd=ROOT, shell=sys.platform == "win32").returncode
finally:
    server.terminate()
sys.exit(code)
