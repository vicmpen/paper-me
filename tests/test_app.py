import pytest
from fastapi.testclient import TestClient

from webapp import app as app_module
from webapp import runner, scheduler
from webapp.db import AgentInput


@pytest.fixture
def client(tmp_db, monkeypatch):
    for name in ("start", "shutdown", "sync_jobs"):
        monkeypatch.setattr(scheduler, name, lambda: None)
    with TestClient(app_module.app, base_url="http://127.0.0.1") as c:
        yield c


def form(**over):
    base = {"name": "Space", "query": "launch news", "domain_mode": "include",
            "domains": "spacenews.com", "lookback_days": "7", "max_searches": "5",
            "schedule_time": ""}
    base.update(over)
    return base


def make_agent(db, **over):
    base = dict(name="A", query="q", domain_mode="none", domains=[],
                lookback_days=7, max_searches=5, schedule_time=None)
    base.update(over)
    return db.create_agent(AgentInput(**base))


def test_index_empty(client):
    r = client.get("/")
    assert r.status_code == 200 and "New agent" in r.text


def test_create_agent_flow(client, tmp_db):
    r = client.post("/agents", data=form(), follow_redirects=False)
    assert r.status_code == 303
    aid = int(r.headers["location"].rsplit("/", 1)[1])
    assert tmp_db.get_agent(aid).domains == ["spacenews.com"]
    page = client.get(f"/agents/{aid}")
    assert page.status_code == 200 and "Space" in page.text and "No runs yet" in page.text
    assert "Space" in client.get("/").text


def test_create_agent_invalid_rerenders(client, tmp_db):
    r = client.post("/agents", data=form(name="", domains="localhost"))
    assert r.status_code == 422
    assert "launch news" in r.text  # submitted values preserved
    assert tmp_db.list_agents() == []


def test_create_agent_missing_fields_is_form_error_not_json(client):
    r = client.post("/agents", data={"name": "x"})
    assert r.status_code == 422 and "text/html" in r.headers["content-type"]


