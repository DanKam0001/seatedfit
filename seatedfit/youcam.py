"""YouCam AI Clothes client: upload, create task, poll, download.

Every network call is written to a JSONL ledger. Task creation is refused once
the ledger holds `task_cap` created tasks, so a bug cannot spend without limit.
Signed URLs and the token are never logged.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

DEFAULT_BASE = "https://yce-api-01.makeupar.com"
TASK_PATH = "/s2s/v2.0/task/cloth-v4"
FILE_PATH = "/s2s/v2.0/file"

# Worth retrying. Everything else is a fact about the input or the account.
TRANSIENT_HTTP = {408, 429, 500, 502, 503, 504}
TRANSIENT_ERRORS = {"unknown_internal_error", "error_download_image"}
# Stop the whole run, not just this task.
OUT_OF_UNITS_HINTS = ("unit", "credit", "quota", "balance", "insufficient")


class YouCamError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


class SpendStop(YouCamError):
    """Budget or task cap reached: callers must stop calling."""


@dataclass
class TryOn:
    image: bytes
    task_id: str
    seconds: float


def _looks_out_of_units(status: int, text: str) -> bool:
    if status == 402:
        return True
    low = text.lower()
    return status in (400, 403) and any(h in low for h in OUT_OF_UNITS_HINTS)


class YouCamClient:
    def __init__(self, token=None, base_url=None, ledger: Path | None = None, task_cap=120,
                 session=None, poll_seconds=3.0, poll_timeout=180.0, sleep=time.sleep):
        self.token = token or os.environ.get("YOURCAM_API_KEY", "")
        self.base = (base_url or os.environ.get("YOUCAM_BASE_URL") or DEFAULT_BASE).rstrip("/")
        self.ledger = Path(ledger) if ledger else None
        self.task_cap = task_cap
        self.http = session or requests.Session()
        self.poll_seconds = poll_seconds
        self.poll_timeout = poll_timeout
        self.sleep = sleep
        self._files: dict[str, str] = {}

    # ledger ---------------------------------------------------------------
    def _log(self, **row):
        if not self.ledger:
            return
        row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **row}
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def tasks_used(self) -> int:
        if not self.ledger or not self.ledger.exists():
            return 0
        rows = (json.loads(x) for x in self.ledger.read_text(encoding="utf-8").splitlines() if x.strip())
        return sum(1 for r in rows if r.get("call") == "task_create" and r.get("task_id"))

    # http -----------------------------------------------------------------
    @property
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _api(self, method, path, label, ctx, **kw):
        last = None
        for attempt in range(3):
            try:
                r = self.http.request(method, self.base + path, headers=self._headers, timeout=60, **kw)
            except requests.RequestException as e:
                self._log(call=label, attempt=attempt, error_code="network", detail=type(e).__name__, **ctx)
                last = YouCamError("network", type(e).__name__)
                self.sleep(2 ** attempt)
                continue
            text = r.text[:400]
            if _looks_out_of_units(r.status_code, text):
                self._log(call=label, attempt=attempt, http=r.status_code, error_code="out_of_units", detail=text, **ctx)
                raise SpendStop("out_of_units", text)
            if r.status_code in TRANSIENT_HTTP:
                self._log(call=label, attempt=attempt, http=r.status_code, error_code="transient_http", detail=text, **ctx)
                last = YouCamError(f"http_{r.status_code}", text)
                self.sleep(2 ** attempt)
                continue
            if r.status_code != 200:
                code = _error_code(r) or f"http_{r.status_code}"
                self._log(call=label, attempt=attempt, http=r.status_code, error_code=code, detail=text, **ctx)
                raise YouCamError(code, text)
            if label != "task_create":  # that row is written with its task_id by create_task
                self._log(call=label, attempt=attempt, http=200, **ctx)
            return r.json()
        raise last

    def upload(self, path: Path, ctx=None) -> str:
        path = Path(path)
        key = str(path.resolve())
        if key in self._files:
            return self._files[key]
        file_id = self.upload_bytes(path.read_bytes(), path.name, ctx)
        self._files[key] = file_id
        return file_id

    def upload_bytes(self, data: bytes, name: str, ctx=None) -> str:
        ctx = ctx or {}
        ctype = "image/png" if name.lower().endswith(".png") else "image/jpeg"
        body = {"files": [{"content_type": ctype, "file_name": name, "file_size": len(data)}]}
        j = self._api("POST", FILE_PATH, "file_create", ctx, json=body)
        entry = j["data"]["files"][0]
        req = entry["requests"][0]
        put = self.http.put(req["url"], headers=req.get("headers") or {"Content-Type": ctype}, data=data, timeout=120)
        self._log(call="file_put", http=put.status_code, file=name, bytes=len(data), **ctx)
        if put.status_code not in (200, 201, 204):
            raise YouCamError(f"upload_http_{put.status_code}")
        return entry["file_id"]

    def create_task(self, src_id: str, ref_id: str, category: str, ctx=None) -> str:
        ctx = ctx or {}
        used = self.tasks_used()
        if used >= self.task_cap:
            self._log(call="task_refused_cap", used=used, **ctx)
            raise SpendStop("task_cap", f"{used} tasks already created")
        body = {"src_file_id": src_id, "ref_file_id": ref_id, "garment_category": category}
        j = self._api("POST", TASK_PATH, "task_create", ctx, json=body)
        task_id = j["data"]["task_id"]
        self._log(call="task_create", http=200, task_id=task_id, **{"category": category, **ctx})
        return task_id

    def wait(self, task_id: str, ctx=None) -> str:
        ctx = ctx or {}
        waited = 0.0
        while waited < self.poll_timeout:
            self.sleep(self.poll_seconds)
            waited += self.poll_seconds
            j = self._api("GET", f"{TASK_PATH}/{task_id}", "task_poll", ctx)
            data = j.get("data") or {}
            status = data.get("task_status")
            if status == "success":
                self._log(call="task_done", task_id=task_id, task_status=status, waited=waited, **ctx)
                return data["results"]["url"]
            if status in ("error", "failed"):
                code = data.get("error") or "task_error"
                self._log(call="task_done", task_id=task_id, task_status=status, error_code=code,
                          detail=str(data.get("error_message", ""))[:300], waited=waited, **ctx)
                raise YouCamError(str(code), str(data.get("error_message", "")))
        self._log(call="task_done", task_id=task_id, task_status="timeout", error_code="poll_timeout", **ctx)
        raise YouCamError("poll_timeout")

    def try_on(self, src: Path | bytes, ref: Path, category: str, ctx=None, src_name="photo.jpg") -> TryOn:
        ctx = ctx or {}
        t0 = time.time()
        src_id = self.upload_bytes(src, src_name, ctx) if isinstance(src, bytes) else self.upload(src, ctx)
        ref_id = self.upload(ref, ctx)
        task_id = self.create_task(src_id, ref_id, category, ctx)
        url = self.wait(task_id, ctx)
        got = self.http.get(url, timeout=120)
        self._log(call="result_get", http=got.status_code, task_id=task_id, bytes=len(got.content), **ctx)
        if got.status_code != 200:
            raise YouCamError(f"download_http_{got.status_code}")
        return TryOn(got.content, task_id, round(time.time() - t0, 1))


def _error_code(r) -> str | None:
    try:
        j = r.json()
    except ValueError:
        return None
    return j.get("error_code") or j.get("error")
