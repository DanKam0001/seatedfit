import io
import json
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from seatedfit import app as server
from seatedfit.catalogue import model_path
from seatedfit.youcam import SpendStop, TryOn

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
