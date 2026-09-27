# Live paper — design (sub-project 1: paper slice)

Date: 2026-09-27
Status: approved in chat, section by section; reviewed (Fable, xhigh) and
revised; bottom line and visual direction added

Builds on `2026-09-26-web-news-agents-design.md` and
`2026-09-27-search-providers-design.md`. Everything in those specs stays as
written unless changed below. Product context: `PRODUCT.md`. Visual
direction: `.impeccable/surfaces/frontend-src-paper-paperpage-tsx.md`.

## Goal

Each agent gets its own newspaper. The latest run is today's edition; earlier
runs are back issues. Claude lays each edition out from a fixed catalog of
newspaper components, following the json-render pattern: a guardrailed
catalog, the model emits a spec, and a renderer maps it to components. The
edition streams onto the page block by block while Claude composes it. The
main story, when the results have one, is identified from the results and
labelled as such.

This is the first step of splitting the app into a Python backend and a React
frontend. The design system created here (with Impeccable) is app-wide and
paper-first.

## Decisions (from the user)

- One paper per agent: latest run = today's edition, earlier runs = back issues.
- Claude composes each edition's layout from a component catalog.
- "Live" means streaming: components appear as Claude composes them.
- Design system covers the whole app, paper-first, built with Impeccable.
  Visual direction chosen: **Orienteering Course** (code-led build).
- Split the app: Python backend, React + json-render frontend. The
  Python-only alternative was not meaningfully faster, because run time is
  dominated by LLM and search calls, not rendering.
- Sequence: this paper slice first, alongside the existing Jinja pages;
  sub-project 2 ports the remaining pages and removes Jinja/HTMX;
  sub-project 3 makes the app public and multi-user.
- The main story must be clearly identified from the results, and only when
  one exists.

## Assumptions

- Frontend toolchain: Vite + React 19 + TypeScript + React Router, npm.
  `@json-render/core` and `@json-render/react` pinned at `0.21.0` (peers:
  `zod ^4`, `react ^19.2.3`). Plain CSS with custom-property tokens and CSS
  modules; no Tailwind, no shadcn.
- New Python dependency: `jsonschema`. SSE uses FastAPI's built-in
  `fastapi.sse` (`EventSourceResponse`, `ServerSentEvent`).
- The compose call uses `config.WEBAPP_MODEL` and `config.WEBAPP_EFFORT`.
- This slice stays local and single-user with no auth. The existing Host pin
  and cross-site POST guard cover the new routes (verified: they pass through
  the Vite dev proxy unchanged; no CORS). See "Keeping the public app open".

## json-render facts (verified against 0.21.0)

- The exports exist: `defineCatalog` and `createSpecStreamCompiler` (core);
  `defineRegistry`, `Renderer` and `JSONUIProvider` (react).
- `<Renderer>` must be wrapped in `<JSONUIProvider registry>`; a bare
  `Renderer` throws. It renders parents whose children have not arrived yet,
  skipping them with a `console.warn` each render. Expect noisy logs while
  streaming and in tests.
- SpecStream is JSONL of RFC 6902 ops. An element is `{type, props,
  children}`. Children are declared inline in the parent's `children` array
  before the child elements exist, and leaves need `children: []`.
- The compiler buffers partial trailing lines, skips bad JSON, creates the
  path on a `replace` to a missing path, and has `reset()`.
- `catalog.prompt()` is **not** used: it instructs state, `repeat`, dynamic
  props, actions, `visible`/`watch`, and invented sample data.
- `catalog.jsonSchema()` gives no per-component prop schemas; Zod 4's
  `z.toJSONSchema(props)` does.
- `catalog.validate()` does not validate props, so the Python validator is
  the real guard.

## Architecture

```
webapp/                          Python backend
  api.py                         NEW  JSON + SSE routes under /api, included in app.py
  edition_events.py              NEW  edition_events(run_id): async event source (DB poll today)
  compose.py                     NEW  compose stage: Claude stream -> JSONL patches -> validate -> store
  edition_spec.py                NEW  patch applier, element validator, finalize rules
  fallback_edition.py            NEW  rules-based patches from answer + items (pure)
  catalog/                       NEW  generated, committed: catalog.prompt.txt, catalog.schema.json
  app.py                         + include api router, serve the SPA at /paper/*,
                                   "Read the paper" link on agent_detail.html
  db.py                          + runs.stage, runs.edition, edition_lines, save_results()
  runner.py                      + on_stage, save results before compose, compose step
  search_agent.py                + optional on_stage callback
frontend/                        NEW  Vite + React 19 + TypeScript
  src/api.ts                     every fetch and the EventSource constructor (relative /api URLs)
  src/catalog/                   Zod catalog (source of truth) + React registry
  src/paper/                     paper page, masthead, back issues, sources, useEditionStream
  src/styleguide/                component library page with fixture specs
  src/styles/                    tokens.css + component CSS (from Impeccable)
  scripts/export-catalog.ts      writes webapp/catalog/* from the Zod catalog
```

