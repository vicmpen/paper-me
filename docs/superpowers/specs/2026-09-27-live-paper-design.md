# Live paper — design (sub-project 1: paper slice)

Date: 2026-09-27
Status: approved in chat, section by section

Builds on `2026-09-26-web-news-agents-design.md` and
`2026-09-27-search-providers-design.md`. Everything in those specs stays as
written unless changed below.

## Goal

Each agent gets its own newspaper. The latest run is today's edition; earlier
runs are back issues. The edition is laid out by Claude from a fixed catalog of
newspaper components (the json-render pattern: a guardrailed catalog, the model
emits a spec, a renderer maps it to components) and it streams onto the page
block by block while Claude composes it. The main story, when the results have
one, is identified from the results and labelled as such.

This is the first step of splitting the app into a Python backend and a React
frontend. The design system created here (with Impeccable) is app-wide and
paper-first.

## Decisions (from the user)

- One paper per agent: latest run = today's edition, earlier runs = back issues.
- Claude composes each edition's layout from a component catalog.
- "Live" means streaming: components appear as Claude composes them.
- Design system covers the whole app, paper-first, built with Impeccable.
- Split the app: Python backend, React + json-render frontend (the Python-only
  alternative was not meaningfully faster: run time is dominated by LLM and
  search calls, not rendering).
- Sequence: this paper slice first, alongside the existing Jinja pages;
  porting the remaining pages and removing Jinja/HTMX is sub-project 2.
- The main story must be clearly identified from the results, and only when
  one exists.

## Assumptions

- Frontend toolchain: Vite + React 19 + TypeScript + React Router, npm (ships
  with Node 22, already installed). Plain CSS with custom-property tokens and
  CSS modules; no Tailwind, no shadcn — the newspaper look is bespoke.
- json-render packages: `@json-render/core` and `@json-render/react`, with Zod
  for the catalog. Exact versions and API names are pinned in the first plan
  task (see Risks).
- New Python dependency: `jsonschema` (validates streamed elements against the
  exported catalog schema). SSE uses FastAPI's built-in
  `fastapi.sse.EventSourceResponse`; no other new Python dependency.
- The compose call uses `config.WEBAPP_MODEL` and `config.WEBAPP_EFFORT`, like
  the plan and write calls.
- Single local user; no auth. The existing Host pin and cross-site POST guard
  cover the new routes because the frontend is served same-origin.

## Architecture

```
webapp/                          Python backend
  api.py                         NEW  JSON + SSE routes under /api, included in app.py
  compose.py                     NEW  compose stage: Claude stream -> JSONL patches -> validate -> store
  edition_spec.py                NEW  patch applier, element validator, finalize rules (shared by
                                      compose and fallback)
  fallback_edition.py            NEW  rules-based patches from answer + items
  catalog/                       NEW  generated, committed: catalog.prompt.txt, catalog.schema.json
  app.py                         + include api router, serve frontend/dist at /paper/*,
                                   "Read the paper" link on agent_detail.html
  db.py                          + runs.stage, runs.edition, edition_lines table, save_results()
  runner.py                      + on_stage callback, save results before compose, compose step
  search_agent.py                + optional on_stage callback
frontend/                        NEW  Vite + React 19 + TypeScript
  src/catalog/                   Zod catalog (source of truth) + React registry
  src/paper/                     paper page, masthead, back-issues rail, sources, useEditionStream
  src/styleguide/                component library page with fixture specs
  src/styles/                    tokens.css + component CSS (from Impeccable)
  scripts/export-catalog.ts      writes webapp/catalog/* from the Zod catalog
PRODUCT.md, DESIGN.md            NEW  Impeccable context (repo root)
```

**Serving.** FastAPI serves `frontend/dist` at `/paper/*` with an `index.html`
fallback so client-side routes resolve. If `frontend/dist` does not exist,
`/paper/*` returns a plain page saying to run `npm run build` (status 503), not
a 500. The existing Jinja pages keep working; the agent page links to
`/paper/{agent_id}`.

