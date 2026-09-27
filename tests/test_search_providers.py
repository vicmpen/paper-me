import sys
import types
from datetime import date

import pytest
import requests

import config
from webapp import search_providers
from webapp.search_providers import (
    TEXT_CAP, ProviderError, SearchHit, SearchRequest, clip, hostname, post_json, require_key,
)

KEY = "secret-key-123"


def req(**over):
    base = dict(query="q", max_results=10, since=date(2026, 9, 20),
                include_domains=[], exclude_domains=[])
    base.update(over)
    return SearchRequest(**base)


# --- post_json ---

def test_post_json_ok(fake_post):
    fake_post.respond(200, {"results": [1]})
    data = post_json("exa", "https://api.example/search", headers={"x-api-key": KEY}, body={"a": 1})
    assert data == {"results": [1]}
    call = fake_post.calls[0]
    assert call["url"] == "https://api.example/search"
    assert call["json"] == {"a": 1} and call["timeout"] == 20
    assert call["headers"] == {"x-api-key": KEY}


def test_post_json_http_error_uses_tag(fake_post, caplog):
    fake_post.respond(401, {"error": "Invalid API key", "tag": "INVALID_API_KEY"})
    with pytest.raises(ProviderError) as e:
        post_json("exa", "https://x", headers={"x-api-key": KEY}, body={})
    assert str(e.value) == "exa: HTTP 401 INVALID_API_KEY"
    assert KEY not in str(e.value) and KEY not in caplog.text


def test_post_json_http_error_nested_blopus_message(fake_post):
    fake_post.respond(401, {"error": {"code": "unauthorized",
                                      "message": "Invalid or missing API key."}})
    with pytest.raises(ProviderError) as e:
        post_json("blopus", "https://x", headers={}, body={})
    assert str(e.value) == "blopus: HTTP 401 Invalid or missing API key."


def test_post_json_http_error_plain_text(fake_post):
    fake_post.respond(502, text="Bad gateway")
    with pytest.raises(ProviderError, match=r"^blopus: HTTP 502 Bad gateway$"):
        post_json("blopus", "https://x", headers={}, body={})


def test_post_json_request_exception(fake_post):
    fake_post.exc = requests.Timeout(f"timed out talking to host with {KEY}")
    with pytest.raises(ProviderError) as e:
        post_json("exa", "https://x", headers={"x-api-key": KEY}, body={})
    assert str(e.value) == "exa: request failed (Timeout)"


@pytest.mark.parametrize("resp", [dict(status=200, text="<html>"), dict(status=200, payload=[1, 2])])
def test_post_json_not_json_object(fake_post, resp):
    fake_post.respond(**resp)
    with pytest.raises(ProviderError, match="response was not JSON"):
        post_json("exa", "https://x", headers={}, body={})


# --- small helpers ---

def test_require_key(monkeypatch):
    monkeypatch.delenv("SOME_TEST_KEY", raising=False)
    with pytest.raises(ProviderError, match="^SOME_TEST_KEY is not set$"):
        require_key("SOME_TEST_KEY")
    monkeypatch.setenv("SOME_TEST_KEY", "v")
    assert require_key("SOME_TEST_KEY") == "v"


def test_hostname_and_clip():
    assert hostname("https://www.a.com/x?y=1") == "www.a.com"
    assert hostname("not a url") == ""
    assert len(clip("x" * (TEXT_CAP + 50))) == TEXT_CAP


# --- dispatcher ---

@pytest.fixture
def fake_provider(monkeypatch):
    mod = types.ModuleType("fake_search_provider")
    mod.ENV_KEY = "FAKE_PROVIDER_KEY"
    mod.seen = []
    def search(r):
        mod.seen.append(r)
        return [SearchHit(title="t", url="https://a.com", published="", source="a.com", text="")]
    mod.search = search
    monkeypatch.setitem(sys.modules, "fake_search_provider", mod)
    monkeypatch.setitem(search_providers._PROVIDERS, "fake", "fake_search_provider")
    monkeypatch.setattr(config, "WEBAPP_SEARCH_PROVIDER", "fake")
    return mod


def test_search_dispatches_to_configured_module(fake_provider):
    r = req()
    hits = search_providers.search(r)
    assert fake_provider.seen == [r] and hits[0].url == "https://a.com"


def test_unknown_provider(monkeypatch):
    monkeypatch.setattr(config, "WEBAPP_SEARCH_PROVIDER", "nope")
    with pytest.raises(ProviderError, match="unknown search provider: 'nope'"):
        search_providers.search(req())
    with pytest.raises(ProviderError, match="unknown search provider"):
        search_providers.preflight()


def test_preflight_missing_key(fake_provider, monkeypatch):
    monkeypatch.delenv("FAKE_PROVIDER_KEY", raising=False)
    with pytest.raises(ProviderError, match="^FAKE_PROVIDER_KEY is not set$"):
        search_providers.preflight()
    monkeypatch.setenv("FAKE_PROVIDER_KEY", "k")
    search_providers.preflight()  # no error


def test_config_defaults():
    assert config.WEBAPP_SEARCH_PROVIDER in search_providers._PROVIDERS
    assert config.WEBAPP_RESULTS_PER_QUERY == 10
    assert config.WEBAPP_EFFORT == "low"
