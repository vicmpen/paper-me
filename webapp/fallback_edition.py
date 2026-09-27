"""Rules-based edition built from a run's answer and sources.

Used when compose fails or produces an invalid page, and on the fly for runs
that predate the paper. It produces the same JSONL patch lines as compose
and always passes edition_spec validation (the tests check).

Main story: the answer bullet that cites the most distinct outlets leads,
but only with at least two outlets and strictly more than every other
bullet. Otherwise the edition has no main story.
"""

from __future__ import annotations

import re

from webapp.edition_spec import dump_line, element, outlet

MAX_CITES = 10
MAX_STORIES = 3
MAX_BRIEFS = 8
_CITE_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_BULLET_RE = re.compile(r"^\s*[-*]\s+")
_SITE_SUFFIX_RE = re.compile(r"\s+\|\s+[^|]+$")


def truncate(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def parse_cites(text: str, k: int) -> list[int]:
    cites: list[int] = []
    for match in _CITE_RE.finditer(text):
        for part in match.group(1).split(","):
            n = int(part)
            if 1 <= n <= k and n not in cites:
                cites.append(n)
    return cites[:MAX_CITES]


def strip_cites(text: str) -> str:
    return " ".join(_CITE_RE.sub("", text).split()).replace(" .", ".").replace(" ,", ",")


def clean_title(title: str) -> str:
    return _SITE_SUFFIX_RE.sub("", title).strip() or title.strip()


def _bullets(answer: str) -> list[str]:
    return [_BULLET_RE.sub("", line) for line in answer.splitlines() if _BULLET_RE.match(line)]


def build(answer: str | None, items: list) -> list[str]:
    """Patch lines for a rules-based edition; [] when there are no sources."""
    k = len(items)
    if k == 0:
        return []
    answer = answer or ""
    urls = [it.url for it in items]

    def n_outlets(cites: list[int]) -> int:
        return len({o for n in cites if (o := outlet(urls[n - 1]))})

    raw_bullets = _bullets(answer)
    bullets = [(strip_cites(b), parse_cites(b, k)) for b in raw_bullets]
    bullets = [(text, cites) for text, cites in bullets if text]

    blocks: list[tuple[str, dict]] = []
    page_props: dict = {}

    lead_index = None
    scores = [n_outlets(cites) for _, cites in bullets]
    if scores:
        best = max(scores)
        if best >= 2 and scores.count(best) == 1:
            lead_index = scores.index(best)
    lead_cites: list[int] = []
    if lead_index is not None:
        text, lead_cites = bullets[lead_index]
        first = items[lead_cites[0] - 1]
        blocks.append(("lead", element("LeadStory", {
            "headline": truncate(clean_title(first.title), 160),
            "dek": truncate(first.summary, 400),
            "body": [truncate(text, 1200)],
            "cites": lead_cites,
        })))
        page_props["bottomLine"] = {"text": truncate(text, 280), "cites": lead_cites}

    story_sources = [n for n in range(1, k + 1) if n not in lead_cites][:MAX_STORIES]
    for i, n in enumerate(story_sources, 1):
        it = items[n - 1]
        blocks.append((f"s{i}", element("Story", {
            "headline": truncate(clean_title(it.title), 160),
            "dek": truncate(it.summary, 400),
            "cites": [n],
            "weight": "minor",
        })))

    briefs = [{"text": truncate(text, 500), "cites": cites}
              for i, (text, cites) in enumerate(bullets) if i != lead_index and cites]
    if briefs:
        blocks.append(("briefs", element("Briefs", {"title": "In brief",
                                                    "items": briefs[:MAX_BRIEFS]})))
    elif not raw_bullets and answer.strip():
        paragraphs = [truncate(strip_cites(p), 1200)
                      for p in re.split(r"\n\s*\n", answer) if strip_cites(p)][:3]
        if paragraphs:
            cites = parse_cites(answer, k) or list(range(1, min(k, MAX_CITES) + 1))
            blocks.append(("summary", element("Analysis", {
                "heading": "Summary", "paragraphs": paragraphs, "cites": cites})))
    elif not answer.strip():
        rest = [n for n in range(1, k + 1) if n not in story_sources][:MAX_BRIEFS]
        if rest:
            blocks.append(("briefs", element("Briefs", {"title": "In brief", "items": [
                {"text": truncate(clean_title(items[n - 1].title), 500), "cites": [n]}
                for n in rest]})))

    lines = [dump_line("add", "/root", "page"),
             dump_line("add", "/elements/page",
                       element("Page", page_props, [eid for eid, _ in blocks]))]
    lines += [dump_line("add", f"/elements/{eid}", el) for eid, el in blocks]
    return lines
