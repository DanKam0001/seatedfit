"""The client against a fake server: no test here reaches the network."""
import json

import pytest
import requests

from seatedfit.youcam import SpendStop, YouCamClient, YouCamError


class Resp:
    def __init__(self, status=200, body=None, content=b"img"):
        self.status_code, self._body, self.content = status, body or {}, content
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


class Fake:
    """Answers the upload, task and poll calls; `script` overrides task creation."""

    def __init__(self, script=None, polls=None):
        self.script, self.polls, self.creates = list(script or []), list(polls or []), 0

    def request(self, method, url, headers=None, timeout=None, json=None):
        assert headers["Authorization"] == "Bearer tok"
        if "/file" in url:
            return Resp(body={"data": {"files": [{"file_id": "f1", "requests": [{"url": "https://put", "headers": {}}]}]}})
        if method == "POST":
            self.creates += 1
            if self.script:
                r = self.script.pop(0)
                if isinstance(r, Exception):
                    raise r
                return r
            return Resp(body={"data": {"task_id": f"t{self.creates}"}})
        if self.polls:
            return self.polls.pop(0)
        return Resp(body={"data": {"task_status": "success", "results": {"url": "https://signed/secret?sig=abc"}}})

    def put(self, url, headers=None, data=None, timeout=None):
        return Resp()

    def get(self, url, timeout=None):
        return Resp(content=b"jpeg")


def client(tmp_path, fake, cap=120):
    return YouCamClient("tok", "https://api", tmp_path / "l.jsonl", cap, fake, sleep=lambda s: None)


def rows(tmp_path):
    return [json.loads(x) for x in (tmp_path / "l.jsonl").read_text().splitlines()]


def test_full_flow_and_ledger_holds_no_secrets(tmp_path):
    r = client(tmp_path, Fake()).try_on(b"src", _ref(tmp_path), "full_body", {"model": "m"})
    assert r.image == b"jpeg" and r.task_id == "t1"
    text = (tmp_path / "l.jsonl").read_text()
    assert "tok" not in text and "sig=abc" not in text
    assert [x["call"] for x in rows(tmp_path)].count("task_create") == 1


def _ref(tmp_path):
    p = tmp_path / "g.jpg"
    p.write_bytes(b"x")
    return p


def test_task_cap_refuses_before_spending(tmp_path):
    fake = Fake()
    c = client(tmp_path, fake, cap=2)
    c.create_task("a", "b", "full_body")
    c.create_task("a", "b", "full_body")
    with pytest.raises(SpendStop):
        c.create_task("a", "b", "full_body")
    assert fake.creates == 2


def test_402_stops_without_retry(tmp_path):
    fake = Fake([Resp(402, {"error": "over budget"})])
    with pytest.raises(SpendStop):
        client(tmp_path, fake).create_task("a", "b", "full_body")
    assert fake.creates == 1


def test_out_of_units_text_stops(tmp_path):
    with pytest.raises(SpendStop):
        client(tmp_path, Fake([Resp(403, {"error": "insufficient credit"})])).create_task("a", "b", "full_body")


def test_transient_is_retried_and_recorded(tmp_path):
    fake = Fake([Resp(503), requests.ConnectionError()])
    assert client(tmp_path, fake).create_task("a", "b", "full_body") == "t3"
    codes = [x.get("error_code") for x in rows(tmp_path)]
    assert "transient_http" in codes and "network" in codes


def test_input_error_is_not_retried(tmp_path):
    fake = Fake([Resp(400, {"error": "error_no_person"})])
    with pytest.raises(YouCamError) as e:
        client(tmp_path, fake).create_task("a", "b", "full_body")
    assert e.value.code == "error_no_person" and fake.creates == 1


def test_failed_task_records_its_code(tmp_path):
    fake = Fake(polls=[Resp(body={"data": {"task_status": "error", "error": "error_pose"}})])
    with pytest.raises(YouCamError):
        client(tmp_path, fake).wait("t1")
    assert rows(tmp_path)[-1]["error_code"] == "error_pose"


class ToneFake(Fake):
    def request(self, method, url, headers=None, timeout=None, json=None):
        self.last = (method, url, json)
        if method == "GET":
            return Resp(body={"data": {"task_status": "success", "results": {"color": {"skin_color": "#74523c"}}}})
        return super().request(method, url, headers, timeout, json)


def test_skin_tone_uses_its_own_paths_and_counts_against_the_cap(tmp_path):
    fake = ToneFake()
    got = client(tmp_path, fake).skin_tone(b"face", {"model": "m"})
    assert got["skin_color"] == "#74523c" and "/task/skin-tone-analysis/" in fake.last[1]
    made = [r for r in rows(tmp_path) if r["call"] == "task_create"]
    assert len(made) == 1 and made[0]["units"] == 20
    with pytest.raises(SpendStop):
        client(tmp_path, ToneFake(), cap=1).skin_tone(b"face")


def test_skin_tone_failure_raises(tmp_path):
    bad = Resp(body={"data": {"task_status": "error", "error": "error_face_position_too_small"}})
    with pytest.raises(YouCamError) as e:
        client(tmp_path, Fake(polls=[bad])).skin_tone(b"face")
    assert e.value.code == "error_face_position_too_small"


def test_missing_skin_colour_is_an_error(tmp_path):
    with pytest.raises(YouCamError):
        client(tmp_path, Fake(polls=[Resp(body={"data": {"task_status": "success", "results": {"color": {}}}})])).skin_tone(b"f")
