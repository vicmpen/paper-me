import asyncio

from webapp import edition_events, fallback_edition
from webapp.db import AgentInput
from webapp.search_agent import FoundItem


def running(db):
    aid = db.create_agent(AgentInput(name="A", query="q", domain_mode="none", domains=[],
                                     lookback_days=7, max_searches=5, schedule_time=None))
    rid, _ = db.create_run(aid, "manual")
    return rid


def finish(db, rid, **over):
    base = dict(status="succeeded", error=None, input_tokens=0, output_tokens=0, searches=0,
                items=[])
    base.update(over)
    db.finish_run(rid, **base)


def collect(run_id, *steps):
    """Consume the stream; each poll tick runs the next scripted DB change."""
    pending = list(steps)

    async def fake_sleep(_seconds):
        if not pending:
            raise AssertionError("stream kept polling after the last step")
        pending.pop(0)()

    async def go():
        return [event async for event in edition_events.edition_events(run_id, sleep=fake_sleep)]

    return asyncio.run(go())


def test_finished_run_replays_and_ends(tmp_db):
    rid = running(tmp_db)
    tmp_db.append_edition_lines(rid, ["l1", "l2"])
    finish(tmp_db, rid, edition="composed")
    assert collect(rid) == [
        ("status", {"status": "succeeded", "stage": None}), ("reset", {}),
        ("patch", "l1"), ("patch", "l2"),
        ("done", {"status": "succeeded", "edition": "composed", "error": None}),
    ]


def test_live_run_tails_lines_then_replays_the_final_edition(tmp_db):
    rid = running(tmp_db)
    tmp_db.append_edition_lines(rid, ["l1"])
    events = collect(
        rid,
        lambda: (tmp_db.set_stage(rid, "composing"), tmp_db.append_edition_lines(rid, ["l2", "l3"])),
        lambda: finish(tmp_db, rid, edition="composed"),
    )
    assert events == [
        ("status", {"status": "running", "stage": None}), ("reset", {}), ("patch", "l1"),
        ("status", {"status": "running", "stage": "composing"}), ("patch", "l2"), ("patch", "l3"),
        ("status", {"status": "succeeded", "stage": None}), ("reset", {}),
        ("patch", "l1"), ("patch", "l2"), ("patch", "l3"),
        ("done", {"status": "succeeded", "edition": "composed", "error": None}),
    ]


def test_fallback_swap_during_a_live_connection_resets(tmp_db):
    rid = running(tmp_db)
    tmp_db.append_edition_lines(rid, ["a", "b"])
    events = collect(rid, lambda: finish(tmp_db, rid, edition="fallback",
                                         edition_lines=["x", "y", "z"]))
    assert events[-5:] == [("reset", {}), ("patch", "x"), ("patch", "y"), ("patch", "z"),
                           ("done", {"status": "succeeded", "edition": "fallback", "error": None})]


def test_every_connection_replays_from_the_start(tmp_db):
    rid = running(tmp_db)
    tmp_db.append_edition_lines(rid, ["a", "b", "c"])
    first = collect(rid, lambda: None, lambda: finish(tmp_db, rid, edition="composed"))
    second = collect(rid)
    assert first[:5] == [("status", {"status": "running", "stage": None}), ("reset", {}),
                         ("patch", "a"), ("patch", "b"), ("patch", "c")]
    assert second[1:5] == [("reset", {}), ("patch", "a"), ("patch", "b"), ("patch", "c")]


def test_failed_run_sends_done_with_the_error(tmp_db):
    rid = running(tmp_db)
    tmp_db.append_edition_lines(rid, ["partial"])
    finish(tmp_db, rid, status="failed", error="search provider failed")
    assert collect(rid) == [
        ("status", {"status": "failed", "stage": None}), ("reset", {}),
        ("done", {"status": "failed", "edition": None, "error": "search provider failed"}),
    ]


def test_old_run_without_lines_gets_fallback_edition(tmp_db):
    rid = running(tmp_db)
    items = [FoundItem(title="T1", url="https://a.com/1", source="a", published="", summary="s1"),
             FoundItem(title="T2", url="https://b.com/2", source="b", published="", summary="s2")]
    finish(tmp_db, rid, items=items, answer="- A [1][2]")   # edition=None, as before the paper
    events = collect(rid)
    patches = [payload for kind, payload in events if kind == "patch"]
    assert patches == fallback_edition.build("- A [1][2]", tmp_db.list_items(rid))
    assert events[-1] == ("done", {"status": "succeeded", "edition": "fallback", "error": None})


def test_old_run_with_zero_items_is_empty(tmp_db):
    rid = running(tmp_db)
    finish(tmp_db, rid, answer="No results found in this window.")
    assert collect(rid)[-1] == ("done", {"status": "succeeded", "edition": "empty", "error": None})


def test_run_deleted_mid_stream_ends_quietly(tmp_db):
    rid = running(tmp_db)
    agent_id = tmp_db.get_run(rid).agent_id
    events = collect(rid, lambda: tmp_db.delete_agent(agent_id))
    assert events == [("status", {"status": "running", "stage": None}), ("reset", {})]
