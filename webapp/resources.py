"""Resource lookups shared by the HTML pages and the JSON API.

Every route resolves agents and runs through these functions, so the
ownership check a multi-user version needs lands in one place (answering
404, not 403, for other people's resources).
"""

from __future__ import annotations

from fastapi import HTTPException

from webapp import db


def agent_or_404(agent_id: int) -> db.Agent:
    agent = db.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404)
    return agent


def run_or_404(run_id: int) -> db.Run:
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404)
    return run
