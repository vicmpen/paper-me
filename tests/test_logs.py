import logging

from webapp import logs


def test_setup_logging_writes_file_and_drops_status_polls(tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "LOG_PATH", tmp_path / "webapp.log")
    monkeypatch.delenv("WEBAPP_LOG_LEVEL", raising=False)
    root = logging.getLogger()
    saved = root.handlers[:], root.level
    access = logging.getLogger("uvicorn.access")
    saved_filters = access.filters[:]
    try:
        logs.setup_logging()
        access.info('127.0.0.1:1 - "GET /runs/4/status HTTP/1.1" 200')
        access.info('127.0.0.1:1 - "POST /agents/2/run HTTP/1.1" 303')
        logging.getLogger("webapp.runner").info("run 4 started")
        for h in root.handlers:
            h.flush()
        text = (tmp_path / "webapp.log").read_text()
        assert "POST /agents/2/run" in text and "run 4 started" in text
        assert "/runs/4/status" not in text
    finally:
        for h in root.handlers:
            h.close()
        root.handlers = saved[0]
        root.setLevel(saved[1])
        access.filters = saved_filters
