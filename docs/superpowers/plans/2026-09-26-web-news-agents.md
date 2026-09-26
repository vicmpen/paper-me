# Web News Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local FastAPI + HTMX web app where the user saves news agents (query + include/exclude domains + lookback + optional daily schedule), runs them via Claude's `web_search` tool, and browses results and run history.

**Architecture:** New `webapp/` package beside the existing email pipeline. SQLite (`data/webapp.db`) stores agents/runs/items; `search_agent.py` makes the Claude call; `runner.py` executes runs in background threads; `scheduler.py` (APScheduler) triggers daily runs; `app.py` serves Jinja templates with HTMX status polling.

**Tech Stack:** Python 3.13, FastAPI 0.141.1, uvicorn 0.54.0, Jinja2 3.1.6, python-multipart 0.0.32, APScheduler 3.11.3, anthropic 0.125.0, pytest 9.1.1, httpx 0.28.1, sqlite3 (stdlib), HTMX 2.x (vendored).

**Spec:** `docs/superpowers/specs/2026-09-26-web-news-agents-design.md` — the "Shared interfaces" section is binding. Every implementer reads the spec before starting.

## Global Constraints

- Model constant `WEBAPP_MODEL = "claude-sonnet-4-6"` in `config.py`; tool type `"web_search_20260209"`.
- `anthropic==0.125.0` (not 1.x). All deps pinned exactly in `requirements.txt`.
- Server binds `127.0.0.1:8000`, no `--reload`.
- DB path `data/webapp.db`; `.gitignore` has `data/webapp.db*`.
- Tests make no network calls. Scheduler disabled in tests via `WEBAPP_DISABLE_SCHEDULER=1`.
- Errors stored/displayed only via `errors.sanitize_error`.
- All HTML via Jinja autoescape; never `|safe` on model/web-derived text.
- Match repo style: module docstrings explaining *why*, `from __future__ import annotations`, plain functions + dataclasses, no ORM.
- Parallel implementers: **do not run `git commit`** — the coordinator commits after each wave. Only touch the files listed in your task.

## Review Focus

1. Deleting an agent while its run is in progress → run thread finishes without crashing the server; UI no longer lists it. (Test: `test_runner.py::test_execute_run_agent_deleted_midrun`.)
2. Clicking "Run now" twice quickly / scheduler firing during a manual run → only one running run per agent. (Test: `test_db.py::test_create_run_single_running`.)
3. Pasting domains as full URLs with `www.`, paths, mixed case, commas + newlines → normalized hostnames; pasting an IP or `localhost` → clear form error. (Tests in `test_db.py` validation block.)
4. Server restarted mid-run → run shows "failed: interrupted (server restarted)" rather than spinning forever. (Test: `test_db.py::test_init_db_marks_interrupted`.)
5. Model returns a page title containing HTML/`<script>` → rendered as text. (Test: `test_app.py::test_item_title_escaped`.)

---

## Execution waves

- **Wave 0 (coordinator, serial):** Task 0.
- **Wave 1 (parallel):** Task 1 (db), Task 2 (search_agent).
- **Wave 2 (parallel):** Task 3 (runner + scheduler), Task 4 (app + templates).
- **Wave 3 (coordinator):** Task 5 (integration, README, live smoke).

---

### Task 0: Scaffolding (coordinator)

**Files:**
- Create: `errors.py`, `webapp/__init__.py`, `webapp/__main__.py`, `webapp/runner.py` (stub), `webapp/scheduler.py` (stub), `tests/__init__.py`, `tests/conftest.py`, `webapp/static/htmx.min.js`
- Modify: `main.py` (import sanitize_error from errors), `config.py` (add WEBAPP_MODEL), `requirements.txt`, `.gitignore`

