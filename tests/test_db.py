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
