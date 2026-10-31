"""Render pairs through the real API with the cache in front: nothing is paid for twice.

    python scripts/render_one.py m1_studio g1_long_wool_coat full_body
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from seatedfit.catalogue import render_cached  # noqa: E402

if __name__ == "__main__":
    model, garment, category = sys.argv[1:4]
    print(render_cached(model, garment, category))
