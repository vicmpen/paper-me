import json
from types import SimpleNamespace as NS

import pytest

from webapp.search_agent import SearchError, run_search


def agent(**over):
    base = dict(query="open-weight LLMs", domain_mode="none", domains=[],
                lookback_days=7, max_searches=5)
    base.update(over)
    return NS(**base)


def text(s):
    return NS(type="text", text=s)


def search_ok():
    return NS(type="web_search_tool_result", content=[NS(type="web_search_result", url="https://x.com")])


def search_err(code="unavailable"):
    return NS(type="web_search_tool_result", content=NS(type="web_search_tool_result_error", error_code=code))


def resp(content, stop="end_turn", searches=1, inp=100, out=10, stop_details=None):
    return NS(content=content, stop_reason=stop, stop_details=stop_details,
              usage=NS(input_tokens=inp, output_tokens=out,
                       server_tool_use=NS(web_search_requests=searches)))


def items_json(*items):
    return json.dumps({"items": [dict(title="T", url=u, source="S", published=p, summary="sum")
                                 for u, p in items]})


class FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = self

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeStream(self._responses.pop(0))


class _FakeStream:
    def __init__(self, response):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._response


TODAY = "2026-09-26"


def test_success_basic_and_request_shape():
    c = FakeClient([resp([NS(type="server_tool_use", name="web_search"), search_ok(),
                          text(items_json(("https://a.com/1", "2026-09-25")))])])
    r = run_search(agent(), client=c, today=TODAY)
    assert [i.url for i in r.items] == ["https://a.com/1"]
    assert (r.input_tokens, r.output_tokens, r.searches) == (100, 10, 1)
    call = c.calls[0]
    assert call["model"] == "claude-sonnet-4-6"
    assert call["output_config"]["format"]["type"] == "json_schema"
    tool = call["tools"][0]
    assert tool["type"] == "web_search_20260209" and tool["max_uses"] == 5
    assert "allowed_domains" not in tool and "blocked_domains" not in tool
    user = call["messages"][0]["content"]
    assert TODAY in user and "open-weight LLMs" in user and "2026-09-19" in user


@pytest.mark.parametrize("mode,key", [("include", "allowed_domains"), ("exclude", "blocked_domains")])
def test_domain_modes(mode, key):
    c = FakeClient([resp([search_ok(), text(items_json())])])
    run_search(agent(domain_mode=mode, domains=["a.com"]), client=c, today=TODAY)
    tool = c.calls[0]["tools"][0]
    assert tool[key] == ["a.com"]
    other = {"allowed_domains", "blocked_domains"} - {key}
    assert not (other & tool.keys())


def test_pause_turn_continues_and_accumulates():
    first = resp([NS(type="server_tool_use", name="web_search"), search_ok()], stop="pause_turn")
    second = resp([search_ok(), text(items_json(("https://a.com/1", "")))], searches=2)
    c = FakeClient([first, second])
    r = run_search(agent(), client=c, today=TODAY)
    assert len(c.calls) == 2
    msgs = c.calls[1]["messages"]
    assert msgs[-1] == {"role": "assistant", "content": first.content}
    assert len(msgs) == 2  # no extra user "continue" message
    assert (r.input_tokens, r.searches) == (200, 3)


def test_pause_turn_cap():
    c = FakeClient([resp([search_ok()], stop="pause_turn") for _ in range(6)])
    with pytest.raises(SearchError, match="continuations"):
        run_search(agent(), client=c, today=TODAY)
    assert len(c.calls) == 6


def test_refusal_with_and_without_category():
    c = FakeClient([resp([], stop="refusal", stop_details=NS(category="cyber"))])
    with pytest.raises(SearchError, match="model refused: cyber"):
        run_search(agent(), client=c, today=TODAY)
    c = FakeClient([resp([], stop="refusal")])
    with pytest.raises(SearchError, match="model refused"):
        run_search(agent(), client=c, today=TODAY)


def test_max_tokens():
    c = FakeClient([resp([search_ok(), text('{"items": [')], stop="max_tokens")])
    with pytest.raises(SearchError, match="truncated"):
        run_search(agent(), client=c, today=TODAY)


def test_all_searches_errored():
    c = FakeClient([resp([search_err("too_many_requests"), text(items_json())])])
    with pytest.raises(SearchError, match="web search failed: too_many_requests"):
        run_search(agent(), client=c, today=TODAY)


def test_partial_search_errors_ok():
    c = FakeClient([resp([search_err(), search_ok(), text(items_json())], searches=2)])
    assert run_search(agent(), client=c, today=TODAY).items == []


def test_zero_searches():
    c = FakeClient([resp([text(items_json(("https://a.com", "")))], searches=0)])
    with pytest.raises(SearchError, match="did not search"):
        run_search(agent(), client=c, today=TODAY)


def test_searches_fallback_counts_blocks_when_usage_missing():
    r0 = resp([NS(type="server_tool_use", name="web_search"),
               NS(type="server_tool_use", name="code_execution"),
               search_ok(), text(items_json())])
    r0.usage = NS(input_tokens=1, output_tokens=1)
    assert run_search(agent(), client=FakeClient([r0]), today=TODAY).searches == 1


def test_parse_failure():
    c = FakeClient([resp([search_ok(), text("not json")])])
    with pytest.raises(SearchError, match="parse"):
        run_search(agent(), client=c, today=TODAY)


def test_only_trailing_text_blocks_parsed():
    c = FakeClient([resp([text("Let me search."), search_ok(),
                          text(items_json(("https://a.com/1", "")))])])
    assert len(run_search(agent(), client=c, today=TODAY).items) == 1


def test_post_filtering():
    body = items_json(
        ("https://a.com/1", "2026-09-25"),
        ("https://a.com/1", "2026-09-25"),    # duplicate
        ("javascript:alert(1)", ""),          # bad scheme
        ("https:///nohost", ""),              # no host
        ("https://b.com/old", "2026-09-01"),  # outside window
        ("https://b.com/edge", "2026-09-18"), # within 1-day slack
        ("https://c.com/nodate", ""),         # kept
        ("https://c.com/weird", "last week"), # unparseable, kept
    )
    r = run_search(agent(), client=FakeClient([resp([search_ok(), text(body)])]), today=TODAY)
    assert [i.url for i in r.items] == [
        "https://a.com/1", "https://b.com/edge", "https://c.com/nodate", "https://c.com/weird"]


def test_context_window_exceeded():
    c = FakeClient([resp([search_ok(), text('{"items": [')], stop="model_context_window_exceeded")])
    with pytest.raises(SearchError, match="context window"):
        run_search(agent(), client=c, today=TODAY)