- [ ] **Step 1:** Move `_EMAIL_RE`, `_UUID_RE`, `_API_KEY_RE`, `_REQ_ID_RE`, `sanitize_error` verbatim from `main.py` into `errors.py` (with the explanatory comment); in `main.py` replace them with `from errors import sanitize_error` and drop the now-unused `import re`.
- [ ] **Step 2:** `config.py`: append
```python
# Web app (webapp/)
WEBAPP_MODEL = "claude-sonnet-4-6"
```
- [ ] **Step 3:** `requirements.txt`: set `anthropic==0.125.0`; add `fastapi==0.141.1`, `uvicorn==0.54.0`, `jinja2==3.1.6`, `python-multipart==0.0.32`, `apscheduler==3.11.3`, `pytest==9.1.1`, `httpx==0.28.1`. `.venv/bin/pip install -r requirements.txt`.
- [ ] **Step 4:** `.gitignore`: add `data/webapp.db*`.
- [ ] **Step 5:** Stubs matching the spec signatures:
```python
# webapp/runner.py
def start_run(agent_id: int, trigger_kind: str) -> int: raise NotImplementedError
def execute_run(run_id: int) -> None: raise NotImplementedError
# webapp/scheduler.py
def start() -> None: raise NotImplementedError
def shutdown() -> None: raise NotImplementedError
def sync_jobs() -> None: raise NotImplementedError
```
- [ ] **Step 6:** `webapp/__main__.py`:
```python
import uvicorn
uvicorn.run("webapp.app:app", host="127.0.0.1", port=8000)
```
- [ ] **Step 7:** `tests/conftest.py`:
```python
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
```
- [ ] **Step 8:** Download htmx 2.0.x minified into `webapp/static/htmx.min.js`.
- [ ] **Step 9:** Verify `python -c "import main"` works; commit `chore: scaffold webapp package`.

---

### Task 1: Database layer (`webapp/db.py`)

**Files:** Create `webapp/db.py`, `tests/test_db.py`.

**Interfaces:**
- Consumes: nothing (imports `FoundItem` only under `TYPE_CHECKING`).
- Produces: everything under `# webapp/db.py` in the spec's Shared interfaces, exactly: `DB_PATH`, `AgentInput`, `Agent`, `Run`, `Item`, `connect`, `init_db`, `validate_agent`, `create_agent`, `get_agent`, `list_agents`, `update_agent`, `delete_agent`, `create_run -> tuple[int, bool]`, `get_run`, `list_runs`, `latest_run`, `finish_run`, `seen_urls`, `list_items`. Schema exactly as in spec "Data model". Validation exactly as in spec "Validation".

Note on `Agent(AgentInput)` dataclass inheritance: parent fields have no defaults, child fields have defaults, so it works; always construct by keyword.

- [ ] **Step 1: Write the failing tests** — `tests/test_db.py`:

