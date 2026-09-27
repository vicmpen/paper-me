from datetime import date

import pytest

from webapp.search_providers import TEXT_CAP, ProviderError, SearchRequest, exa


def req(**over):
    base = dict(query="open-weight llm", max_results=8, since=date(2026, 9, 20),
                include_domains=[], exclude_domains=[])
    base.update(over)
    return SearchRequest(**base)


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "exa-test-key")


RESULTS = {"results": [
    {"title": "Llama 5 released", "url": "https://ai.meta.com/blog/llama-5",
     "publishedDate": "2026-09-25T10:00:00.000Z", "text": "x" * 2000},
    {"title": None, "url": "https://hf.co/x", "publishedDate": None},
    {"title": "no url", "publishedDate": "2026-09-24T00:00:00.000Z"},
    {"title": "bad date", "url": "https://t.co/y", "publishedDate": "yesterday", "text": None},
    "not a dict",
], "costDollars": {"total": 0.012}}


def test_request_shape_without_domains(fake_post):
    exa.search(req())
    call = fake_post.calls[0]
    assert call["url"] == "https://api.exa.ai/search"
    assert call["headers"] == {"x-api-key": "exa-test-key"}
    assert call["timeout"] == 20
    assert call["json"] == {
        "query": "open-weight llm", "type": "auto", "numResults": 8,
        "startPublishedDate": "2026-09-20T00:00:00.000Z",
        "contents": {"text": {"maxCharacters": TEXT_CAP}},
    }


def test_request_domains(fake_post):
    exa.search(req(include_domains=["a.com"]))
    exa.search(req(exclude_domains=["b.com", "c.com"]))
    first, second = fake_post.calls[0]["json"], fake_post.calls[1]["json"]
    assert first["includeDomains"] == ["a.com"] and "excludeDomains" not in first
    assert second["excludeDomains"] == ["b.com", "c.com"] and "includeDomains" not in second


def test_result_mapping(fake_post, caplog):
    caplog.set_level("INFO")
    fake_post.respond(200, RESULTS)
    hits = exa.search(req())
    assert [h.url for h in hits] == ["https://ai.meta.com/blog/llama-5", "https://hf.co/x", "https://t.co/y"]
    first, second, third = hits
    assert first.title == "Llama 5 released" and first.published == "2026-09-25"
    assert first.source == "ai.meta.com" and len(first.text) == TEXT_CAP
    assert second.title == "https://hf.co/x" and second.published == "" and second.text == ""
    assert third.published == "" and third.text == ""
    assert "3 hits" in caplog.text and "0.012" in caplog.text


def test_missing_results_key_is_empty(fake_post):
    fake_post.respond(200, {"requestId": "r"})
    assert exa.search(req()) == []


def test_missing_key_no_request(fake_post, monkeypatch):
    monkeypatch.delenv("EXA_API_KEY")
    with pytest.raises(ProviderError, match="^EXA_API_KEY is not set$"):
        exa.search(req())
    assert fake_post.calls == []


def test_http_error(fake_post):
    fake_post.respond(402, {"error": "Out of credits", "tag": "NO_MORE_CREDITS"})
    with pytest.raises(ProviderError, match="^exa: HTTP 402 NO_MORE_CREDITS$"):
        exa.search(req())
