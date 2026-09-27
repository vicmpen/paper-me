"""Third-party web search behind one small interface.

Each provider is a module in this package exposing:

    ENV_KEY: str                                  # env var holding its API key
    def search(req: SearchRequest) -> list[SearchHit]

config.WEBAPP_SEARCH_PROVIDER names the active one. Adding a provider means
one new module, one _PROVIDERS entry, and the config value; nothing outside
this package changes. The helpers below keep adapters small and make them
fail the same way: every problem is a ProviderError whose message never
contains the API key.
"""

from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass
from datetime import date
from types import ModuleType
from urllib.parse import urlparse

import requests

import config

log = logging.getLogger(__name__)

TEXT_CAP = 1500   # max chars of SearchHit.text
HTTP_TIMEOUT = 20  # seconds per provider request; no retries

_PROVIDERS = {
    "exa": "webapp.search_providers.exa",
    "blopus": "webapp.search_providers.blopus",
}


@dataclass
class SearchRequest:
    query: str
    max_results: int              # per query
    since: date                   # start of the lookback window
    include_domains: list[str]    # [] = no include filter
    exclude_domains: list[str]    # [] = no exclude filter


@dataclass
class SearchHit:
    title: str                    # never empty: falls back to the URL
    url: str                      # never empty
    published: str                # "YYYY-MM-DD" or ""
    source: str                   # site name if the provider gives one, else URL hostname
    text: str                     # excerpt, <= TEXT_CAP chars, may be ""


class ProviderError(Exception):
    pass


def _provider_module() -> ModuleType:
    name = config.WEBAPP_SEARCH_PROVIDER
    path = _PROVIDERS.get(name)
    if path is None:
        raise ProviderError(f"unknown search provider: {name!r}")
    return importlib.import_module(path)


def preflight() -> None:
    """Fail fast on a bad provider name or a missing API key."""
    require_key(_provider_module().ENV_KEY)


def search(req: SearchRequest) -> list[SearchHit]:
    return _provider_module().search(req)


def require_key(env: str) -> str:
    key = os.environ.get(env)
    if not key:
        raise ProviderError(f"{env} is not set")
    return key


def post_json(provider: str, url: str, *, headers: dict, body: dict) -> dict:
    """POST JSON, return the decoded object; any failure is a ProviderError.

    Headers carry the API key, so neither they nor the exception text (which
    can echo request details) go into messages or logs.
    """
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=HTTP_TIMEOUT)
    except requests.RequestException as e:
        raise ProviderError(f"{provider}: request failed ({type(e).__name__})") from None
    if not resp.ok:
        log.warning("%s: HTTP %d, body: %s", provider, resp.status_code, resp.text[:2000])
        raise ProviderError(f"{provider}: HTTP {resp.status_code} {_error_detail(resp)}")
    try:
        data = resp.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise ProviderError(f"{provider}: response was not JSON")
    return data


def _error_detail(resp) -> str:
    try:
        data = resp.json()
    except ValueError:
        data = None
    if isinstance(data, dict):
        for key in ("tag", "error", "message", "detail"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value[:200]
    return resp.text[:200].strip()


def hostname(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def clip(text: str) -> str:
    return text[:TEXT_CAP]
