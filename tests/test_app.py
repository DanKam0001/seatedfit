import io
import json
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from seatedfit import app as server
from seatedfit import regions, tone
from seatedfit.catalogue import GARMENTS, MODELS, model_path
from seatedfit.youcam import SpendStop, TryOn, YouCamError

api = TestClient(server.app)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_CAP_FILE", str(tmp_path / "cap.json"))
    monkeypatch.setenv("LIVE_DAILY_CAP", "2")


def jpeg(path=None, rgb=None):
    buf = io.BytesIO()
    (Image.open(path).convert("RGB") if path else Image.fromarray(rgb)).save(buf, "JPEG")
    return buf.getvalue()


class FakeClient:
    calls = 0

    def try_on(self, src, ref, category, ctx, src_name):
        FakeClient.calls += 1
        return TryOn(src, "t", 1.0)  # the unchanged photo: must not pass


def test_health():
    r = api.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["saved_cells"] > 0


def test_index_and_assets_served():
    assert "SeatedFit" in api.get("/").text
    assert api.get("/static/app.js").status_code == 200
    assert api.get("/media/models/m2_studio.jpg").status_code == 200


def test_page_says_synthetic_and_states_limits():
    t = api.get("/").text
    assert "AI-generated" in t and "not how it truly fits" in t and "not been tested with wheelchair users" in t
    assert "5.5 million" not in t


def test_gallery_holds_only_approved():
    z = zipfile.ZipFile(io.BytesIO(api.get("/api/gallery.zip").content))
    names = set(z.namelist()) - {"descriptions.json"}
    m = api.get("/api/matrix").json()
    assert names == {f"{c['model']}__{c['garment']}.jpg" for c in m["cells"] if c["verdict"] == "pass"}


def test_photo_check_accepts_sample():
    r = api.post("/api/photo-check", files={"photo": ("a.jpg", jpeg(model_path("m2_studio")), "image/jpeg")})
    assert r.status_code == 200 and r.json()["ok"] is True


def test_photo_check_refuses_empty_scene():
    blank = np.full((900, 900, 3), 200, np.uint8)
    r = api.post("/api/photo-check", files={"photo": ("a.jpg", jpeg(rgb=blank), "image/jpeg")})
    assert r.json()["ok"] is False