**Serving.** Vite builds with `base: "/paper/"`; React Router uses
`basename="/paper"`. FastAPI mounts `frontend/dist/assets` at `/paper/assets`
and adds a catch-all `GET /paper/{path:path}` that returns
`frontend/dist/index.html` as a `FileResponse`. `StaticFiles(html=True)`
does not fall back to `index.html` for client routes, so it can't be used
here. If `index.html` is missing, the route raises
`HTTPException(503, "Frontend not built: run npm run build")`, which the
existing error handler returns as plain text. The existing Jinja pages keep
working; the agent page links to `/paper/{agent_id}`.

**Dev.** `python -m webapp` (port 8000) and `npm run dev` side by side; Vite
proxies `/api` to `127.0.0.1:8000`. **Prod.** `npm run build` once, then
`python -m webapp` serves everything.

**Catalog sync.** The Zod catalog is the only definition of the components.
`npm run export-catalog` writes:

- `webapp/catalog/catalog.prompt.txt`, a hand-authored prompt covering:
  - the JSONL format: `/root` first; `add /elements/<id>` with exactly
    `{type, props, children}`; children inline in the parent; `children: []`
    on leaves;
  - the component list generated from `catalog.data.components` (name,
    description, compact props schema).
- `webapp/catalog/catalog.schema.json`: `z.toJSONSchema(props)` for each
  component (draft 2020-12, `additionalProperties: false`).

Both files are committed. A Vitest test regenerates them in memory and fails
if they differ from the committed files.

## Component catalog — binding

