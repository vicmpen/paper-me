"""`python -m webapp` — serve on localhost. No --reload: a reloader process
would start a second scheduler and double-fire scheduled runs."""

import uvicorn

from webapp.logs import LOG_PATH, setup_logging

setup_logging()
print(f"Logging to {LOG_PATH}")
uvicorn.run("webapp.app:app", host="127.0.0.1", port=8000, log_config=None)
