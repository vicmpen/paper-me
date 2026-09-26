"""Logging setup for `python -m webapp`.

One root configuration shared by our modules and uvicorn (started with
log_config=None so its loggers propagate here): console plus a rotating
file at data/webapp.log. Level from WEBAPP_LOG_LEVEL (default INFO). At
INFO the every-2s run-status polls are dropped from the access log, or
they would drown everything else while a run is in flight.
"""

from __future__ import annotations

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "webapp.log"

_STATUS_POLL_RE = re.compile(r"GET /runs/\d+/status ")


class _DropStatusPolls(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not _STATUS_POLL_RE.search(record.getMessage())


def setup_logging() -> None:
    level = os.environ.get("WEBAPP_LOG_LEVEL", "INFO").upper()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    console = logging.StreamHandler()
    file = RotatingFileHandler(LOG_PATH, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    for h in (console, file):
        h.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [console, file]
    if level != "DEBUG":
        logging.getLogger("uvicorn.access").addFilter(_DropStatusPolls())
        # APScheduler logs every job add/remove/execution at INFO; ours are enough.
        logging.getLogger("apscheduler").setLevel(logging.WARNING)
