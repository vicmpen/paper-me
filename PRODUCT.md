# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: domain trackers, meaning analysts, traders, researchers and
journalists who follow a specific beat and care most about precision,
sourcing and what changed. Secondary: everyday news readers who want a
personal paper on the topics they care about (their team, their city's
weather, an election) instead of scrolling feeds. Design for the trackers
first. Everyday readers should find it just as easy to read.

People read on phones and desktops equally. Both are first-class.

## Product Purpose

The user's own reports from the real world. A user creates research agents
for any topic, from politics and the economy to sports and weather events.
Each agent produces the user's own paper. The latest run is today's edition
and earlier runs are back issues.

After one edition, the reader should have:

- **Fast orientation:** in about two minutes, what happened and which story
  matters most.
- **What changed:** what is new since the last edition versus continuing
  stories.
- **Trust and drill-down:** confidence that every claim is sourced, and one
  click to the original article.

## Positioning

"Your own specific research agent." The user defines the beat (a free-text
topic, domains to include or exclude, how far back to look, how many
searches, when to run, and how the response should read). The product then
searches, writes a cited answer and lays the edition out itself. Links come
only from real search results, so the model cannot invent them. The main
story is the event covered by the most independent outlets, and when no
story clearly leads, the edition says so instead of inventing a lead.

## Operating Context

- An agent runs on demand ("Go to press") or on a daily schedule. A run is
  Claude planning search queries, a search provider (Exa or Blopus) running
  them, then Claude writing a cited answer and composing the edition.
- A run takes tens of seconds to minutes. While Claude composes the edition,
  it streams onto the page block by block.
- Each run costs money: Claude calls plus a per-query search charge.
- People read at any time of day, often arriving from a notification that a
  scheduled edition has landed. Notifications are planned but not built.
- Today the app is local and single-user (localhost, no accounts). A public
  multi-user version with sign-up, per-user papers, cost limits and hosting
  is planned as a later sub-project.

## Capabilities and Constraints

- Sources are text only: title, outlet (hostname), published date, summary
  and URL. There are no images and no quotes.
- An edition is composed from a fixed catalog of newspaper components: lead
  story, story, briefs, two-sided split, key figures, timeline and analysis.
  See `docs/superpowers/specs/2026-09-27-live-paper-design.md`.
- Stack: Python (FastAPI, SQLite) backend. The React and json-render
  frontend is being introduced with the paper, and the existing Jinja and
  HTMX pages (agent list, agent form, run pages) will be ported to it later.
- Terminology: agent, run, paper, edition, back issue, source, main story,
  "Go to press".
- Undecided: product name, the details of the public app (accounts, quotas,
  hosting), and an accessibility target.

## Brand Commitments

None binding yet. The product has no name. The current app header says
"News agents" as a placeholder. Each paper's masthead is its agent's name.

## Evidence on Hand

- Real run data in the local `data/webapp.db` (gitignored). The "oil" agent
  (run 10) has 7 cited sources and a bulleted answer on what pushed oil
  prices up versus down. Two other agents have smaller runs.
- `assets/example_digest_screenshot.png` shows the separate daily email
  digest, not the web app.
- Absent, and must not be fabricated: users, testimonials, usage numbers,
  logos, source imagery, and quotes from articles.

## Product Principles

1. **Every claim is traceable.** Citations and real links come before
   flourish. If something cannot be sourced, it does not appear.
2. **Orientation first.** An edition answers "what happened and what matters
   most" at a glance. The main story is earned by independent coverage, and
   when there is none, the edition says so.
3. **Change is the news.** What is new since the last edition stands out
   from continuing stories.
4. **The reader owns the beat.** Any topic, any domain. The edition's form
   adapts to the story (up versus down, a timeline, key numbers) rather than
   forcing one template.
5. **Precise enough for trackers, easy enough for everyone.**

## Accessibility & Inclusion

No formal target yet (user decision, 2026-09-27). Good practice still
applies.
