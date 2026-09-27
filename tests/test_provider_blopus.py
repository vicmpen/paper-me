from datetime import date

import pytest

from webapp.search_providers import TEXT_CAP, ProviderError, SearchRequest, blopus


def req(**over):
    base = dict(query="tsitsipas", max_results=10, since=date(2026, 9, 20),
                include_domains=[], exclude_domains=[])
    base.update(over)
    return SearchRequest(**base)


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("BLOPUS_API_KEY", "blopus-test-key")


RESULTS = {"results": [
    {"title": "Tsitsipas wins", "url": "https://atptour.com/a", "snippet": "s" * 1300,
     "site_name": "ATP Tour", "domain": "atptour.com", "published_at": 1790000000},
    {"title": "", "url": "https://b.com/x", "snippet": None, "site_name": None,
     "domain": "b.com", "published_at": None},
    {"title": "no url"},
    {"title": "T", "url": "https://c.com/z", "published_at": "garbage"},
    {"title": "bool date", "url": "https://d.com/q", "published_at": True},
], "remaining_quota": 990, "degraded": True, "note": "index lag"}


def test_request_shape_without_domains(fake_post):
    blopus.search(req())
    call = fake_post.calls[0]
    assert call["url"] == "https://api.blopus.ai/v1/search"
    assert call["headers"] == {"Authorization": "Bearer blopus-test-key"}
    assert call["timeout"] == 20
    assert call["json"] == {
        "query": "tsitsipas", "count": 10, "start_date": "2026-09-20",
        "include_excerpt": True, "excerpt_chars": 1200,
    }


def test_request_domains_count_cap_and_query_truncation(fake_post):
    blopus.search(req(include_domains=["a.com"], max_results=80, query="w " * 400))
    blopus.search(req(exclude_domains=["b.com"]))
    first, second = fake_post.calls[0]["json"], fake_post.calls[1]["json"]
    assert first["include_domains"] == ["a.com"] and "exclude_domains" not in first
    assert first["count"] == 50
    assert len(first["query"]) == 500
    assert second["exclude_domains"] == ["b.com"] and "include_domains" not in second


def test_result_mapping(fake_post, caplog):
    caplog.set_level("INFO")
    fake_post.respond(200, RESULTS)
    hits = blopus.search(req())
    assert [h.url for h in hits] == ["https://atptour.com/a", "https://b.com/x",
                                     "https://c.com/z", "https://d.com/q"]
    first, second, third, fourth = hits
    assert first.title == "Tsitsipas wins" and first.source == "ATP Tour"
    assert first.published == "2026-09-21" and len(first.text) == 1300 <= TEXT_CAP
    assert second.title == "https://b.com/x" and second.source == "b.com"
    assert second.published == "" and second.text == ""
    assert third.source == "c.com" and third.published == ""
    assert fourth.published == ""
    assert "remaining_quota=990" in caplog.text
    assert "degraded" in caplog.text and "index lag" in caplog.text


def test_blopus_too_many_domains(fake_post):
    many = [f"d{i}.com" for i in range(51)]
    with pytest.raises(ProviderError, match="^blopus: at most 50 domains per list$"):
        blopus.search(req(include_domains=many))
    with pytest.raises(ProviderError, match="at most 50 domains"):
        blopus.search(req(exclude_domains=many))
    assert fake_post.calls == []


def test_missing_key_no_request(fake_post, monkeypatch):
    monkeypatch.delenv("BLOPUS_API_KEY")
    with pytest.raises(ProviderError, match="^BLOPUS_API_KEY is not set$"):
        blopus.search(req())
    assert fake_post.calls == []


def test_http_error(fake_post):
    fake_post.respond(429, {"message": "rate limited"})
    with pytest.raises(ProviderError, match="^blopus: HTTP 429 rate limited$"):
        blopus.search(req())
