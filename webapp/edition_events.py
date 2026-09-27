"""Event source for an edition's live stream, independent of the wire format.

edition_events(run_id) yields (kind, payload) tuples; webapp/api.py encodes
them as Server-Sent Events. Today it polls SQLite every 250 ms; a pub/sub
backend can replace the polling here without touching the protocol or the
frontend.

Protocol: every connection starts with "status" and "reset" and replays the
edition from its first line, so reconnects need no Last-Event-ID. While the
run is running, new lines follow as "patch" events. When the run finishes,
the stream sends "reset", the final lines (possibly the fallback edition
finish_run swapped in) and "done", then ends. Lines are read before the run
row on each tick: finish_run swaps lines and status in one transaction, so a
tick that sees "running" has only read appended lines.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from webapp import db, fallback_edition

POLL_INTERVAL_S = 0.25


def _status(run: db.Run) -> dict:
    return {"status": run.status, "stage": run.stage}


def _final_edition(run: db.Run) -> tuple[list[str], str | None]:
    if run.status != "succeeded":
        return [], None
    if run.edition is not None:
        return db.all_edition_lines(run.id), run.edition
    items = db.list_items(run.id)  # the run predates the paper: build its edition now
    if not items:
        return [], "empty"
    return fallback_edition.build(run.answer, items), "fallback"


def _final_events(run: db.Run) -> list[tuple[str, object]]:
    lines, edition = _final_edition(run)
    return [("patch", line) for line in lines] + [
        ("done", {"status": run.status, "edition": edition, "error": run.error})]


async def edition_events(
    run_id: int, *, poll_interval: float = POLL_INTERVAL_S,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> AsyncIterator[tuple[str, object]]:
    lines = db.edition_lines_after(run_id, 0)
    run = db.get_run(run_id)
    if run is None:
        return
    status = _status(run)
    yield "status", status
    yield "reset", {}
    if run.status != "running":
        for event in _final_events(run):
            yield event
        return
    last_seq = 0
    for seq, line in lines:
        last_seq = seq
        yield "patch", line
    while True:
        await sleep(poll_interval)
        new_lines = db.edition_lines_after(run_id, last_seq)
        run = db.get_run(run_id)
        if run is None:
            return  # agent deleted mid-run; the client's reconnect gets a 404
        if _status(run) != status:
            status = _status(run)
            yield "status", status
        if run.status == "running":
            for seq, line in new_lines:
                last_seq = seq
                yield "patch", line
            continue
        yield "reset", {}
        for event in _final_events(run):
            yield event
        return