```python
from types import SimpleNamespace

import pytest

from webapp.db import AgentInput


def form(**over):
    base = {
        "name": "AI", "query": "open-weight models", "domain_mode": "none",
        "domains": "", "lookback_days": "7", "max_searches": "5", "schedule_time": "",
    }
    base.update(over)
    return base


def make_input(**over):
    base = dict(name="AI", query="q", domain_mode="none", domains=[],
                lookback_days=7, max_searches=5, schedule_time=None)
    base.update(over)
    return AgentInput(**base)


def found(url, title="t"):
    return SimpleNamespace(title=title, url=url, source="S", published="2026-09-25", summary="s")


# --- validation ---

def test_validate_ok_defaults(tmp_db):
    inp, errs = tmp_db.validate_agent(form())
    assert errs == {}
    assert inp == make_input(query="open-weight models")


def test_validate_required_fields(tmp_db):
    inp, errs = tmp_db.validate_agent(form(name="  ", query=""))
    assert inp is None
    assert set(errs) >= {"name", "query"}


def test_validate_domain_normalization(tmp_db):
    inp, errs = tmp_db.validate_agent(form(
        domain_mode="include",
        domains="https://WWW.TechCrunch.com/ai?x=1, huggingface.co:443\n\nhuggingface.co\n",
    ))
    assert errs == {}
    assert inp.domains == ["www.techcrunch.com", "huggingface.co"]


@pytest.mark.parametrize("bad", ["localhost", "127.0.0.1", "exämple.com", "nodot", "-bad.com"])
def test_validate_rejects_bad_domains(tmp_db, bad):
    inp, errs = tmp_db.validate_agent(form(domain_mode="exclude", domains=bad))
    assert inp is None
    assert "domains" in errs and bad.lower() in errs["domains"].lower()


def test_validate_mode_requires_domains(tmp_db):
    inp, errs = tmp_db.validate_agent(form(domain_mode="include", domains=" "))
    assert inp is None and "domains" in errs


def test_validate_mode_none_ignores_domains(tmp_db):
    inp, errs = tmp_db.validate_agent(form(domain_mode="none", domains="a.com"))
    assert errs == {} and inp.domains == []


def test_validate_too_many_domains(tmp_db):
    doms = "\n".join(f"d{i}.com" for i in range(65))
    inp, errs = tmp_db.validate_agent(form(domain_mode="include", domains=doms))
    assert inp is None and "domains" in errs


def test_validate_bad_mode(tmp_db):
    _, errs = tmp_db.validate_agent(form(domain_mode="both"))
    assert "domain_mode" in errs


@pytest.mark.parametrize("field,value", [
    ("lookback_days", "0"), ("lookback_days", "31"), ("lookback_days", "x"),
    ("max_searches", "0"), ("max_searches", "21"),
    ("schedule_time", "24:00"), ("schedule_time", "7:5"), ("schedule_time", "abc"),
])
def test_validate_ranges(tmp_db, field, value):
    _, errs = tmp_db.validate_agent(form(**{field: value}))
    assert field in errs


def test_validate_schedule_time_ok(tmp_db):
    inp, errs = tmp_db.validate_agent(form(schedule_time="07:30"))
    assert errs == {} and inp.schedule_time == "07:30"


# --- agents CRUD ---

def test_agent_crud(tmp_db):
    aid = tmp_db.create_agent(make_input(domain_mode="include", domains=["a.com"]))
    a = tmp_db.get_agent(aid)
    assert a.id == aid and a.domains == ["a.com"] and a.created_at
    tmp_db.update_agent(aid, make_input(name="B"))
    assert tmp_db.get_agent(aid).name == "B"
    assert [x.id for x in tmp_db.list_agents()] == [aid]
    tmp_db.delete_agent(aid)
    assert tmp_db.get_agent(aid) is None


def test_list_agents_sorted_by_name(tmp_db):
    tmp_db.create_agent(make_input(name="zeta"))
    tmp_db.create_agent(make_input(name="alpha"))
    assert [a.name for a in tmp_db.list_agents()] == ["alpha", "zeta"]


# --- runs ---

def test_create_run_single_running(tmp_db):
    aid = tmp_db.create_agent(make_input())
    rid, created = tmp_db.create_run(aid, "manual")
    assert created and tmp_db.get_run(rid).status == "running"
    rid2, created2 = tmp_db.create_run(aid, "scheduled")
    assert (rid2, created2) == (rid, False)


def test_finish_run_and_seen_before(tmp_db):
    aid = tmp_db.create_agent(make_input())
    r1, _ = tmp_db.create_run(aid, "manual")
    tmp_db.finish_run(r1, status="succeeded", error=None, input_tokens=10,
                      output_tokens=2, searches=1, items=[found("https://a.com/1")])
    r2, created = tmp_db.create_run(aid, "manual")
    assert created
    tmp_db.finish_run(r2, status="succeeded", error=None, input_tokens=1, output_tokens=1,
                      searches=1, items=[found("https://a.com/1"), found("https://a.com/2")])
    items = tmp_db.list_items(r2)
    assert [(i.url, i.seen_before) for i in items] == [("https://a.com/1", True), ("https://a.com/2", False)]
    run = tmp_db.get_run(r2)
    assert run.status == "succeeded" and run.finished_at and run.input_tokens == 1
    assert tmp_db.latest_run(aid).id == r2
    assert [r.id for r in tmp_db.list_runs(aid)] == [r2, r1]


def test_failed_runs_do_not_count_as_seen(tmp_db):
    aid = tmp_db.create_agent(make_input())
    r1, _ = tmp_db.create_run(aid, "manual")
    tmp_db.finish_run(r1, status="failed", error="x", input_tokens=0, output_tokens=0,
                      searches=0, items=[found("https://a.com/1")])
    r2, _ = tmp_db.create_run(aid, "manual")
    assert tmp_db.seen_urls(aid, r2) == set()


def test_delete_agent_cascades(tmp_db):
    aid = tmp_db.create_agent(make_input())
    rid, _ = tmp_db.create_run(aid, "manual")
    tmp_db.finish_run(rid, status="succeeded", error=None, input_tokens=0, output_tokens=0,
                      searches=0, items=[found("https://a.com/1")])
    tmp_db.delete_agent(aid)
    assert tmp_db.get_run(rid) is None and tmp_db.list_items(rid) == []


def test_init_db_marks_interrupted(tmp_db):
    aid = tmp_db.create_agent(make_input())
    rid, _ = tmp_db.create_run(aid, "manual")
    tmp_db.init_db()
    run = tmp_db.get_run(rid)
    assert run.status == "failed" and "interrupted" in run.error and run.finished_at
```

- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_db.py -q` → fails (module missing).
- [ ] **Step 3:** Implement `webapp/db.py` per spec (schema, pragmas, validation regexes, JSON-encoded domains, `create_run` via INSERT + `except sqlite3.IntegrityError` → select existing running id, `finish_run` in one `with conn:` transaction).
- [ ] **Step 4:** Run `.venv/bin/pytest tests/test_db.py -q` → all pass.

---

### Task 2: Search agent (`webapp/search_agent.py`)

**Files:** Create `webapp/search_agent.py`, `tests/test_search_agent.py`.

**Interfaces:**
- Consumes: `config.WEBAPP_MODEL`; an `agent` object with attributes `query, domain_mode, domains, lookback_days, max_searches` (the `db.Agent` dataclass; tests use `SimpleNamespace`). Import `Agent` only under `TYPE_CHECKING`.
- Produces: `SearchError`, `FoundItem`, `SearchResult`, `ITEMS_SCHEMA`, `SYSTEM_PROMPT`, `run_search(agent, *, client=None, today=None) -> SearchResult` exactly per spec "Search agent" + "Spike result" (output via `output_config.format`).

- [ ] **Step 1: Write the failing tests** — `tests/test_search_agent.py`:

```python
import json
from types import SimpleNamespace as NS

import pytest

from webapp.search_agent import SearchError, run_search


def agent(**over):
    base = dict(query="open-weight LLMs", domain_mode="none", domains=[],
                lookback_days=7, max_searches=5)
    base.update(over)
    return NS(**base)


def text(s):
    return NS(type="text", text=s)


def search_ok():
    return NS(type="web_search_tool_result", content=[NS(type="web_search_result", url="https://x.com")])


def search_err(code="unavailable"):
    return NS(type="web_search_tool_result", content=NS(type="web_search_tool_result_error", error_code=code))


def resp(content, stop="end_turn", searches=1, inp=100, out=10, stop_details=None):
    return NS(content=content, stop_reason=stop, stop_details=stop_details,
              usage=NS(input_tokens=inp, output_tokens=out,
                       server_tool_use=NS(web_search_requests=searches)))


def items_json(*items):
    return json.dumps({"items": [dict(title="T", url=u, source="S", published=p, summary="sum")
                                 for u, p in items]})


class FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


TODAY = "2026-09-26"


def test_success_basic_and_request_shape():
    c = FakeClient([resp([NS(type="server_tool_use", name="web_search"), search_ok(),
                          text(items_json(("https://a.com/1", "2026-09-25")))])])
    r = run_search(agent(), client=c, today=TODAY)
    assert [i.url for i in r.items] == ["https://a.com/1"]
    assert (r.input_tokens, r.output_tokens, r.searches) == (100, 10, 1)
    call = c.calls[0]
    assert call["model"] == "claude-sonnet-4-6"
    assert call["output_config"]["format"]["type"] == "json_schema"
    tool = call["tools"][0]
    assert tool["type"] == "web_search_20260209" and tool["max_uses"] == 5
    assert "allowed_domains" not in tool and "blocked_domains" not in tool
    user = call["messages"][0]["content"]
    assert TODAY in user and "open-weight LLMs" in user and "2026-09-19" in user


@pytest.mark.parametrize("mode,key", [("include", "allowed_domains"), ("exclude", "blocked_domains")])
def test_domain_modes(mode, key):
    c = FakeClient([resp([search_ok(), text(items_json())])])
    run_search(agent(domain_mode=mode, domains=["a.com"]), client=c, today=TODAY)
    tool = c.calls[0]["tools"][0]
    assert tool[key] == ["a.com"]
    other = {"allowed_domains", "blocked_domains"} - {key}
    assert not (other & tool.keys())


