"""SQLite persistence for the web app: agents, runs, and found items.

Plain sqlite3 + dataclasses, no ORM. A fresh connection is opened per call
because runs execute in background threads and sqlite3 connections must not
be shared across threads. WAL mode lets the UI read while a run writes.

"Only one running run per agent" is enforced by a partial unique index, not
by a check-then-insert, so a double-clicked "Run now" and a scheduler tick
racing each other can't both start a run.

DB_PATH is read at call time so tests can monkeypatch it.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webapp.search_agent import FoundItem

log = logging.getLogger(__name__)

DB_PATH: Path = Path(__file__).resolve().parent.parent / "data" / "webapp.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  query TEXT NOT NULL,
  domain_mode TEXT NOT NULL,
  domains TEXT NOT NULL,
  lookback_days INTEGER NOT NULL,
  max_searches INTEGER NOT NULL,
  schedule_time TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY,
  agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  trigger_kind TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  error TEXT,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  searches INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS runs_one_running ON runs(agent_id) WHERE status = 'running';
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  title TEXT NOT NULL, url TEXT NOT NULL, source TEXT NOT NULL,
  published TEXT NOT NULL, summary TEXT NOT NULL,
  seen_before INTEGER NOT NULL DEFAULT 0
);
"""

_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://")
_DOMAIN_MODES = {"none", "include", "exclude"}
_MAX_DOMAINS = 64


@dataclass
class AgentInput:
    name: str
    query: str
    domain_mode: str            # "none" | "include" | "exclude"
    domains: list[str]          # [] when domain_mode == "none"
    lookback_days: int
    max_searches: int
    schedule_time: str | None   # "HH:MM" or None


@dataclass
class Agent(AgentInput):
    id: int = 0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Run:
    id: int
    agent_id: int
    trigger_kind: str
    status: str
    started_at: str
    finished_at: str | None
    error: str | None
    input_tokens: int
    output_tokens: int
    searches: int


@dataclass
class Item:
    id: int
    run_id: int
    title: str
    url: str
    source: str
    published: str
    summary: str
    seen_before: bool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        # Any run still "running" at startup belongs to a previous process
        # whose thread is gone; without this it would spin in the UI forever.
        with conn:
            cur = conn.execute(
                "UPDATE runs SET status='failed', error=?, finished_at=? WHERE status='running'",
                ("interrupted (server restarted)", _now()),
            )
    log.info("database ready at %s", DB_PATH)
    if cur.rowcount:
        log.warning("marked %d interrupted run(s) as failed", cur.rowcount)


# --- validation ---

def _normalize_domain(raw: str) -> str:
    d = _SCHEME_RE.sub("", raw.strip().lower())
    d = re.split(r"[/?#]", d, maxsplit=1)[0]
    return d.split(":", 1)[0]


def _parse_int(form: dict[str, str], field: str, lo: int, hi: int,
               errors: dict[str, str]) -> int:
    raw = (form.get(field) or "").strip()
    try:
        value = int(raw)
    except ValueError:
        errors[field] = f"Must be a whole number between {lo} and {hi}."
        return 0
    if not lo <= value <= hi:
        errors[field] = f"Must be between {lo} and {hi}."
    return value


def validate_agent(form: dict[str, str]) -> tuple[AgentInput | None, dict[str, str]]:
    errors: dict[str, str] = {}

    name = (form.get("name") or "").strip()
    if not name:
        errors["name"] = "Name is required."
    query = (form.get("query") or "").strip()
    if not query:
        errors["query"] = "Query is required."

    domain_mode = (form.get("domain_mode") or "").strip()
    if domain_mode not in _DOMAIN_MODES:
        errors["domain_mode"] = "Choose none, include, or exclude."

    domains: list[str] = []
    if domain_mode in ("include", "exclude"):
        entries = [e for e in re.split(r"[,\n]", form.get("domains") or "") if e.strip()]
        invalid: list[str] = []
        for entry in entries:
            d = _normalize_domain(entry)
            if not d.isascii() or not _DOMAIN_RE.match(d):
                invalid.append(entry.strip())
            elif d not in domains:
                domains.append(d)
        if invalid:
            errors["domains"] = "Invalid domain(s): " + ", ".join(invalid)
        elif not domains:
            errors["domains"] = f"Enter at least one domain for {domain_mode} mode."
        elif len(domains) > _MAX_DOMAINS:
            errors["domains"] = f"At most {_MAX_DOMAINS} domains allowed."

    lookback_days = _parse_int(form, "lookback_days", 1, 30, errors)
    max_searches = _parse_int(form, "max_searches", 1, 20, errors)

    schedule_time: str | None = (form.get("schedule_time") or "").strip() or None
    if schedule_time is not None and not _TIME_RE.match(schedule_time):
        errors["schedule_time"] = "Use 24-hour HH:MM, e.g. 07:30."

    if errors:
        return None, errors
    return AgentInput(
        name=name, query=query, domain_mode=domain_mode, domains=domains,
        lookback_days=lookback_days, max_searches=max_searches,
        schedule_time=schedule_time,
    ), {}


