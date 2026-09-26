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
