"""Reduce the ledger and matrix to the numbers quoted in README and RESULTS.
Writes proof_results/summary.json. Spends nothing."""
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from seatedfit.catalogue import GARMENTS, LEDGER, PROOF  # noqa: E402


def main():
    rows = [json.loads(x) for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
    done = [r for r in rows if r.get("call") == "task_done"]
    matrix = json.loads((PROOF / "matrix.json").read_text(encoding="utf-8"))
    cells = [c for c in matrix["cells"] if c["checks"]]

    def values(check, cs):
        return sorted(next(x for x in c["checks"] if x["id"] == check)["value"] for c in cs)

    def by_length(length):
        return [c for c in cells if GARMENTS[c["garment"]]["length"] == length]

    hands = sorted(next(x for x in c["checks"] if x["id"] == "person")["detail"]["worst_hand"]
                   for c in cells if next(x for x in c["checks"] if x["id"] == "person")["detail"].get("worst_hand") is not None)
    verdicts = {}
    for length in ("long", "short"):
        verdicts[length] = dict(Counter(c["verdict"] for c in by_length(length)))
    out = {
        "ledger_rows": len(rows),
        "tasks_created": sum(1 for r in rows if r.get("call") == "task_create" and r.get("task_id")),
        "tasks_succeeded": sum(1 for r in done if r.get("task_status") == "success"),
        "tasks_failed": sum(1 for r in done if r.get("task_status") != "success"),
        "error_codes": dict(Counter(r["error_code"] for r in rows if r.get("error_code"))),
        "median_wait_seconds": median(r["waited"] for r in done if "waited" in r),
        "counts": matrix["counts"], "cells_total": matrix["cells_total"], "verdicts_by_length": verdicts,
        "evidence": {
            "clearance_short_max": values("clearance", by_length("short"))[-1],
            "clearance_long_max": values("clearance", by_length("long"))[-1],
            "clearance_values_warn": sorted(v for v in values("clearance", cells) if .05 <= v < .15),
            "clearance_lowest_fail": min(v for v in values("clearance", cells) if v >= .15),
            "change_min": values("change", cells)[0], "chair_ssim_min": values("chair", cells)[0],
            "face_ssim_min": values("person", cells)[0], "hand_ssim_min": hands[0],
        },
        "demo_pair": {c["garment"]: {"verdict": c["verdict"], "clearance": next(x for x in c["checks"] if x["id"] == "clearance")["value"]}
                      for c in cells if c["model"] == "m2_studio" and c["garment"] in ("g1_long_wool_coat", "g4_crop_jacket")},
    }
    (PROOF / "summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