def test_pause_turn_continues_and_accumulates():
    first = resp([NS(type="server_tool_use", name="web_search"), search_ok()], stop="pause_turn")
    second = resp([search_ok(), text(items_json(("https://a.com/1", "")))], searches=2)
    c = FakeClient([first, second])
    r = run_search(agent(), client=c, today=TODAY)
    assert len(c.calls) == 2
    msgs = c.calls[1]["messages"]
    assert msgs[-1] == {"role": "assistant", "content": first.content}
    assert len(msgs) == 2  # no extra user "continue" message
    assert (r.input_tokens, r.searches) == (200, 3)


def test_pause_turn_cap():
    c = FakeClient([resp([search_ok()], stop="pause_turn") for _ in range(6)])
    with pytest.raises(SearchError, match="continuations"):
        run_search(agent(), client=c, today=TODAY)
    assert len(c.calls) == 6


def test_refusal_with_and_without_category():
    c = FakeClient([resp([], stop="refusal", stop_details=NS(category="cyber"))])
    with pytest.raises(SearchError, match="model refused: cyber"):
        run_search(agent(), client=c, today=TODAY)
    c = FakeClient([resp([], stop="refusal")])
    with pytest.raises(SearchError, match="model refused"):
        run_search(agent(), client=c, today=TODAY)


def test_max_tokens():
    c = FakeClient([resp([search_ok(), text('{"items": [')], stop="max_tokens")])
    with pytest.raises(SearchError, match="truncated"):
        run_search(agent(), client=c, today=TODAY)


def test_all_searches_errored():
    c = FakeClient([resp([search_err("too_many_requests"), text(items_json())])])
    with pytest.raises(SearchError, match="web search failed: too_many_requests"):
        run_search(agent(), client=c, today=TODAY)


def test_partial_search_errors_ok():
    c = FakeClient([resp([search_err(), search_ok(), text(items_json())], searches=2)])
    assert run_search(agent(), client=c, today=TODAY).items == []


def test_zero_searches():
    c = FakeClient([resp([text(items_json(("https://a.com", "")))], searches=0)])
    with pytest.raises(SearchError, match="did not search"):
        run_search(agent(), client=c, today=TODAY)


def test_searches_fallback_counts_blocks_when_usage_missing():
    r0 = resp([NS(type="server_tool_use", name="web_search"),
               NS(type="server_tool_use", name="code_execution"),
               search_ok(), text(items_json())])
    r0.usage = NS(input_tokens=1, output_tokens=1)
    assert run_search(agent(), client=FakeClient([r0]), today=TODAY).searches == 1


def test_parse_failure():
    c = FakeClient([resp([search_ok(), text("not json")])])
    with pytest.raises(SearchError, match="parse"):
        run_search(agent(), client=c, today=TODAY)


def test_only_trailing_text_blocks_parsed():
    c = FakeClient([resp([text("Let me search."), search_ok(),
                          text(items_json(("https://a.com/1", "")))])])
    assert len(run_search(agent(), client=c, today=TODAY).items) == 1


def test_post_filtering():
    body = items_json(
        ("https://a.com/1", "2026-09-25"),
        ("https://a.com/1", "2026-09-25"),    # duplicate
        ("javascript:alert(1)", ""),          # bad scheme
        ("https:///nohost", ""),              # no host
        ("https://b.com/old", "2026-09-01"),  # outside window
        ("https://b.com/edge", "2026-09-18"), # within 1-day slack
        ("https://c.com/nodate", ""),         # kept
        ("https://c.com/weird", "last week"), # unparseable, kept
    )
    r = run_search(agent(), client=FakeClient([resp([search_ok(), text(body)])]), today=TODAY)
    assert [i.url for i in r.items] == [
        "https://a.com/1", "https://b.com/edge", "https://c.com/nodate", "https://c.com/weird"]
