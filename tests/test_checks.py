"""Planted failures in real clean renders, and the demo pair from the saved run."""
import json

import numpy as np
import pytest
from PIL import Image

from seatedfit import checks, regions
from seatedfit.catalogue import GARMENTS, PROOF, model_path, render_path
from seatedfit.planted import PLANTS

CLEAN = [("m2_studio", "g4_crop_jacket"), ("m3_home", "g5_shirt"), ("m6_side", "g6_knit")]


def load(model, garment):
    src = np.array(Image.open(model_path(model)).convert("RGB"))
    res = np.array(Image.open(render_path(model, garment, GARMENTS[garment]["category"])).convert("RGB"))
    if res.shape != src.shape:
        res = np.array(Image.fromarray(res).resize(src.shape[1::-1]))
    return src, res, regions.locate_marked(model, src)


@pytest.mark.parametrize("model,garment", CLEAN)
def test_clean_render_passes(model, garment):
    src, res, reg = load(model, garment)
    rep = checks.run_checks(src, res, reg)
    assert rep.verdict == "pass", rep.to_dict()


@pytest.mark.parametrize("model,garment", CLEAN)
@pytest.mark.parametrize("plant", PLANTS)
def test_planted_failure_is_caught(model, garment, plant):
    fn, check_id, want = PLANTS[plant]
    src, res, reg = load(model, garment)
    rep = checks.run_checks(src, fn(src, res, reg), reg)
    got = next(c for c in rep.checks if c.id == check_id)
    assert got.status == want and rep.verdict == "fail", rep.to_dict()


def test_long_coat_fails_and_cropped_jacket_passes_on_same_person():
    coat = checks.run_checks(*load("m2_studio", "g1_long_wool_coat"))
    jacket = checks.run_checks(*load("m2_studio", "g4_crop_jacket"))
    assert coat.verdict == "fail" and jacket.verdict == "pass"
    clr = next(c for c in coat.checks if c.id == "clearance")
    assert clr.status == "fail" and f"{clr.value:.0%}" in clr.message


def test_every_check_returns_number_status_and_region():
    d = checks.run_checks(*load("m2_studio", "g1_long_wool_coat")).to_dict()
    assert {c["id"] for c in d["checks"]} == {"clearance", "chair", "person", "change"}
    assert all(c["value"] is not None and c["status"] in ("pass", "warn", "fail") for c in d["checks"])


def test_no_wheels_found_is_not_measured_never_pass():
    src, res, reg = load("m2_studio", "g4_crop_jacket")
    bare = regions.Regions(reg.shape, "auto", reg.face, [], [], [])
    rep = checks.run_checks(src, res, bare)
    assert rep.verdict == "warn"
    assert {c.id: c.status for c in rep.checks}["clearance"] == "not_measured"


def test_saved_matrix_is_complete_and_consistent():
    m = json.loads((PROOF / "matrix.json").read_text(encoding="utf-8"))
    assert m["cells_total"] == len(m["cells"]) == sum(m["counts"].values())
    assert m["thresholds"] == checks.THRESHOLDS
    for c in m["cells"]:
        if c["verdict"] != "no_render":
            assert c["alt"] and (PROOF / "web" / "overlays" / c["web"]).exists()