def test_non_image_refused():
    r = api.post("/api/photo-check", files={"photo": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 415


def test_oversize_refused():
    r = api.post("/api/photo-check", files={"photo": ("a.jpg", b"0" * (server.MAX_UPLOAD + 1), "image/jpeg")})
    assert r.status_code == 413


def test_unknown_garment():
    r = api.post("/api/tryon", data={"garment": "nope"}, files={"photo": ("a.jpg", b"x", "image/jpeg")})
    assert r.status_code == 404


def post_tryon():
    return api.post("/api/tryon", data={"garment": "g4_crop_jacket"},
                    files={"photo": ("a.jpg", jpeg(model_path("m2_studio")), "image/jpeg")}).json()


def test_daily_cap_falls_back_to_saved(monkeypatch):
    FakeClient.calls = 0
    monkeypatch.setattr(server, "live_client", FakeClient)
    assert post_tryon()["mode"] == "live"
    assert post_tryon()["mode"] == "live"
    r = post_tryon()
    assert r["mode"] == "fallback" and "saved" in r["message"] and FakeClient.calls == 2


def test_unchanged_upload_is_refused_and_image_withheld(monkeypatch):
    monkeypatch.setattr(server, "live_client", FakeClient)
    r = post_tryon()
    assert r["verdict"] == "fail" and "render" not in r


def test_no_key_falls_back(monkeypatch):
    monkeypatch.setattr(server, "live_client", lambda: None)
    assert post_tryon()["mode"] == "fallback"


def test_spend_stop_falls_back(monkeypatch):
    class Broke(FakeClient):
        def try_on(self, *a, **k):
            raise SpendStop("out_of_units")
    monkeypatch.setattr(server, "live_client", Broke)
    assert post_tryon()["mode"] == "fallback"


def test_upload_never_written_to_disk(monkeypatch, tmp_path):
    before = {p for p in server.PROOF.rglob("*") if p.is_file()}
    monkeypatch.setattr(server, "live_client", FakeClient)
    post_tryon()
    assert {p for p in server.PROOF.rglob("*") if p.is_file()} == before


def test_key_never_reaches_a_response(monkeypatch):
    monkeypatch.setenv("YOURCAM_API_KEY", "sk-canary")
    assert "sk-canary" not in json.dumps(api.get("/api/catalogue").json())


# Read off the sample by eye, in the page's own units. regions.json plays no part.
WHEELS = [{"kind": "wheel", "x": .352, "y": .732, "w": .045, "h": .28}, {"kind": "wheel", "x": .645, "y": .73, "w": .045, "h": .28}]


def saved_check(garment, wheels=WHEELS):
    data = {"garment": garment, "sample": "m2_studio"}
    if wheels:
        data["wheels"] = json.dumps(wheels)
    return api.post("/api/tryon", data=data)


@pytest.fixture
def no_marks_file(monkeypatch, tmp_path):
    monkeypatch.setattr(regions, "MARKS", tmp_path / "gone.json")


def test_marked_wheels_give_real_verdicts_with_no_hand_marks_and_no_key(monkeypatch, no_marks_file):
    monkeypatch.delenv("YOURCAM_API_KEY", raising=False)
    long = saved_check("g1_long_wool_coat").json()
    short = saved_check("g4_crop_jacket").json()
    assert long["verdict"] == "fail" and "render" not in long and long["saved"] is True
    assert short["verdict"] == "pass" and "render" in short
    assert {c["status"] for c in short["checks"]} == {"pass"}
    assert "Hands were not compared" in next(c for c in short["checks"] if c["id"] == "person")["message"]


def test_no_marks_stays_not_measured():
    r = saved_check("g4_crop_jacket", None).json()
    assert r["verdict"] == "warn"
    assert {c["id"]: c["status"] for c in r["checks"]}["clearance"] == "not_measured"


def test_marks_on_a_bare_wall_cannot_pass():
    wall = [{"kind": "wheel", "x": .12, "y": .25, "w": .045, "h": .28}]
    r = saved_check("g4_crop_jacket", wall).json()
    clr = next(c for c in r["checks"] if c["id"] == "clearance")
    assert r["verdict"] == "warn" and clr["status"] == "warn" and "Check your marks" in clr["message"]


@pytest.mark.parametrize("bad", [
    "not json", "[]", "[1]", json.dumps([{"kind": "caster", "x": .5, "y": .5, "w": .1, "h": .1}]),
    json.dumps([{"kind": "wheel", "x": 2, "y": .5, "w": .1, "h": .1}]),
    json.dumps([{"kind": "wheel", "x": .5, "y": .5, "w": .001, "h": .1}]),
    json.dumps([{"kind": "hat", "x": .5, "y": .5, "w": .1, "h": .1}, WHEELS[0]]),
    json.dumps(WHEELS * 4),
])
def test_bad_marks_refused(bad):
    assert api.post("/api/tryon", data={"garment": "g4_crop_jacket", "sample": "m2_studio", "wheels": bad}).status_code == 422


def test_saved_path_spends_nothing(monkeypatch):
    def boom():
        raise AssertionError("the saved path must not make a client")
    monkeypatch.setattr(server, "live_client", boom)
    assert saved_check("g4_crop_jacket").json()["mode"] == "live"


def test_rotated_upload_is_checked_upright():
    buf = io.BytesIO()
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees to show
    Image.new("RGB", (40, 20)).save(buf, "JPEG", exif=exif)
    assert server._decode(buf.getvalue()).shape[:2] == (40, 20)


def test_tone_saved_for_every_sample_with_no_key(monkeypatch):
    monkeypatch.delenv("YOURCAM_API_KEY", raising=False)
    for m in MODELS:
        j = api.get(f"/api/tone/{m}").json()
        assert j["skin"].startswith("#") and len(j["garments"]) == len(GARMENTS)
        got = [g["contrast"] for g in j["garments"]]
        assert got == sorted(got, reverse=True)
    assert api.get("/api/tone/m2_studio").json()["source"] == "youcam"
    assert api.get("/api/tone/m1_studio").json()["source"] == "local"
    assert api.get("/api/tone/nope").status_code == 404


def test_contrast_is_plain_colour_distance():
    r = {x["garment"]: x["contrast"] for x in tone.rank("#ededee")}
    assert r["g5_shirt"] < 1 and r["g4_crop_jacket"] > 50


class ToneClient:
    calls = 0
    sent = b""

    def skin_tone(self, jpeg, ctx):
        ToneClient.calls += 1
        ToneClient.sent = jpeg
        return {"skin_color": "#74523c"}


def post_tone():
    return api.post("/api/tone", files={"photo": ("a.jpg", jpeg(model_path("m2_studio")), "image/jpeg")}).json()


def test_tone_upload_has_its_own_cap_and_sends_only_the_face(monkeypatch):
    ToneClient.calls = 0
    monkeypatch.setenv("LIVE_TONE_DAILY_CAP", "1")
    monkeypatch.setattr(server, "live_client", ToneClient)
    assert post_tone()["source"] == "youcam"
    side = Image.open(io.BytesIO(ToneClient.sent)).size
    assert side == (640, 640) and ToneClient.calls == 1
    assert post_tone()["source"] == "local" and ToneClient.calls == 1
    assert server._used_today() == 0  # a tone reading doesn't eat a try-on slot


def test_tone_failure_falls_back_to_local(monkeypatch):
    class Bad(ToneClient):
        def skin_tone(self, jpeg, ctx):
            raise YouCamError("error_face_position_invalid")
    monkeypatch.setattr(server, "live_client", Bad)
    r = post_tone()
    assert r["source"] == "local" and r["error"] == "error_face_position_invalid"


def test_tone_with_no_face_is_refused():
    blank = np.full((900, 900, 3), 200, np.uint8)
    assert api.post("/api/tone", files={"photo": ("a.jpg", jpeg(rgb=blank), "image/jpeg")}).status_code == 422


def test_page_says_contrast_is_not_style():
    assert "not a style judgement" in api.get("/").text
    assert "not a style judgement" in api.get("/static/app.js").text