```

- [ ] **Step 2:** `.venv/bin/pytest tests/test_search_agent.py -q` → fails.
- [ ] **Step 3:** Implement per spec. Notes: default client `anthropic.Anthropic(timeout=600, max_retries=2)` created lazily only when `client is None`; block access via `getattr(b, "type", None)`; error blocks are those whose `content` is not a list; `published` date parsing via `date.fromisoformat(p[:10])` inside try.
- [ ] **Step 4:** `.venv/bin/pytest tests/test_search_agent.py -q` → all pass.

---

### Task 3: Runner + scheduler

**Files:** Replace stubs `webapp/runner.py`, `webapp/scheduler.py`; create `tests/test_runner.py`.

**Interfaces:**
- Consumes: `webapp.db` (`get_agent`, `get_run`, `create_run`, `finish_run`, `list_agents`), `webapp.search_agent.run_search`, `errors.sanitize_error`. Call them as module attributes (`db.get_agent(...)`, `search_agent.run_search(...)`) so tests can monkeypatch.
- Produces: `runner.start_run(agent_id, trigger_kind) -> int` (LookupError if agent missing), `runner.execute_run(run_id) -> None`; `scheduler.start()`, `scheduler.shutdown()`, `scheduler.sync_jobs()` per spec.

- [ ] **Step 1: Write the failing tests** — `tests/test_runner.py`:

```python
from types import SimpleNamespace

import pytest

from webapp import runner, scheduler, search_agent
from webapp.db import AgentInput


def make_agent(db, **over):
    base = dict(name="A", query="q", domain_mode="none", domains=[],
                lookback_days=7, max_searches=5, schedule_time=None)
    base.update(over)
    return db.create_agent(AgentInput(**base))


def result(*urls):
    items = [search_agent.FoundItem(title="t", url=u, source="s", published="", summary="x") for u in urls]
    return search_agent.SearchResult(items=items, input_tokens=5, output_tokens=3, searches=2)


def test_execute_run_success(tmp_db, monkeypatch):
    aid = make_agent(tmp_db)
    rid, _ = tmp_db.create_run(aid, "manual")
    seen = {}
    def fake(agent, **kw):
        seen["agent"] = agent
        return result("https://a.com/1")
    monkeypatch.setattr(search_agent, "run_search", fake)
    runner.execute_run(rid)
    run = tmp_db.get_run(rid)
    assert run.status == "succeeded" and (run.input_tokens, run.searches) == (5, 2)
    assert seen["agent"].id == aid
    assert [i.url for i in tmp_db.list_items(rid)] == ["https://a.com/1"]


def test_execute_run_failure_sanitized(tmp_db, monkeypatch):
    aid = make_agent(tmp_db)
    rid, _ = tmp_db.create_run(aid, "manual")
    def boom(agent, **kw):
        raise RuntimeError("bad key sk-abc123 for me@x.com")
    monkeypatch.setattr(search_agent, "run_search", boom)
    runner.execute_run(rid)
    run = tmp_db.get_run(rid)
    assert run.status == "failed"
    assert "RuntimeError" in run.error and "sk-abc123" not in run.error and "me@x.com" not in run.error


def test_execute_run_agent_deleted_midrun(tmp_db, monkeypatch):
    aid = make_agent(tmp_db)
    rid, _ = tmp_db.create_run(aid, "manual")
    def delete_then_return(agent, **kw):
        tmp_db.delete_agent(aid)
        return result("https://a.com/1")
    monkeypatch.setattr(search_agent, "run_search", delete_then_return)
    runner.execute_run(rid)  # must not raise
    assert tmp_db.get_run(rid) is None


def test_execute_run_missing_run_is_noop(tmp_db):
    runner.execute_run(9999)


def test_start_run_missing_agent(tmp_db):
    with pytest.raises(LookupError):
        runner.start_run(9999, "manual")


def test_start_run_spawns_thread_once(tmp_db, monkeypatch):
    aid = make_agent(tmp_db)
    started = []
    class FakeThread:
        def __init__(self, target, args, daemon):
            started.append(args)
        def start(self):
            pass
    monkeypatch.setattr(runner.threading, "Thread", FakeThread)
    rid = runner.start_run(aid, "manual")
    rid2 = runner.start_run(aid, "scheduled")
    assert rid == rid2 and started == [(rid,)]


def test_scheduler_disabled_is_noop(tmp_db):
    scheduler.start()
    scheduler.sync_jobs()
    scheduler.shutdown()


def test_scheduler_sync_jobs(tmp_db, monkeypatch):
    monkeypatch.delenv("WEBAPP_DISABLE_SCHEDULER")
    a1 = make_agent(tmp_db, name="a", schedule_time="07:30")
    make_agent(tmp_db, name="b", schedule_time=None)
    scheduler.start()
    try:
        jobs = {j.id: j for j in scheduler._scheduler.get_jobs()}
        assert set(jobs) == {f"agent-{a1}"}
        tmp_db.update_agent(a1, AgentInput(name="a", query="q", domain_mode="none", domains=[],
                                           lookback_days=7, max_searches=5, schedule_time=None))
        scheduler.sync_jobs()
        assert scheduler._scheduler.get_jobs() == []
    finally:
        scheduler.shutdown()