**Dev.** `python -m webapp` (port 8000) and `npm run dev` (Vite) side by side;
Vite proxies `/api` to `127.0.0.1:8000`. **Prod.** `npm run build` once, then
`python -m webapp` serves everything.

**Catalog sync.** The Zod catalog is the only definition of the components.
`npm run export-catalog` writes `webapp/catalog/catalog.prompt.txt` (from
`catalog.prompt()`) and `webapp/catalog/catalog.schema.json` (one JSON Schema
per component's props). Both files are committed. A Vitest test regenerates
them in memory and fails if they differ from the committed files.

## Component catalog — binding

All factual fields carry `cites`: an array of 1–10 integers, each a source
number (1-based position in the run's items). Limits below catch garbage, not
style; the compose prompt asks for tighter writing.

| Component | Props | Notes |
|---|---|---|
| `Page` | none; `children` = ordered element ids | Root. A CSS grid; children flow in order. |
| `LeadStory` | `kicker?` (≤40), `headline` (≤160), `dek` (≤400), `body` (1–3 strings, ≤1200 each), `cites` | The main story. At most one; first child of `Page` if present. |
| `Story` | `kicker?`, `headline`, `dek`, `cites`, `weight`: `"major"` \| `"minor"` | Weight picks its grid span. |
| `Briefs` | `title` (≤40), `items`: 1–8 × {`text` (≤500), `cites`} | Short one-line items. |
| `Split` | `title` (≤80), `sides`: exactly 2 × {`label` (≤40), `direction`: `"up"` \| `"down"` \| `"neutral"`, `points`: 1–6 × {`text`, `cites`}} | "What pushes it up vs down", pros/cons. |
| `Figures` | `items`: 1–4 × {`value` (≤24), `label` (≤80), `cites`} | Key numbers, verbatim from sources. |
| `Timeline` | `title` (≤80), `events`: 2–10 × {`date` (≤24, free text), `text`, `cites`} | Dated sequence. |
| `Analysis` | `heading` (≤60), `paragraphs` (1–3, ≤1200 each), `cites` | Labelled synthesis ("What it means"). |

Guardrails:

- No URLs, images, or HTML in any prop. Links are resolved on the frontend from
  `cites` against the run's items, so Claude cannot invent a link.
- No quote component: sources give summaries, not quotes.
- The grid span of each component type is fixed by the design system; Claude
  chooses components, order, and story weight only.
- json-render state, actions, visibility, and watchers are not used. Patches
  touching `/state` or elements carrying `visible`/`watch` are rejected.

Not generated by Claude (plain React around the renderer): masthead (agent name
as paper title, date, edition number, live indicator), back-issues rail,
numbered sources list, and an "Update" tag on any story citing a source whose
`seen_before` is true.

## Main story rule — binding

"Outlets" of an element = the distinct hostnames of the items its `cites`
point to (same `hostname` normalisation the Jinja templates use).

- **Composed editions.** The compose prompt defines the main story as the event
  reported by the most independent outlets, and central to the agent's topic
  (coverage first, relevance breaks ties). Claude groups sources into stories.
  If no story clearly leads, Claude omits `LeadStory`.
- **Server check at finalize.** A `LeadStory` stands only if its outlets ≥ 2
  and strictly greater than the outlets of every other element with `cites`
  at story level (`Story`, and each `Briefs` item, `Split` point, `Timeline`
  event counted individually). Otherwise the backend appends one `replace`
  patch turning it into `Story` with `weight: "major"` (same kicker, headline,
  dek, cites; body dropped). This is an ordinary patch: viewers see it change
  in place, no reset.
- **Display.** The lead carries a "Main story" label and "Reported by N
  sources", N computed by the frontend from its cites' outlets. With no lead,
  the edition opens with a one-line note that no single story dominates
  (final wording from Impeccable).

## Backend

### Data model and migration (`webapp/db.py`)

- `runs.stage TEXT` — `planning` | `searching` | `writing` | `composing` |
  NULL (not started or finished). Cleared by `finish_run`.
- `runs.edition TEXT` — `composed` | `fallback` | `empty` | NULL (run failed,
  or run predates this feature).
- New table `edition_lines(id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL
  REFERENCES runs(id) ON DELETE CASCADE, seq INTEGER NOT NULL, line TEXT NOT
  NULL, UNIQUE(run_id, seq))`. `seq` starts at 1 per run.
- Columns are added through the existing `_add_missing_columns` migration.
- New `save_results(run_id, *, items, answer, provider, searches)`: inserts
  items (with `seen_before`, exactly as `finish_run` does today) and stores
  answer/provider/searches while the run stays `running`. `finish_run` keeps
  its signature and still inserts exactly the `items` it is given; the success
  path passes `items=[]` (already saved) and failure paths pass `[]` as today.
  It gains an `edition` argument, records status, error, tokens,
  `finished_at`, `edition`, and clears `stage`. Its `answer`/`provider`
  arguments become optional overrides (`None` leaves the saved values).
- New `set_stage(run_id, stage)`, `append_edition_lines(run_id, lines)`,
  `replace_edition_lines(run_id, lines)`, `edition_lines_after(run_id, seq)`.

### Runner and pipeline (`webapp/runner.py`, `webapp/search_agent.py`)

```
plan -> search -> write        (search_agent.run_search, unchanged except on_stage)
save_results                   (answer + items persisted; run still "running")
compose                        (compose.compose_edition; never raises)
finish_run(status="succeeded", edition=..., tokens = search + compose)
```

- `run_search(..., on_stage=None)` calls `on_stage("planning" | "searching" |
  "writing")` at each step; the default is a no-op, so existing tests are
  unaffected. The runner passes `lambda s: db.set_stage(run_id, s)`.
- The runner sets stage `composing` before calling compose.
- A run whose write stage produced zero items (including the no-hits path)
  skips compose: `edition = "empty"`.
- Failures before `save_results` keep today's behaviour: run `failed`, no
  edition.

### Compose (`webapp/compose.py`)

- One streaming call: `client.messages.stream(...)` with `COMPOSE_MAX_TOKENS =
  8000` and its own timeout `COMPOSE_TIMEOUT_S = 120`. System prompt =
  `catalog.prompt.txt` + paper rules (main story rule, cite rules, no quotes,
  no invented numbers, tight newspaper headlines, follow the agent's response
  instructions where they shape content). User message: today's date, topic,
  response instructions, the answer, and the numbered items (number, title,
  outlet, published date, summary).
- The text stream is split on newlines. Each complete line goes through
  `edition_spec`:
  1. parse as a JSON Patch op; only `add`, `replace`, `remove`, only paths
     `/root`, `/elements/<id>`, or below `/elements/<id>/`;
  2. apply to a server-side copy of the spec;
  3. validate the touched element against `catalog.schema.json` for its
     `type`, and every `cites` value in `1..k` (k = number of items);
  4. if valid, append to `edition_lines`; if not, revert the copy, drop the
     line, and count it.
- **Finalize** when the stream ends normally: root is a `Page`; every child id
  exists; at most 12 elements; at most one `LeadStory` and, if present, it is
  the first child. Then the main story check (may append the demotion patch).
  Passing → `edition = "composed"`.
- **Fallback** when finalize fails, the stream errors or times out, or
  `stop_reason` is `max_tokens`/`refusal`: `replace_edition_lines` with the
  fallback edition's lines → `edition = "fallback"`. Dropped-line count and
  fallback reason are logged per run.
- Returns `(edition_kind, input_tokens, output_tokens)`; catches every
  exception internally.

### Fallback edition (`webapp/fallback_edition.py`)

Pure function of `(answer, items)` → list of JSONL patch lines, validated by
the same `edition_spec` code (tests assert it always passes).

1. Parse answer bullets (lines starting `- ` or `* `): text with `[n]` markers
   removed, and cites = the in-range `[n]` numbers.
2. Lead: the bullet with the most outlets, if ≥ 2 and strictly more than every
   other bullet. Lead headline = title of its first cited item (a trailing
   `" | <site>"` segment stripped); dek = that item's summary; body = [bullet
   text]; cites = bullet cites. Otherwise no lead.
3. Stories: up to 3 items not cited by the lead, in item order →
   `Story` weight `minor` (headline = cleaned title, dek = summary, cites =
   [n]).
4. Briefs ("In brief"): the remaining bullets. If the answer has no bullets
   but has text → one `Analysis` ("Summary") with its paragraphs. If there is
   no answer (runs predating the write stage) → remaining items as briefs
   (text = cleaned title).

Old runs with items but no `edition_lines` get this edition generated on the
fly by the stream endpoint; it is not stored.

### API (`webapp/api.py`)

- `GET /api/agents/{id}/paper` → `{agent: {id, name, query}, current_run_id,
  editions: [{run_id, started_at, finished_at, status, edition, error}]}`,
  newest first (same cap as `list_runs`).
- `GET /api/runs/{id}/sources` → `[{n, title, url, source, published, summary,
  seen_before}]`.
- `POST /api/agents/{id}/run` → `{run_id}` (reuses `runner.start_run`; if a run
  is already in progress, returns that run's id). Covered by the existing
  cross-site POST guard.
- `GET /api/runs/{id}/edition/stream` → SSE (`EventSourceResponse`):
  - `status` — `{status, stage}` whenever either changes;
  - `patch` — `id` = seq, `data` = one JSONL line;
  - `reset` — the streamed lines were replaced (fallback); client clears and
    the replacement lines follow as `patch` events;
  - `done` — `{status, edition, error}`; the stream then ends.
  The endpoint checks the DB every 250 ms, honours `Last-Event-ID` (resume
  after that seq), and stops on `done` or client disconnect. Unknown run → 404.
  Finished runs replay their lines and send `done` immediately — one endpoint
  for live editions and back issues.

## Frontend

- **Routes.** `/paper/:agentId` — the in-progress run if there is one
  (streaming), else the latest succeeded edition; if the latest run failed, a
  banner says it didn't go to press, with its error. `/paper/:agentId/:runId` —
  a specific edition. `/paper/styleguide` — the component library.
- **Page anatomy.** Masthead (paper name, date, edition number, "Go to press"
  button → `POST /api/agents/{id}/run`, then follows the new run) → status
  strip while streaming (stage labels: planning, searching, writing, laying out
  the page) → json-render `<Renderer>` → numbered sources list → back-issues
  rail (failed runs listed as "Didn't go to press").
- **`useEditionStream(runId)`.** Opens an `EventSource` on the stream endpoint;
  feeds each `patch` line into `createSpecStreamCompiler`; `reset` clears the
  compiler; `done` closes the source and exposes the final status. Exposes
  `{spec, status, stage, edition, error}`. (`useUIStream` is not used: it
  POSTs to trigger generation, while here runs are started by the backend.)
- **Citations.** A `SourcesProvider` fetches `/api/runs/{id}/sources`;
  components render `cites` as superscript links to the sources list and the
  source URL. The main-story "Reported by N sources" count and the "Update"
  tag come from the same data.
- **Motion.** New blocks animate in as they arrive; details from DESIGN.md,
  and reduced-motion is respected.
- **Styleguide.** Renders every catalog component from fixture specs, including
  edge cases: no lead, single source, demoted lead, long headlines, 12
  elements, empty edition, fallback edition; plus a looped replay of a
  recorded stream to check arrival motion. Fixtures double as test inputs.

## Design system (Impeccable)

1. `/impeccable init` → `PRODUCT.md` (interviews the user; seeded with the
   decisions above).
2. New-work for the paper surface in Read mode → visual world (type, colour,
   grid, motion) → `DESIGN.md` and `frontend/src/styles/tokens.css`.
3. Catalog components, masthead, rail, and styleguide are built against the
   tokens.
4. `/impeccable critique` and `/impeccable polish` on the styleguide and a live
   edition before the slice is done.
5. Sub-project 2 applies the same DESIGN.md to the ported pages.

## Error handling

| Case | Behaviour |
|---|---|
| Plan/search/write fails | Run `failed` (unchanged); stream sends `done` with sanitised error; paper shows latest good edition + banner. |
| Compose fails, truncates, or yields an invalid spec | Fallback edition; run `succeeded`; reason and dropped-line count logged. |
| Invalid streamed line | Dropped, counted, logged; stream continues. |
| Connection drops | `EventSource` reconnects; server resumes after `Last-Event-ID`. |
| Agent deleted mid-run | Lines cascade away; stream 404 → "not found" on the paper. |
| Server restart mid-run | Existing startup sweep marks the run failed; stream sends `done`. |
| Zero items | `edition = "empty"`; paper shows an empty-edition state. |
| Frontend not built | `/paper/*` returns the "run npm run build" page (503). |

## Testing

TDD, backend first.

- **pytest**
  - `edition_spec`: allowed/rejected ops and paths, unknown component types,
    schema violations, cite range, `/state` and `visible`/`watch` rejected,
    revert on invalid line, finalize rules, main story check (single outlet,
    tie, winner) and the demotion patch.
  - `fallback_edition`: lead selection (clear winner, tie → no lead, single
    outlet → no lead), title cleanup, no-bullets and no-answer paths; output
    always validates and finalizes.
  - `compose` with a fake streaming client: chunks splitting a line mid-JSON,
    invalid lines dropped, truncation / API error / refusal → fallback, token
    accounting.
  - Runner: stage updates in order, results saved before compose, compose
    failure still `succeeded` with `fallback`, zero items → `empty`.
  - DB: migration adds columns/table to an old DB; `save_results` +
    `finish_run` don't double-insert items.
  - API: paper and sources JSON, "Go to press" (including cross-site guard and
    already-running case), SSE replay, tail of a live run, `Last-Event-ID`
    resume, `reset`, `done` for succeeded/failed runs, on-the-fly fallback for
    old runs, 404 for unknown runs, 503 page when the frontend isn't built.
- **Vitest + Testing Library**
  - Each component renders from the styleguide fixtures; cites resolve to the
    right sources; "Main story" / "Reported by N sources" / "Update" appear
    when they should.
  - `useEditionStream` against a mock `EventSource` (patch, reset, done,
    reconnect).
  - Catalog drift check.
- **Manual** — the styleguide page, and a real run of the oil agent watched
  live in the browser; Impeccable critique/polish.

## Risks — verify first

The first plan task installs the json-render packages and confirms, against
the installed version, before any other frontend work:

- the names and signatures of `defineCatalog`, `defineRegistry`, `Renderer`,
  `createSpecStreamCompiler`, and `catalog.prompt()`;
- that `catalog.prompt()` instructs the JSONL-patch (SpecStream) format and how
  it expects `Page.children` to be built (inline list vs. appended ids), so
  the validator and fallback emit the same shape;
- how to get a JSON Schema per component (json-render export if provided,
  otherwise `z.toJSONSchema` on each props schema);
- the Zod and React versions it requires.

If any of these differ from this spec, the plan adapts the affected task and
notes the change; the architecture does not change.

## Out of scope

- Porting agent list, forms, and run pages to React; removing Jinja/HTMX
  (sub-project 2).
- Token-level streaming inside a block (blocks appear when complete).
- Images, quotes, cross-agent front page, email/PDF editions.
- Browser end-to-end test framework.
