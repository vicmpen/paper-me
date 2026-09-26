"""FastAPI + HTMX front end for the news agents.

Server-rendered Jinja pages; HTMX is only used to poll a running run's status
and to swap it in after "Run now". Every form field is declared
`str = Form("")` so FastAPI never answers with its own JSON 422 — all
validation goes through `db.validate_agent` and re-renders the HTML form.

runner/scheduler/db are called as module attributes so tests can
monkeypatch them.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from webapp import db, runner, scheduler

load_dotenv()

_HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=_HERE / "templates")


def _hostname(url: str) -> str:
    # Provenance comes from the real URL, never from the model's `source` text.
    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def _when(ts: str | None) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return ts


templates.env.filters["hostname"] = _hostname
templates.env.filters["when"] = _when


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")

# Local-only app with no auth: any web page the user visits could otherwise
# POST here (create agents, fire paid runs, delete data), and DNS rebinding
# could read results. Pin the Host header and reject cross-site writes.
_LOCAL_HOSTS = ["127.0.0.1", "localhost"]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_LOCAL_HOSTS)


@app.middleware("http")
async def _reject_cross_site_posts(request: Request, call_next):
    if request.method == "POST":
        origin = request.headers.get("origin")
        cross_site = request.headers.get("sec-fetch-site") == "cross-site"
        if cross_site or (origin and urlparse(origin).hostname not in _LOCAL_HOSTS):
            return PlainTextResponse("cross-site request rejected", status_code=403)
    return await call_next(request)


@app.exception_handler(StarletteHTTPException)
async def _http_error(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(request, "404.html", {}, status_code=404)
    return PlainTextResponse(str(exc.detail), status_code=exc.status_code)


def _agent_or_404(agent_id: int) -> db.Agent:
    agent = db.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404)
    return agent


def _run_or_404(run_id: int) -> db.Run:
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404)
    return run


def _agent_to_form(agent: db.Agent) -> dict[str, str]:
    return {
        "name": agent.name, "query": agent.query, "domain_mode": agent.domain_mode,
        "domains": "\n".join(agent.domains), "lookback_days": str(agent.lookback_days),
        "max_searches": str(agent.max_searches), "schedule_time": agent.schedule_time or "",
    }


def _form_page(request: Request, form: dict[str, str], errors: dict[str, str],
               agent: db.Agent | None, status_code: int = 200):
    return templates.TemplateResponse(
        request, "agent_form.html",
        {"form": form, "errors": errors, "agent": agent}, status_code=status_code,
    )


def _status_partial(request: Request, run: db.Run):
    resp = templates.TemplateResponse(request, "_run_status.html", {"run": run})
    if run.status != "running":
        resp.headers["HX-Refresh"] = "true"
    return resp


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    rows = [(a, db.latest_run(a.id)) for a in db.list_agents()]
    return templates.TemplateResponse(request, "agents.html", {"rows": rows})


@app.get("/agents/new", response_class=HTMLResponse)
def new_agent(request: Request):
    form = {"name": "", "query": "", "domain_mode": "none", "domains": "",
            "lookback_days": "7", "max_searches": "5", "schedule_time": ""}
    return _form_page(request, form, {}, None)


@app.post("/agents")
def create_agent(request: Request, name: str = Form(""), query: str = Form(""),
                 domain_mode: str = Form(""), domains: str = Form(""),
                 lookback_days: str = Form(""), max_searches: str = Form(""),
                 schedule_time: str = Form("")):
    form = {"name": name, "query": query, "domain_mode": domain_mode, "domains": domains,
            "lookback_days": lookback_days, "max_searches": max_searches,
            "schedule_time": schedule_time}
    inp, errors = db.validate_agent(form)
    if inp is None:
        return _form_page(request, form, errors, None, status_code=422)
    agent_id = db.create_agent(inp)
    scheduler.sync_jobs()
    return RedirectResponse(f"/agents/{agent_id}", status_code=303)


@app.get("/agents/{agent_id}", response_class=HTMLResponse)
def agent_detail(request: Request, agent_id: int):
    agent = _agent_or_404(agent_id)
    runs = db.list_runs(agent_id)
    latest = runs[0] if runs else None
    shown = next((r for r in runs if r.status == "succeeded"), None)
    items = db.list_items(shown.id) if shown else []
    return templates.TemplateResponse(request, "agent_detail.html", {
        "agent": agent, "runs": runs, "run": latest, "shown": shown, "items": items,
    })


@app.get("/agents/{agent_id}/edit", response_class=HTMLResponse)
def edit_agent(request: Request, agent_id: int):
    agent = _agent_or_404(agent_id)
    return _form_page(request, _agent_to_form(agent), {}, agent)


@app.post("/agents/{agent_id}")
def update_agent(request: Request, agent_id: int, name: str = Form(""),
                 query: str = Form(""), domain_mode: str = Form(""),
                 domains: str = Form(""), lookback_days: str = Form(""),
                 max_searches: str = Form(""), schedule_time: str = Form("")):
    agent = _agent_or_404(agent_id)
    form = {"name": name, "query": query, "domain_mode": domain_mode, "domains": domains,
            "lookback_days": lookback_days, "max_searches": max_searches,
            "schedule_time": schedule_time}
    inp, errors = db.validate_agent(form)
    if inp is None:
        return _form_page(request, form, errors, agent, status_code=422)
    db.update_agent(agent_id, inp)
    scheduler.sync_jobs()
    return RedirectResponse(f"/agents/{agent_id}", status_code=303)


@app.post("/agents/{agent_id}/delete")
def delete_agent(agent_id: int):
    db.delete_agent(agent_id)
    scheduler.sync_jobs()
    return RedirectResponse("/", status_code=303)


@app.post("/agents/{agent_id}/run")
def run_now(request: Request, agent_id: int):
    try:
        run_id = runner.start_run(agent_id, "manual")
    except LookupError:
        raise HTTPException(status_code=404)
    if request.headers.get("HX-Request"):
        return _status_partial(request, _run_or_404(run_id))
    return RedirectResponse(f"/agents/{agent_id}", status_code=303)


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, run_id: int):
    run = _run_or_404(run_id)
    return templates.TemplateResponse(request, "run_detail.html", {
        "run": run, "agent": db.get_agent(run.agent_id), "items": db.list_items(run_id),
    })


@app.get("/runs/{run_id}/status", response_class=HTMLResponse)
def run_status(request: Request, run_id: int):
    run = db.get_run(run_id)
    if run is None:
        # Run vanished (agent deleted mid-run). htmx ignores 4xx swaps, so a
        # 404 here would leave the page polling forever; send it home instead.
        return HTMLResponse("", headers={"HX-Redirect": "/"})
    return _status_partial(request, run)
