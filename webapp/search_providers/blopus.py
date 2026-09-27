"""Blopus search adapter: POST https://api.blopus.ai/v1/search.

Blopus limits: query 1-500 chars, count <= 50 (billed per 10), at most 50
domains per include/exclude list. Dates come back as epoch seconds.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from webapp.search_providers import (
    ProviderError, SearchHit, SearchRequest, clip, hostname, post_json, require_key,
)

log = logging.getLogger(__name__)

ENV_KEY = "BLOPUS_API_KEY"
URL = "https://api.blopus.ai/v1/search"
MAX_DOMAINS = 50
MAX_COUNT = 50
MAX_QUERY_CHARS = 500


def _published(value) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return ""
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return ""


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def search(req: SearchRequest) -> list[SearchHit]:
    key = require_key(ENV_KEY)
    if len(req.include_domains) > MAX_DOMAINS or len(req.exclude_domains) > MAX_DOMAINS:
        raise ProviderError(f"blopus: at most {MAX_DOMAINS} domains per list")
    body = {
        "query": req.query[:MAX_QUERY_CHARS],
        "count": min(req.max_results, MAX_COUNT),
        "start_date": req.since.isoformat(),
        "include_excerpt": True,
        "excerpt_chars": 1200,
    }
    if req.include_domains:
        body["include_domains"] = req.include_domains
    if req.exclude_domains:
        body["exclude_domains"] = req.exclude_domains

    started = time.monotonic()
    data = post_json("blopus", URL, headers={"Authorization": f"Bearer {key}"}, body=body)
    results = data.get("results")
    hits: list[SearchHit] = []
    for r in results if isinstance(results, list) else []:
        if not isinstance(r, dict):
            continue
        url = r.get("url")
        if not isinstance(url, str) or not url:
            continue
        hits.append(SearchHit(
            title=_text(r.get("title")) or url,
            url=url,
            published=_published(r.get("published_at")),
            source=_text(r.get("site_name")) or _text(r.get("domain")) or hostname(url),
            text=clip(_text(r.get("snippet"))),
        ))

    log.info("blopus: %r -> %d hits in %.1fs (remaining_quota=%s)", req.query, len(hits),
             time.monotonic() - started, data.get("remaining_quota", "?"))
    if data.get("degraded") or data.get("note"):
        log.warning("blopus: degraded=%s note=%r", data.get("degraded"), data.get("note"))
    return hits
