"""JSON and SSE routes for the React paper, under /api.

Resources resolve through webapp.resources so ownership checks land in one
place later. The stream handler is async: an async generator costs nothing
per idle viewer, where a sync one would hold a threadpool thread for as long
as the page stays open.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent

from webapp import db, edition_events, runner
from webapp.resources import agent_or_404, run_or_404

router = APIRouter(prefix="/api")


def _edition(run: db.Run) -> dict:
    return {"run_id": run.id, "started_at": run.started_at, "finished_at": run.finished_at,
            "status": run.status, "edition": run.edition, "error": run.error,
            "answer": run.answer}


@router.get("/agents/{agent_id}/paper")
def paper(agent_id: int) -> dict:
    agent = agent_or_404(agent_id)
    runs = db.list_runs(agent_id)
    current = (next((r for r in runs if r.status == "running"), None)
               or next((r for r in runs if r.status == "succeeded"), None))
    return {"agent": {"id": agent.id, "name": agent.name, "query": agent.query},
            "current_run_id": current.id if current else None,
            "editions": [_edition(r) for r in runs]}


@router.get("/runs/{run_id}/sources")
def sources(run_id: int) -> list[dict]:
    run_or_404(run_id)
    return [{"n": n, "title": it.title, "url": it.url, "source": it.source,
             "published": it.published, "summary": it.summary, "seen_before": it.seen_before}
            for n, it in enumerate(db.list_items(run_id), 1)]


@router.post("/agents/{agent_id}/run")
def go_to_press(agent_id: int) -> dict:
    agent_or_404(agent_id)
    try:
        run_id = runner.start_run(agent_id, "manual")
    except LookupError:
        raise HTTPException(status_code=404)
    return {"run_id": run_id}


# The lookup is a dependency so an unknown run answers 404 before the stream starts.
@router.get("/runs/{run_id}/edition/stream", response_class=EventSourceResponse)
async def edition_stream(run: db.Run = Depends(run_or_404)):
    async for kind, payload in edition_events.edition_events(run.id):
        if kind == "patch":
            yield ServerSentEvent(event="patch", raw_data=payload)
        else:
            yield ServerSentEvent(event=kind, data=payload)
