import sqlite3
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


# --- response instructions, answer, provider ---

def test_validate_response_instructions(tmp_db):
    inp, errs = tmp_db.validate_agent(form(response_instructions="  Two sentences.  "))
    assert errs == {} and inp.response_instructions == "Two sentences."
    inp, errs = tmp_db.validate_agent(form(response_instructions="x" * 2000))
    assert errs == {}
    inp, errs = tmp_db.validate_agent(form(response_instructions="x" * 2001))
    assert inp is None
    assert errs["response_instructions"] == "Keep this to 2000 characters or fewer."
    inp, errs = tmp_db.validate_agent(form())  # field absent from the form
    assert inp.response_instructions == ""


def test_response_instructions_round_trip(tmp_db):
    aid = tmp_db.create_agent(make_input(response_instructions="Bullets."))
    assert tmp_db.get_agent(aid).response_instructions == "Bullets."
    tmp_db.update_agent(aid, make_input(response_instructions="One line."))
    assert tmp_db.get_agent(aid).response_instructions == "One line."
    assert tmp_db.list_agents()[0].response_instructions == "One line."


def test_finish_run_stores_answer_provider_and_item_order(tmp_db):
    aid = tmp_db.create_agent(make_input())
    rid, _ = tmp_db.create_run(aid, "manual")
    tmp_db.finish_run(rid, status="succeeded", error=None, input_tokens=1, output_tokens=1,
                      searches=2, items=[found("https://b.com/2"), found("https://a.com/1")],
                      answer="See [1] and [2].", provider="exa")
    run = tmp_db.get_run(rid)
    assert run.answer == "See [1] and [2]." and run.provider == "exa"
    assert [i.url for i in tmp_db.list_items(rid)] == ["https://b.com/2", "https://a.com/1"]


def test_finish_run_without_answer_defaults_none(tmp_db):
    aid = tmp_db.create_agent(make_input())
    rid, _ = tmp_db.create_run(aid, "manual")
    tmp_db.finish_run(rid, status="failed", error="x", input_tokens=0, output_tokens=0,
                      searches=0, items=[])
    run = tmp_db.get_run(rid)
    assert run.answer is None and run.provider is None


OLD_SCHEMA = """
CREATE TABLE agents (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, query TEXT NOT NULL,
  domain_mode TEXT NOT NULL, domains TEXT NOT NULL, lookback_days INTEGER NOT NULL,
  max_searches INTEGER NOT NULL, schedule_time TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE runs (
  id INTEGER PRIMARY KEY,
  agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  trigger_kind TEXT NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL,
  finished_at TEXT, error TEXT,
  input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
  searches INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX runs_one_running ON runs(agent_id) WHERE status = 'running';
CREATE TABLE items (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  title TEXT NOT NULL, url TEXT NOT NULL, source TEXT NOT NULL,
  published TEXT NOT NULL, summary TEXT NOT NULL,
  seen_before INTEGER NOT NULL DEFAULT 0
);
"""


def test_init_db_migrates_old_schema(tmp_path, monkeypatch, caplog):
    from webapp import db
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(OLD_SCHEMA)
    conn.execute("INSERT INTO agents (name, query, domain_mode, domains, lookback_days,"
                 " max_searches, schedule_time, created_at, updated_at)"
                 " VALUES ('Old', 'q', 'none', '[]', 7, 5, NULL, 't', 't')")
    conn.execute("INSERT INTO runs (agent_id, trigger_kind, status, started_at, finished_at)"
                 " VALUES (1, 'manual', 'succeeded', 't', 't')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "DB_PATH", path)
    caplog.set_level("INFO", logger="webapp.db")
    db.init_db()
    db.init_db()  # second run is a no-op
    agent = db.get_agent(1)
    assert agent.name == "Old" and agent.response_instructions == ""
    run = db.get_run(1)
    assert run.status == "succeeded" and run.answer is None and run.provider is None
    assert caplog.text.count("added column") == 3