```

- [ ] **Step 2:** `.venv/bin/pytest tests/test_runner.py -q` → fails.
- [ ] **Step 3:** Implement. Scheduler: module global `_scheduler: BackgroundScheduler | None = None`; `start()` returns early if env disabled, else creates, starts, `sync_jobs()`; `shutdown()` does `_scheduler.shutdown(wait=False)` and resets to None; job func `_fire(agent_id)` wraps `runner.start_run(agent_id, "scheduled")` in try/except printing to stderr.
- [ ] **Step 4:** `.venv/bin/pytest tests/test_runner.py -q` → all pass.

---

### Task 4: Web app + templates

**Files:** Create `webapp/app.py`, `webapp/templates/{base,agents,agent_form,agent_detail,run_detail,_run_status,_items,404}.html`, `webapp/static/style.css`, `tests/test_app.py`.

**Interfaces:**
- Consumes: `webapp.db` (all of it), `webapp.runner.start_run`, `webapp.scheduler.{start,shutdown,sync_jobs}` — call as module attributes (`runner.start_run(...)`) so tests can monkeypatch. `webapp/static/htmx.min.js` exists (Task 0).
- Produces: `app: FastAPI` in `webapp/app.py`; routes and HTMX contract exactly per spec "Web UI".

Wave 2 note: Task 1 (db) is complete before this starts; runner/scheduler may still be stubs — tests monkeypatch `runner.start_run`, and the scheduler functions (with `WEBAPP_DISABLE_SCHEDULER=1` Task 3's real implementation is a no-op; while stubbed, the test fixture monkeypatches them to no-ops).

- [ ] **Step 1: Write the failing tests** — `tests/test_app.py`:

```python
import pytest
from fastapi.testclient import TestClient

from webapp import app as app_module
from webapp import runner, scheduler
from webapp.db import AgentInput


@pytest.fixture
def client(tmp_db, monkeypatch):
    for name in ("start", "shutdown", "sync_jobs"):
        monkeypatch.setattr(scheduler, name, lambda: None)
    with TestClient(app_module.app) as c:
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


@pytest.mark.parametrize("path", ["/agents/999", "/agents/999/edit", "/runs/999", "/runs/999/status"])
def test_404s(client, path):
    assert client.get(path).status_code == 404


def test_run_missing_agent_404(client, monkeypatch):
    def missing(agent_id, kind):
        raise LookupError(agent_id)
    monkeypatch.setattr(runner, "start_run", missing)
    assert client.post("/agents/999/run").status_code == 404
```

- [ ] **Step 2:** `.venv/bin/pytest tests/test_app.py -q` → fails.
- [ ] **Step 3:** Implement `app.py` (lifespan, `Jinja2Templates(directory=Path(__file__).parent / "templates")`, `StaticFiles` at `/static`, `load_dotenv()` at import, every Form param `str = Form("")`, helpers `_agent_or_404`, `hostname` Jinja filter via `urlparse`). Templates: `base.html` loads `/static/style.css` and `/static/htmx.min.js`; `_run_status.html` per spec HTMX contract; `_items.html` shared by agent detail and run detail. Form re-render on 422 passes back the raw form dict and errors. Clean, readable CSS: max-width container, system font, cards with subtle border, status badges (running/succeeded/failed).
- [ ] **Step 4:** `.venv/bin/pytest tests/test_app.py -q` → all pass.

---

### Task 5: Integration (coordinator)

- [ ] **Step 1:** `.venv/bin/pytest -q` → full suite passes.
- [ ] **Step 2:** `python -c "import main"`, confirm email pipeline imports still OK.
- [ ] **Step 3:** README: add a "Web app" section (what it is, `python -m webapp`, open http://127.0.0.1:8000, cost note ~$0.3+/run, scheduler only while running, tests `pytest`).
- [ ] **Step 4:** Live smoke: start server, create an agent via HTTP, run it, poll until finished, confirm items render.
- [ ] **Step 5:** Final code review (fresh reviewer), fix findings, commit.
