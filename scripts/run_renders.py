"""Pay for every model x garment render that is not already saved. Stops on a spend stop."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from seatedfit.catalogue import GARMENTS, MODELS, render_cached  # noqa: E402
from seatedfit.youcam import SpendStop  # noqa: E402

stopped = False


def one(pair):
    global stopped
    model, garment = pair
    if stopped:
        return
    category = GARMENTS[garment]["category"]
    try:
        print(model, garment, json.dumps(render_cached(model, garment, category)), flush=True)
    except SpendStop as e:
        stopped = True
        print("SPEND STOP:", e, flush=True)


if __name__ == "__main__":
    pairs = [(m, g) for m in MODELS for g in GARMENTS]
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(one, pairs))
    print("stopped" if stopped else "complete", flush=True)