def test_edit_and_delete(client, tmp_db):
    aid = make_agent(tmp_db)
    assert client.get(f"/agents/{aid}/edit").status_code == 200
    r = client.post(f"/agents/{aid}", data=form(name="Renamed"), follow_redirects=False)
    assert r.status_code == 303 and tmp_db.get_agent(aid).name == "Renamed"
    r = client.post(f"/agents/{aid}/delete", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert tmp_db.get_agent(aid) is None


def test_run_now_redirect_and_htmx(client, tmp_db, monkeypatch):
    aid = make_agent(tmp_db)
    def fake_start(agent_id, kind):
        rid, _ = tmp_db.create_run(agent_id, kind)
        return rid
    monkeypatch.setattr(runner, "start_run", fake_start)
    r = client.post(f"/agents/{aid}/run", follow_redirects=False)
    assert r.status_code == 303
    r = client.post(f"/agents/{aid}/run", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert 'id="run-status"' in r.text and 'hx-trigger="every 2s"' in r.text


def test_status_partial_finished_sets_refresh(client, tmp_db):
    aid = make_agent(tmp_db)
    rid, _ = tmp_db.create_run(aid, "manual")
    r = client.get(f"/runs/{rid}/status")
    assert "every 2s" in r.text and "HX-Refresh" not in r.headers
    tmp_db.finish_run(rid, status="failed", error="RuntimeError: boom", input_tokens=0,
                      output_tokens=0, searches=0, items=[])
    r = client.get(f"/runs/{rid}/status")
    assert r.headers.get("HX-Refresh") == "true" and "hx-get" not in r.text
    assert "boom" in r.text


def test_item_title_escaped(client, tmp_db):
    from types import SimpleNamespace
    aid = make_agent(tmp_db)
    rid, _ = tmp_db.create_run(aid, "manual")
    evil = SimpleNamespace(title="<script>alert(1)</script>", url="https://a.com/x",
                           source="S", published="", summary="s")
    tmp_db.finish_run(rid, status="succeeded", error=None, input_tokens=0, output_tokens=0,
                      searches=1, items=[evil])
    for path in (f"/agents/{aid}", f"/runs/{rid}"):
        body = client.get(path).text
        assert "<script>alert(1)</script>" not in body
        assert "&lt;script&gt;" in body
        assert "a.com" in body  # real hostname shown


def test_seen_before_rendered_dimmed(client, tmp_db):
    from types import SimpleNamespace
    aid = make_agent(tmp_db)
    it = SimpleNamespace(title="T", url="https://a.com/x", source="S", published="", summary="s")
    for _ in range(2):
        rid, _ = tmp_db.create_run(aid, "manual")
        tmp_db.finish_run(rid, status="succeeded", error=None, input_tokens=0, output_tokens=0,
                          searches=1, items=[it])
    assert "seen before" in client.get(f"/agents/{aid}").text


def test_empty_results_message(client, tmp_db):
    aid = make_agent(tmp_db)
    rid, _ = tmp_db.create_run(aid, "manual")
    tmp_db.finish_run(rid, status="succeeded", error=None, input_tokens=0, output_tokens=0,
                      searches=1, items=[])
    assert "No matching news found" in client.get(f"/agents/{aid}").text


@pytest.mark.parametrize("path", ["/agents/999", "/agents/999/edit", "/runs/999"])
def test_404s(client, path):
    assert client.get(path).status_code == 404


def test_run_missing_agent_404(client, monkeypatch):
    def missing(agent_id, kind):
        raise LookupError(agent_id)
    monkeypatch.setattr(runner, "start_run", missing)
    assert client.post("/agents/999/run").status_code == 404


def test_foreign_host_rejected(client):
    assert client.get("/", headers={"Host": "evil.example:8000"}).status_code == 400


@pytest.mark.parametrize("headers", [
    {"Origin": "https://evil.example"},
    {"Sec-Fetch-Site": "cross-site"},
])
def test_cross_site_post_rejected(client, tmp_db, headers):
    r = client.post("/agents", data=form(), headers=headers, follow_redirects=False)
    assert r.status_code == 403 and tmp_db.list_agents() == []


def test_same_origin_post_allowed(client, tmp_db):
    r = client.post("/agents", data=form(), follow_redirects=False,
                    headers={"Origin": "http://127.0.0.1:8000", "Sec-Fetch-Site": "same-origin"})
    assert r.status_code == 303


def test_status_of_deleted_run_redirects_home(client):
    r = client.get("/runs/999/status")
    assert r.status_code == 200 and r.headers.get("HX-Redirect") == "/"


def _finished_run(db, aid, items, answer=None, provider=None):
    rid, _ = db.create_run(aid, "manual")
    db.finish_run(rid, status="succeeded", error=None, input_tokens=0, output_tokens=0,
                  searches=1, items=items, answer=answer, provider=provider)
    return rid


def _item(title, url, source):
    from types import SimpleNamespace
    return SimpleNamespace(title=title, url=url, source=source, published="", summary="s")


def test_response_instructions_round_trip(client, tmp_db):
    r = client.post("/agents", data=form(response_instructions="Two sentences."),
                    follow_redirects=False)
    aid = int(r.headers["location"].rsplit("/", 1)[1])
    assert tmp_db.get_agent(aid).response_instructions == "Two sentences."
    assert "Two sentences." in client.get(f"/agents/{aid}/edit").text
    assert "Two sentences." in client.get(f"/agents/{aid}").text
    client.post(f"/agents/{aid}", data=form(response_instructions=""), follow_redirects=False)
    assert tmp_db.get_agent(aid).response_instructions == ""
    assert "default briefing" in client.get(f"/agents/{aid}").text


def test_new_agent_form_has_instructions_field(client):
    body = client.get("/agents/new").text
    assert 'name="response_instructions"' in body and "How should the response look?" in body


def test_instructions_too_long_rerenders(client, tmp_db):
    r = client.post("/agents", data=form(response_instructions="x" * 2001))
    assert r.status_code == 422 and "2000 characters or fewer" in r.text
    assert tmp_db.list_agents() == []


def test_answer_rendered_escaped_with_citations(client, tmp_db):
    aid = make_agent(tmp_db)
    items = [_item("First", "https://a.com/1", "a.com"), _item("Second", "https://b.com/2", "B News")]
    rid = _finished_run(tmp_db, aid, items, answer="<script>alert(1)</script> see [1]",
                        provider="exa")
    for path in (f"/agents/{aid}", f"/runs/{rid}"):
        body = client.get(path).text
        assert "<script>alert(1)</script>" not in body
        assert "&lt;script&gt;alert(1)&lt;/script&gt; see [1]" in body
        assert '<span class="cite">[1]</span>' in body and '<span class="cite">[2]</span>' in body
        assert "B News" in body
        assert body.count(">a.com<") == 1  # source equal to the hostname is not repeated
    assert "<dd>exa</dd>" in client.get(f"/runs/{rid}").text


def test_no_sources_message_with_answer(client, tmp_db):
    aid = make_agent(tmp_db)
    _finished_run(tmp_db, aid, [], answer="Nothing relevant this week.", provider="exa")
    body = client.get(f"/agents/{aid}").text
    assert "Nothing relevant this week." in body and "No sources." in body
    assert "No matching news found" not in body


def test_old_run_without_answer_has_no_labels(client, tmp_db):
    aid = make_agent(tmp_db)
    rid = _finished_run(tmp_db, aid, [_item("Old", "https://a.com/1", "S")])
    for path in (f"/agents/{aid}", f"/runs/{rid}"):
        body = client.get(path).text
        assert 'class="cite"' not in body and "<h2>Answer</h2>" not in body
        assert "Old" in body
    assert "<dd>—</dd>" in client.get(f"/runs/{rid}").text


def test_empty_answer_hides_answer_block_keeps_labels(client, tmp_db):
    aid = make_agent(tmp_db)
    rid = _finished_run(tmp_db, aid, [_item("One", "https://a.com/1", "S")], answer="",
                        provider="exa")
    for path in (f"/agents/{aid}", f"/runs/{rid}"):
        body = client.get(path).text
        assert "<h2>Answer</h2>" not in body
        assert '<span class="cite">[1]</span>' in body


def test_partials_without_answer_in_context():
    from types import SimpleNamespace
    item = SimpleNamespace(title="T", url="https://a.com/x", source="S", published="",
                           summary="s", seen_before=False)
    items_html = app_module.templates.get_template("_items.html").render(items=[item])
    assert 'class="cite"' not in items_html and "No sources." not in items_html
    assert "Answer" not in app_module.templates.get_template("_answer.html").render()
