"""Exa search adapter: POST https://api.exa.ai/search.

Exa returns no site name, so `source` is the URL hostname. Page text comes
from `contents.text`, capped server-side at TEXT_CAP characters.
"""

from __future__ import annotations

import logging
import time
from datetime import date

from webapp.search_providers import (
    TEXT_CAP, SearchHit, SearchRequest, clip, hostname, post_json, require_key,
)

log = logging.getLogger(__name__)

ENV_KEY = "EXA_API_KEY"
URL = "https://api.exa.ai/search"


def _published(value) -> str:
    if not isinstance(value, str):
        return ""
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return ""


def search(req: SearchRequest) -> list[SearchHit]:
    key = require_key(ENV_KEY)
    body = {
        "query": req.query,
        "type": "auto",
        "numResults": req.max_results,
        "startPublishedDate": f"{req.since.isoformat()}T00:00:00.000Z",
        "contents": {"text": {"maxCharacters": TEXT_CAP}},
    }
    if req.include_domains:
        body["includeDomains"] = req.include_domains
    if req.exclude_domains:
        body["excludeDomains"] = req.exclude_domains

    started = time.monotonic()
    data = post_json("exa", URL, headers={"x-api-key": key}, body=body)
    results = data.get("results")
    hits: list[SearchHit] = []
    for r in results if isinstance(results, list) else []:
        if not isinstance(r, dict):
            continue
        url = r.get("url")
        if not isinstance(url, str) or not url:
            continue
        title = r.get("title")
        text = r.get("text")
        hits.append(SearchHit(
            title=title.strip() if isinstance(title, str) and title.strip() else url,
            url=url,
            published=_published(r.get("publishedDate")),
            source=hostname(url),
            text=clip(text) if isinstance(text, str) else "",
        ))

    cost = data.get("costDollars")
    total = cost.get("total") if isinstance(cost, dict) else None
    log.info("exa: %r -> %d hits in %.1fs (cost=$%s)", req.query, len(hits),
             time.monotonic() - started, total if total is not None else "?")
    return hits
