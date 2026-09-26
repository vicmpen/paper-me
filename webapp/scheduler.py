"""Daily scheduled runs via an in-process APScheduler.

The app is a single local process, so an in-memory BackgroundScheduler is
enough: jobs are rebuilt from the agents table on start and after every
agent create/update/delete (`sync_jobs`), so there is no job store to keep
in sync. Tests set WEBAPP_DISABLE_SCHEDULER=1 so no background thread starts.
"""

from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import errors
from webapp import db, runner

log = logging.getLogger(__name__)

_JOB_PREFIX = "agent-"

_scheduler: BackgroundScheduler | None = None


def _fire(agent_id: int) -> None:
    # A job for a just-deleted agent can still fire (LookupError); log, don't crash.
    log.info("scheduled run firing for agent %d", agent_id)
    try:
        runner.start_run(agent_id, "scheduled")
    except Exception as e:
        log.warning("scheduled run for agent %d not started: %s", agent_id,
                    errors.sanitize_error(e))


def start() -> None:
    global _scheduler
    if os.environ.get("WEBAPP_DISABLE_SCHEDULER") == "1" or _scheduler is not None:
        return
    log.info("scheduler starting")
    _scheduler = BackgroundScheduler()
    _scheduler.start()
    sync_jobs()


def shutdown() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None


def sync_jobs() -> None:
    if _scheduler is None:
        return
    for job in _scheduler.get_jobs():
        if job.id.startswith(_JOB_PREFIX):
            job.remove()
    scheduled = []
    for agent in db.list_agents():
        if not agent.schedule_time:
            continue
        scheduled.append(f"{agent.id}@{agent.schedule_time}")
        hour, minute = (int(x) for x in agent.schedule_time.split(":"))
        _scheduler.add_job(
            _fire, CronTrigger(hour=hour, minute=minute), args=(agent.id,),
            id=f"{_JOB_PREFIX}{agent.id}", misfire_grace_time=300,
            coalesce=True, max_instances=1, replace_existing=True,
        )
    log.info("scheduler jobs synced: %s", ", ".join(scheduled) or "none")
