"""Executes agent runs in background threads.

A run calls Claude with web search and can take minutes, so the HTTP request
that starts it must return immediately; the UI polls the run row for status.
`execute_run` never raises: it runs on a daemon thread where an uncaught
exception would only vanish into stderr and leave the run stuck "running".
The agent may be deleted while its run is in flight (cascading the run row
away), so every step tolerates missing rows.
"""

from __future__ import annotations

import logging
import threading
import time

import config
import errors
from webapp import db, search_agent

log = logging.getLogger(__name__)


def start_run(agent_id: int, trigger_kind: str) -> int:
    if db.get_agent(agent_id) is None:
        raise LookupError(f"agent {agent_id} not found")
    run_id, created = db.create_run(agent_id, trigger_kind)
    if not created:
        log.info("agent %d already has run %d in progress; not starting another (%s)",
                 agent_id, run_id, trigger_kind)
    if created:
        threading.Thread(target=execute_run, args=(run_id,), daemon=True).start()
    return run_id


def execute_run(run_id: int) -> None:
    started = time.monotonic()
    try:
        run = db.get_run(run_id)
        agent = db.get_agent(run.agent_id) if run else None
        if agent is None:
            log.info("run %d: run or agent no longer exists, skipping", run_id)
            return
        log.info("run %d started: agent %d %r (%s)", run_id, agent.id, agent.name,
                 run.trigger_kind)
        result = search_agent.run_search(agent)
        outcome = dict(status="succeeded", error=None, items=result.items,
                       input_tokens=result.input_tokens,
                       output_tokens=result.output_tokens, searches=result.searches,
                       answer=result.answer, provider=result.provider)
    except search_agent.SearchError as e:
        outcome = dict(status="failed", error=errors.sanitize_error(e), items=[],
                       input_tokens=0, output_tokens=0, searches=0,
                       answer=None, provider=config.WEBAPP_SEARCH_PROVIDER)
    except Exception as e:
        # Unexpected (API, network, bug): keep the traceback in the local log.
        log.exception("run %d raised", run_id)
        outcome = dict(status="failed", error=errors.sanitize_error(e), items=[],
                       input_tokens=0, output_tokens=0, searches=0,
                       answer=None, provider=config.WEBAPP_SEARCH_PROVIDER)

    elapsed = time.monotonic() - started
    if outcome["status"] == "succeeded":
        log.info("run %d succeeded in %.1fs: provider=%s %d items, in=%d out=%d searches=%d",
                 run_id, elapsed, outcome["provider"], len(outcome["items"]),
                 outcome["input_tokens"], outcome["output_tokens"], outcome["searches"])
    else:
        log.warning("run %d failed after %.1fs: %s", run_id, elapsed, outcome["error"])

    try:
        db.finish_run(run_id, **outcome)
    except Exception:
        log.exception("run %d: could not record outcome", run_id)
