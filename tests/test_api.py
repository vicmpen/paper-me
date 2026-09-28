import json

import pytest
from fastapi.testclient import TestClient

from webapp import app as app_module
from webapp import runner, scheduler
from webapp.db import AgentInput
from webapp.search_agent import FoundItem


@pytest.fixture
def client(tmp_db, monkeypatch):
    for name in ("start", "shutdown", "sync_jobs"):
        monkeypatch.setattr(scheduler, name, lambda: None)
    with TestClient(app_module.app, base_url="http://127.0.0.1") as c:
        yield c


def make_agent(db, name="Oil"):
    return db.create_agent(AgentInput(name=name, query="oil prices", domain_mode="none",
                                      domains=[], lookback_days=7, max_searches=5,
                                      schedule_time=None))


def finished_run(db, aid, **over):
    rid, _ = db.create_run(aid, "manual")
    base = dict(status="succeeded", error=None, input_tokens=0, output_tokens=0, searches=1,
                items=[], answer="An answer.", edition="composed")
    base.update(over)
    db.finish_run(rid, **base)
    return rid


def parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        fields = {}
        for line in block.splitlines():
            if line.startswith(":"):
                continue
            key, _, value = line.partition(":")
            fields[key] = value[1:] if value.startswith(" ") else value
        if fields:
            events.append((fields.get("event"), fields.get("data")))
    return events


def test_paper_json(client, tmp_db):
    aid = make_agent(tmp_db)
    old = finished_run(tmp_db, aid)
    live, _ = tmp_db.create_run(aid, "manual")
    body = client.get(f"/api/agents/{aid}/paper").json()
    assert body["agent"] == {"id": aid, "name": "Oil", "query": "oil prices"}
    assert body["current_run_id"] == live
    assert [e["run_id"] for e in body["editions"]] == [live, old]
    assert body["editions"][1] == {"run_id": old, "started_at": body["editions"][1]["started_at"],
                                   "finished_at": body["editions"][1]["finished_at"],
                                   "status": "succeeded", "edition": "composed", "error": None,
                                   "answer": "An answer."}


def test_paper_current_run_is_latest_succeeded_or_null(client, tmp_db):
    aid = make_agent(tmp_db)
    assert client.get(f"/api/agents/{aid}/paper").json()["current_run_id"] is None
    good = finished_run(tmp_db, aid)
    finished_run(tmp_db, aid, status="failed", error="x", edition=None)
    assert client.get(f"/api/agents/{aid}/paper").json()["current_run_id"] == good


def test_paper_404(client):
    assert client.get("/api/agents/999/paper").status_code == 404


def test_sources_are_numbered(client, tmp_db):
    aid = make_agent(tmp_db)
    rid = finished_run(tmp_db, aid, items=[
        FoundItem(title="T1", url="https://a.com/1", source="a.com", published="2026-09-26", summary="s1"),
        FoundItem(title="T2", url="https://b.com/2", source="b.com", published="", summary="s2")])
    body = client.get(f"/api/runs/{rid}/sources").json()
    assert body[0] == {"n": 1, "title": "T1", "url": "https://a.com/1", "source": "a.com",
                       "published": "2026-09-26", "summary": "s1", "seen_before": False}
    assert [s["n"] for s in body] == [1, 2]
    assert client.get("/api/runs/999/sources").status_code == 404


def test_go_to_press_starts_a_run(client, tmp_db, monkeypatch):
    aid = make_agent(tmp_db)
    monkeypatch.setattr(runner, "start_run", lambda agent_id, kind: 42)
    r = client.post(f"/api/agents/{aid}/run")
    assert r.status_code == 200 and r.json() == {"run_id": 42}
    assert client.post("/api/agents/999/run").status_code == 404


def test_go_to_press_rejects_cross_site(client, tmp_db, monkeypatch):
    aid = make_agent(tmp_db)
    monkeypatch.setattr(runner, "start_run", lambda agent_id, kind: pytest.fail("must not start"))
    r = client.post(f"/api/agents/{aid}/run", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_stream_sends_raw_patch_lines_and_json_events(client, tmp_db):
    aid = make_agent(tmp_db)
    rid, _ = tmp_db.create_run(aid, "manual")
    line = '{"op":"add","path":"/root","value":"page"}'
    tmp_db.append_edition_lines(rid, [line])
    tmp_db.finish_run(rid, status="succeeded", error=None, input_tokens=0, output_tokens=0,
                      searches=0, items=[], edition="composed")
    r = client.get(f"/api/runs/{rid}/edition/stream")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    assert [kind for kind, _ in events] == ["status", "reset", "patch", "done"]
    assert events[2][1] == line                   # raw, not JSON-quoted
    assert json.loads(events[1][1]) == {}
    assert json.loads(events[3][1]) == {"status": "succeeded", "edition": "composed", "error": None}


def test_stream_404_for_unknown_run(client):
    assert client.get("/api/runs/999/edition/stream").status_code == 404


def test_spa_serves_index_for_client_routes(client, tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><div id=root></div>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setattr(app_module, "_DIST", tmp_path)
    # StaticFiles resolves its directory at startup; point it at the test build.
    monkeypatch.setattr(app_module._paper_assets, "all_directories", [tmp_path / "assets"])
    # Its first request also checks the real directory, which a clean checkout lacks.
    monkeypatch.setattr(app_module._paper_assets, "directory", tmp_path / "assets")
    monkeypatch.setattr(app_module._paper_assets, "config_checked", False)
    for path in ("/paper/3", "/paper/3/10", "/paper/styleguide"):
        r = client.get(path)
        assert r.status_code == 200 and "id=root" in r.text
    assert client.get("/paper/assets/app.js").text == "console.log(1)"


def test_spa_503_when_frontend_not_built(client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "_DIST", tmp_path / "missing")
    r = client.get("/paper/3")
    assert r.status_code == 503 and r.text == "Frontend not built: run npm run build"


def test_agent_page_links_to_the_paper(client, tmp_db):
    aid = make_agent(tmp_db)
    assert f'href="/paper/{aid}"' in client.get(f"/agents/{aid}").text