# --- agents ---

def _row_to_agent(row: sqlite3.Row) -> Agent:
    return Agent(
        id=row["id"], name=row["name"], query=row["query"],
        domain_mode=row["domain_mode"], domains=json.loads(row["domains"]),
        lookback_days=row["lookback_days"], max_searches=row["max_searches"],
        schedule_time=row["schedule_time"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def create_agent(inp: AgentInput) -> int:
    now = _now()
    with closing(connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO agents (name, query, domain_mode, domains, lookback_days,"
            " max_searches, schedule_time, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (inp.name, inp.query, inp.domain_mode, json.dumps(inp.domains),
             inp.lookback_days, inp.max_searches, inp.schedule_time, now, now),
        )
        return cur.lastrowid


def get_agent(agent_id: int) -> Agent | None:
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    return _row_to_agent(row) if row else None


def list_agents() -> list[Agent]:
    with closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM agents ORDER BY name, id").fetchall()
    return [_row_to_agent(r) for r in rows]


def update_agent(agent_id: int, inp: AgentInput) -> None:
    with closing(connect()) as conn, conn:
        conn.execute(
            "UPDATE agents SET name=?, query=?, domain_mode=?, domains=?, lookback_days=?,"
            " max_searches=?, schedule_time=?, updated_at=? WHERE id=?",
            (inp.name, inp.query, inp.domain_mode, json.dumps(inp.domains),
             inp.lookback_days, inp.max_searches, inp.schedule_time, _now(), agent_id),
        )


def delete_agent(agent_id: int) -> None:
    with closing(connect()) as conn, conn:
        conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))


# --- runs ---

def _row_to_run(row: sqlite3.Row) -> Run:
    return Run(**{k: row[k] for k in row.keys()})


def create_run(agent_id: int, trigger_kind: str) -> tuple[int, bool]:
    with closing(connect()) as conn:
        try:
            with conn:
                cur = conn.execute(
                    "INSERT INTO runs (agent_id, trigger_kind, status, started_at)"
                    " VALUES (?, ?, 'running', ?)",
                    (agent_id, trigger_kind, _now()),
                )
            return cur.lastrowid, True
        except sqlite3.IntegrityError:
            # Either another run is already running (partial unique index) or
            # the agent doesn't exist (foreign key); only the former is benign.
            row = conn.execute(
                "SELECT id FROM runs WHERE agent_id = ? AND status = 'running'",
                (agent_id,),
            ).fetchone()
            if row is None:
                raise
            return row["id"], False


def get_run(run_id: int) -> Run | None:
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return _row_to_run(row) if row else None


def list_runs(agent_id: int, limit: int = 50) -> list[Run]:
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE agent_id = ? ORDER BY id DESC LIMIT ?",
            (agent_id, limit),
        ).fetchall()
    return [_row_to_run(r) for r in rows]


def latest_run(agent_id: int) -> Run | None:
    runs = list_runs(agent_id, limit=1)
    return runs[0] if runs else None


def _seen_urls(conn: sqlite3.Connection, agent_id: int, before_run_id: int) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT items.url FROM items JOIN runs ON items.run_id = runs.id"
        " WHERE runs.agent_id = ? AND runs.status = 'succeeded' AND runs.id < ?",
        (agent_id, before_run_id),
    ).fetchall()
    return {r["url"] for r in rows}


def seen_urls(agent_id: int, before_run_id: int) -> set[str]:
    with closing(connect()) as conn:
        return _seen_urls(conn, agent_id, before_run_id)


def finish_run(run_id: int, *, status: str, error: str | None,
               input_tokens: int, output_tokens: int, searches: int,
               items: list[FoundItem]) -> None:
    with closing(connect()) as conn, conn:
        row = conn.execute("SELECT agent_id FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            # Agent (and its runs) deleted mid-run; nothing left to record.
            return
        seen = _seen_urls(conn, row["agent_id"], run_id)
        conn.executemany(
            "INSERT INTO items (run_id, title, url, source, published, summary, seen_before)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(run_id, it.title, it.url, it.source, it.published, it.summary, it.url in seen)
             for it in items],
        )
        conn.execute(
            "UPDATE runs SET status=?, error=?, finished_at=?, input_tokens=?,"
            " output_tokens=?, searches=? WHERE id=?",
            (status, error, _now(), input_tokens, output_tokens, searches, run_id),
        )


def list_items(run_id: int) -> list[Item]:
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM items WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
    return [Item(**{k: r[k] for k in r.keys()} | {"seen_before": bool(r["seen_before"])})
            for r in rows]
