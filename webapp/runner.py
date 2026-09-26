"""Executes agent runs in background threads.

A run calls Claude with web search and can take minutes, so the HTTP request
that starts it must return immediately; the UI polls the run row for status.
`execute_run` never raises: it runs on a daemon thread where an uncaught
exception would only vanish into stderr and leave the run stuck "running".
The agent may be deleted while its run is in flight (cascading the run row
away), so every step tolerates missing rows.
"""

from __future__ import annotations

import sys
import threading

import errors
from webapp import db, search_agent


def start_run(agent_id: int, trigger_kind: str) -> int:
    if db.get_agent(agent_id) is None:
        raise LookupError(f"agent {agent_id} not found")
    run_id, created = db.create_run(agent_id, trigger_kind)
    if created:
        threading.Thread(target=execute_run, args=(run_id,), daemon=True).start()
    return run_id


def execute_run(run_id: int) -> None:
    try:
        run = db.get_run(run_id)
        agent = db.get_agent(run.agent_id) if run else None
        if agent is None:
            return
        result = search_agent.run_search(agent)
        outcome = dict(status="succeeded", error=None, items=result.items,
                       input_tokens=result.input_tokens,
                       output_tokens=result.output_tokens, searches=result.searches)
    except Exception as e:
        outcome = dict(status="failed", error=errors.sanitize_error(e), items=[],
                       input_tokens=0, output_tokens=0, searches=0)

    try:
        db.finish_run(run_id, **outcome)
    except Exception as e:
        print(f"[runner] could not record run {run_id}: {errors.sanitize_error(e)}",
              file=sys.stderr)
