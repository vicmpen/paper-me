import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["WEBAPP_DISABLE_SCHEDULER"] = "1"


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    from webapp import db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db.init_db()
    return db


import json as _json


class FakeResponse:
    def __init__(self, status=200, payload=None, text=None):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._payload = payload
        self.text = text if text is not None else _json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("not JSON")
        return self._payload


class FakePost:
    """Stands in for requests.post. Call .respond(...) or set .exc before use."""

    def __init__(self):
        self.calls = []
        self.response = FakeResponse(200, {"results": []})
        self.exc = None

    def respond(self, status=200, payload=None, text=None):
        self.response = FakeResponse(status, payload, text)

    def __call__(self, url, *, headers, json, timeout):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if self.exc is not None:
            raise self.exc
        return self.response


@pytest.fixture
def fake_post(monkeypatch):
    import requests
    fake = FakePost()
    monkeypatch.setattr(requests, "post", fake)
    return fake