All factual fields carry `cites`: an array of 1–10 integers, each a source
number (the 1-based position in the run's items). The limits below catch
garbage, not style; the compose prompt asks for tighter writing.

| Component | Props | Notes |
|---|---|---|
| `Page` | `bottomLine?`: {`text` (≤280), `cites`}; `children` = ordered element ids | Root. The bottom line is the one-sentence "what to know"; it is optional. |
| `LeadStory` | `kicker?` (≤40), `headline` (≤160), `dek` (≤400), `body` (1–3 strings, ≤1200 each), `cites` | The main story. At most one; first child of `Page` if present. |
| `Story` | `kicker?`, `headline`, `dek`, `cites`, `weight`: `"major"` \| `"minor"` | Weight picks its span. |
| `Briefs` | `title` (≤40), `items`: 1–8 × {`text` (≤500), `cites`} | Short one-line items. |
| `Split` | `title` (≤80), `sides`: exactly 2 × {`label` (≤40), `direction`: `"up"` \| `"down"` \| `"neutral"`, `points`: 1–6 × {`text`, `cites`}} | Up versus down, pros and cons. |
| `Figures` | `items`: 1–4 × {`value` (≤24), `label` (≤80), `cites`} | Key numbers, verbatim from sources. |
| `Timeline` | `title` (≤80), `events`: 2–10 × {`date` (≤24, free text), `text`, `cites`} | Dated sequence. |
| `Analysis` | `heading` (≤60), `paragraphs` (1–3, ≤1200 each), `cites` | Labelled synthesis ("What it means"). |

**Element rules.**

- An element is exactly `{type, props, children}`, and any other key (`on`,
  `repeat`, `slots`, `visible`, `watch`) is rejected.
- `children` is a list of strings, and is non-empty only on `Page`.
- Prop values are plain JSON, so the schema's `type: string` rejects
  `{"$state": ...}`.
- Allowed ops are `add`, `replace` and `remove`, only on `/root`,
  `/elements/<id>`, or paths below `/elements/<id>/`. `/state`, `move`,
  `copy` and `test` are rejected.

**Guardrails.**

- No URLs, images or HTML in any prop. Links are resolved on the frontend
  from `cites` against the run's items, so Claude cannot invent a link.
- No quote component: the sources are summaries, not quotes.
- Each component type's grid span is fixed by the design system. Claude
  chooses only the components, their order and each story's weight.

**Not generated by Claude.** These are plain React around the renderer:

- the masthead (the agent name as paper title, date, edition number, live
  state);
- the back-issues rail;
- the numbered sources list;
- the "Update" tag on any story citing a source whose `seen_before` is true.

## Main story rule — binding

**Outlets.** An element's outlets are the distinct hostnames of the items its
`cites` point to, lower-cased, with a leading `www.` stripped (the same
function in Python and TypeScript).

**Composed editions (prompt).** The main story is the event reported by the
most independent outlets:

- Claude groups the sources into stories. Relevance to the agent's topic only
  decides which sources count as on-topic before counting.
- `LeadStory.cites` must list every source that reports that event.
- If two stories tie on coverage, or no story clearly leads, there is no main
  story and Claude omits `LeadStory`.

**Server check at finalize.** A `LeadStory` stands only if it has at least 2
outlets and strictly more than every *competitor*.

- Competitors are `Story` elements and individual `Briefs` items whose outlet
  set is not a subset of the lead's outlet set.
- `Split`, `Timeline`, `Figures`, `Analysis` and `bottomLine` never compete.
  They typically cite the lead's own sources.
- If the lead fails, the backend appends one `replace` patch turning it into
  `Story` with `weight: "major"` (same kicker, headline, dek and cites; the
  body is dropped). Viewers see it change in place.

**Display.** The lead carries a "Main story" label and "Reported by N
outlets". N is computed by the frontend from its cites. With no lead, the
edition opens with a one-line note that no single story dominates. Impeccable
decides the final wording.

## Backend

### Data model and migration (`webapp/db.py`)

- `runs.stage TEXT` — `planning` | `searching` | `writing` | `composing` |
  NULL. Cleared by `finish_run` and by the startup sweep (its UPDATE also sets
  `stage = NULL`).
- `runs.edition TEXT` — `composed` | `fallback` | `empty` | NULL (the run
  failed, or predates this feature).
- New table `edition_lines(id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL
  REFERENCES runs(id) ON DELETE CASCADE, seq INTEGER NOT NULL, line TEXT NOT
  NULL, UNIQUE(run_id, seq))`. `seq` starts at 1 per run.
- Columns are added through the existing `_add_missing_columns` migration.
- **Lines only append while the run is `running`**, via
  `append_edition_lines(run_id, lines)`.
- New `save_results(run_id, *, items, answer, provider, searches)`:
  - inserts the items, with `seen_before` computed exactly as `finish_run`
    does today;
  - stores answer, provider and searches while the run stays `running`;
  - is called for zero items too.
- `finish_run` keeps inserting exactly the `items` it is given. The success
  path passes `[]`, because `save_results` already inserted them, and failure
  paths pass `[]` as today. It gains:
  - `edition` (str or None);
  - `edition_lines` (list or None). When given, it deletes the run's lines
    and inserts these, renumbered from 1, **in the same transaction** that
    sets status, error, tokens, `finished_at` and `edition`, and clears
    `stage`.

  Its `answer`/`provider` arguments become optional overrides via `COALESCE`;
  `None` keeps the saved values.
- New `set_stage(run_id, stage)`, `edition_lines_after(run_id, seq)`,
  `all_edition_lines(run_id)`. There is no SQL outside `db.py`.

### Runner and pipeline (`webapp/runner.py`, `webapp/search_agent.py`)

```
plan -> search -> write        search_agent.run_search (unchanged except on_stage)
save_results                   answer + items persisted; run still "running"
set_stage("composing"); compose (never raises; appends lines live)
finish_run(status="succeeded", edition=..., edition_lines=<fallback lines or None>,
           tokens = search + compose)
```

- `run_search(..., on_stage=None)` calls `on_stage("planning" | "searching" |
  "writing")`. The default is a no-op, so existing tests are unaffected.
- **Zero items**, whether from the no-hits path or an answer citing nothing:
  `save_results` still runs, compose is skipped, and `edition = "empty"`. The
  paper shows the stored answer in an empty-edition state.
- Failures before `save_results` keep today's behaviour: the run is `failed`
  and has no edition.
- The compose stage's tokens are also logged on their own line per run, so
  cost per stage is known.

### Compose (`webapp/compose.py`)

- **The call.** One `client.messages.stream(...)` with
  `COMPOSE_MAX_TOKENS = 16000`.
  - The system prompt is `catalog.prompt.txt` plus paper rules: the main
    story rule, cite rules, no quotes, no invented numbers, tight newspaper
    headlines, the optional one-sentence `bottomLine`, and following the
    agent's response instructions where they shape content.
  - The user message holds today's date, the topic, the response
    instructions, the answer, and the numbered items (number, title, outlet,
    published date, summary).
- **Deadline.** `COMPOSE_DEADLINE_S = 120` is a wall-clock deadline checked
  in the line loop. It is separate from the httpx per-read timeout, which a
  stream that keeps emitting never trips. When it passes, the stream is
  closed and the edition falls back.
- **Per line.** The text stream is split on newlines. Each complete line goes
  through `edition_spec`:
  1. parse it and check the op and path (see Element rules);
  2. apply it to a server-side copy of the spec;
  3. validate the touched element: the wrapper rules, the props against
     `catalog.schema.json` for its `type`, and every `cites` value in `1..k`
     (k = the number of items);
  4. if it is valid, `append_edition_lines`; if not, revert the copy, drop
     the line and count it.
- **Finalize** when the stream ends normally:
  - root is a `Page`, every child id exists, there are at most 12 elements,
    and there is at most one `LeadStory`, first if present;
  - then the main story check, which may append the demotion patch;
  - if it passes, `edition = "composed"`.
- **Fallback.** The edition falls back when finalize fails, the stream errors
  or passes its deadline, or `stop_reason` is `max_tokens`, `refusal` or
  `model_context_window_exceeded`. Compose returns the fallback edition's
  lines for `finish_run` to swap in atomically, and `edition = "fallback"`.
  The dropped-line count and the fallback reason are logged per run.
- **Result.** Returns `(edition_kind, fallback_lines | None, input_tokens,
  output_tokens)` and catches every exception internally.

### Fallback edition (`webapp/fallback_edition.py`)

A pure function of `(answer, items)` that returns JSONL patch lines. It uses
the same `edition_spec` validation, and tests assert that it always passes.

1. **Bullets.** Parse the answer's bullets (lines starting `- ` or `* `).
   - Cite markers match `\[(\d+(?:\s*,\s*\d+)*)\]`. A bullet's cites are its
     in-range numbers, de-duplicated and capped at 10. Its text is the bullet
     with the markers removed.
2. **Lead.** The lead is the bullet with the most outlets, if it has at least
   2 and strictly more than every other bullet. Otherwise there is no lead.
   - Headline: the title of its first cited item, with a trailing
     `" | <site>"` segment stripped.
   - Dek: that item's summary. Body: [the bullet text]. Cites: the bullet's
     cites.
   - `Page.bottomLine` is the lead bullet's text and cites; it is absent when
     there is no lead.
3. **Stories.** Up to 3 items not cited by the lead, in item order, become
   `Story` with weight `minor`: headline = the cleaned title, dek = the
   summary, cites = [n].
4. **Briefs** ("In brief") hold the remaining bullets that have at least one
   in-range cite, capped at 8. Bullets without cites are dropped.
   - If the answer has no bullets but has text, it becomes one `Analysis`
     ("Summary") with its paragraphs (capped at 3). Its cites are the
     in-range `[n]` in the text, or else `[1..min(k,10)]`.
   - With no answer at all (runs from before the write stage), the remaining
     items become briefs, with text = the cleaned title.
5. **Limits.** Every string is truncated to its catalog limit with an
   ellipsis.

Old runs with items but no `edition_lines` get this edition generated on the
fly; it is not stored. Old succeeded runs with zero items and no lines count
as `empty`.

### Event source and API

**`webapp/edition_events.py`.** `async def edition_events(run_id)` yields
`(kind, payload)` tuples and knows nothing about SSE. It polls the DB every
250 ms (`await asyncio.sleep`), so pub/sub can replace the poll later in one
place. Per connection:

1. Yield `reset`, then every stored line from seq 1 as `patch`. For an old run
   without lines, yield the on-the-fly fallback lines instead.
2. If the run is finished, yield `done` and stop.
3. Otherwise, on each tick, read the run row first:
   - on a `status`/`stage` change, yield `status`;
   - if the run is still running, yield the lines after the last seq sent;
   - if it has finished, yield `reset`, replay all lines, yield `done` and
     stop. This picks up an atomic fallback swap.

Every connection replays from the start, so reconnects need no
`Last-Event-ID`. An edition is at most about 20 lines.

**`webapp/api.py`.** Every route resolves its resources through
`_agent_or_404` / `_run_or_404`, so there is one place to add ownership
later.

- `GET /api/agents/{id}/paper` returns `{agent: {id, name, query},
  current_run_id, editions: [{run_id, started_at, finished_at, status,
  edition, error}]}`, newest first, with the same cap as `list_runs`.
  `current_run_id` is the running run if there is one, else the latest
  succeeded run, else null.
- `GET /api/runs/{id}/sources` returns `[{n, title, url, source, published,
  summary, seen_before}]`.
- `POST /api/agents/{id}/run` returns `{run_id}`. It reuses
  `runner.start_run`: if a run is already in progress, it returns that run's
  id. It is covered by the existing cross-site POST guard.
- `GET /api/runs/{id}/edition/stream` is an `async def` handler with
  `response_class=EventSourceResponse`. It encodes `edition_events` as SSE:
  - `patch` uses `ServerSentEvent(event="patch", raw_data=line)`, so there is
    no JSON double-encoding;
  - `status`, `reset` and `done` carry JSON data (`done`: `{status, edition,
    error}`);
  - FastAPI sends keepalive pings every 15 s;
  - an unknown run returns 404.

## Frontend

- **Routes.**
  - `/paper/:agentId` shows the running run if there is one (streaming),
    otherwise the latest succeeded edition. If the latest run failed, a
    banner says it didn't go to press and shows its error.
  - `/paper/:agentId/:runId` shows a specific edition.
  - `/paper/styleguide` is the component library.
- **`src/api.ts`.** It owns every `fetch` and the `EventSource` constructor,
  using relative `/api` URLs only, so auth and 401 handling land in one file
  later.
- **Rendering.** `<JSONUIProvider registry>` wraps `<Renderer spec>`.
- **`useEditionStream(runId)`.**
  - It opens the `EventSource` and passes each `patch` line into
    `createSpecStreamCompiler`.
  - `reset` calls the compiler's `reset()`.
  - `done` closes the source and exposes the final status.
  - On `error` with `readyState === CLOSED` (for example a 404), it re-fetches
    `/api/agents/{id}/paper` to tell "not found" from other failures. On
    `error` while `CONNECTING`, the browser retries on its own, and the
    server's replay-from-start keeps that correct.
  - It exposes `{spec, status, stage, edition, error}`.
- **Page anatomy.** It follows the direction contract:
  - the header strip: paper name, edition, live state, and "Go to press",
    which POSTs and then follows the new run;
  - the start triangle with the `bottomLine`;
  - the rendered edition as a course of numbered controls;
  - the control-description table;
  - the numbered sources;
  - the back-issues rail (failed runs listed as "Didn't go to press").
- **Citations.** A `SourcesProvider` fetches the run's sources. Components
  render `cites` as links to the sources list and the source URL. The
  outlets count, the contour rings and the "Update" tag come from the same
  data.
- **Styleguide.** It renders every component from fixture specs, including
  these edge cases:
  - no lead
  - a single source
  - a demoted lead
  - long headlines
  - 12 elements
  - an empty edition (with answer)
  - a fallback edition
  - a bottom line with no lead

  It also plays a recorded stream on a loop. The fixtures double as test
  inputs.

## Design system (Impeccable)

Done:

- `PRODUCT.md` (init);
- the visual direction, chosen on the decision page: **Orienteering Course**.
  The contract (thesis, own world, story, first viewport, signature
  interaction, form, finish) lives in
  `.impeccable/surfaces/frontend-src-paper-paperpage-tsx.md`, with the
  craft-bar references in `.impeccable/reference/`.

The build is code-led, since there is no image generation: the ambition lives
in the contract's first-viewport and signature-interaction blocks.

Remaining, inside the implementation plan:

1. Tokens (`frontend/src/styles/tokens.css`), obtainable typefaces, and the
   night-map (dark) translation.
2. The catalog components, masthead, rails and styleguide in the chosen
   world.
3. One batched inspection round (desktop and mobile), then the detector,
   then the `impeccable-finish-reviewer`, then fixes.
4. The `impeccable-documenter` writes `DESIGN.md` and `.impeccable/design.json`
   from the built world.
5. Sub-project 2 applies the same DESIGN.md to the ported pages.

## Error handling

| Case | Behaviour |
|---|---|
| Plan/search/write fails | Run `failed` (unchanged); stream sends `done` with the sanitised error; the paper shows the latest good edition plus a banner. |
| Compose fails, truncates, passes its deadline, or yields an invalid spec | Fallback edition swapped in atomically by `finish_run`; run `succeeded`; reason and dropped-line count logged. |
| Invalid streamed line | Dropped, counted, logged; the stream continues. |
| Connection drops | `EventSource` reconnects; the server replays from the start after a `reset`. |
| Agent deleted mid-run | Lines cascade away; stream 404; the hook re-fetches the paper and shows "not found". |
| Server restart mid-run | The startup sweep marks the run failed and clears `stage`; the stream sends `done`. |
| Zero items | `edition = "empty"`; the paper shows the stored answer in an empty-edition state. |
| Frontend not built | `/paper/*` returns 503 "Frontend not built: run npm run build". |

## Testing

TDD, backend first.

- **pytest**
  - `edition_spec`:
    - allowed and rejected ops and paths;
    - element wrapper keys (`on`/`repeat`/`slots`/`visible`/`watch`
      rejected), non-empty `children` only on `Page`, and `$state` values
      rejected;
    - unknown types, schema violations and the cite range;
    - revert on an invalid line;
    - the finalize rules;
    - the main story check: a single outlet; a tie; a winner; a
      Timeline/Split citing the lead's sources not demoting it; a subset
      Story not competing; `www.` normalisation; the demotion patch.
  - `fallback_edition`:
    - lead selection (a clear winner, a tie, a single outlet);
    - the bottom line;
    - title cleanup;
    - truncation of every string and the caps (cites 10, briefs 8);
    - bullets without cites dropped;
    - `[1, 2]` cites;
    - the no-bullets path (with and without `[n]`) and the no-answer path;
    - output always validates and finalizes.
  - `compose` with a fake streaming client:
    - chunks splitting a line mid-JSON;
    - invalid lines dropped;
    - the deadline with a stream that never stops;
    - truncation, API error, refusal and context-window stops falling back;
    - token accounting.
  - Runner:
    - stage updates in order;
    - results saved before compose;
    - a compose failure still `succeeded` with `fallback`, with the lines
      swapped in the same transaction;
    - zero items giving `empty`, with the answer stored.
  - DB:
    - the migration on an old DB;
    - `save_results` + `finish_run` don't double-insert items;
    - the startup sweep clears `stage`;
    - lines only append while running.
  - `edition_events` and API:
    - replay starting with `reset`;
    - following a live run;
    - a fallback swap during a live connection (reset + full replay);
    - `done` for succeeded, failed and empty runs;
    - on-the-fly fallback for old runs;
    - `raw_data` patch encoding;
    - 404 for unknown runs;
    - the paper and sources JSON, including `current_run_id` cases;
    - "Go to press", including the cross-site guard and the already-running
      case;
    - the SPA catch-all, `/paper/assets`, and the 503 when unbuilt.
- **Vitest + Testing Library**
  - Each component renders from the styleguide fixtures inside
    `JSONUIProvider`, including specs with missing children.
  - Cites resolve to the right sources; "Main story", "Reported by N
    outlets" and "Update" appear when they should.
  - `useEditionStream` against a mock `EventSource`: patch, reset, done,
    error+CLOSED → re-fetch, and a reconnect replay.
  - The catalog drift check: the hand-written prompt plus the
    `z.toJSONSchema` output.
- **Manual.** The styleguide page and a real run of the oil agent watched
  live in the browser, then the Impeccable finish review.

## Keeping the public app open (sub-project 3)

This slice makes four cheap choices so going public doesn't mean rewrites:

- an `async` SSE handler (no threadpool cap on viewers);
- `edition_events` separate from the SSE encoding (pub/sub later replaces
  one function);
- all `/api` resource lookups through `_agent_or_404` / `_run_or_404`
  (ownership plus a 404 later is a two-line change);
- one `src/api.ts` (cookie auth and 401 handling in one file).

Deferred on purpose:

- SQLite, the daemon threads and the in-process scheduler (`execute_run` is
  already queue-worker shaped; no SQL outside `db.py`);
- polling per viewer;
- same-origin serving and the Host/Origin guards (the allowlist becomes
  config);
- the unauthenticated API with integer ids;
- quotas on "Go to press" (`start_run` is the single entry, and tokens are
  recorded per run and per stage).

## Out of scope

- Porting the agent list, forms and run pages to React; removing Jinja/HTMX
  (sub-project 2).
- Accounts, per-user data, quotas, hosting and notifications (sub-project 3).
- Token-level streaming inside a block (blocks appear when complete).
- Images, quotes, a cross-agent front page, email/PDF editions.
- A browser end-to-end test framework.
