import json

import pytest

from webapp.edition_spec import (EditionSpec, InvalidEdition, InvalidLine, dump_line,
                                 element, outlet)

# Outlets: 1 and 2 are both reuters.com; 3 apnews.com; 4 bbc.co.uk; 5 ft.com.
URLS = ["https://www.reuters.com/a", "https://reuters.com/b", "https://apnews.com/c",
        "https://www.bbc.co.uk/d", "https://ft.com/e"]
ROOT = dump_line("add", "/root", "page")


def add(eid, type_, props, children=()):
    return dump_line("add", f"/elements/{eid}", element(type_, props, list(children)))


def page(*children, **props):
    return add("page", "Page", props, children)


def lead(cites, eid="lead"):
    return add(eid, "LeadStory", {"kicker": "Oil", "headline": "Brent jumps", "dek": "Why.",
                                  "body": ["Para."], "cites": list(cites)})


def story(eid, cites, weight="minor"):
    return add(eid, "Story", {"headline": f"H {eid}", "dek": "D", "cites": list(cites),
                              "weight": weight})


def build(*lines, urls=URLS):
    spec = EditionSpec(urls)
    for line in lines:
        spec.apply_line(line)
    return spec


def test_outlet_normalises_hosts():
    assert outlet("https://WWW.Reuters.com/x") == "reuters.com"
    assert outlet("https://reuters.com:443/y") == "reuters.com"
    assert outlet("not a url") == ""


def test_valid_edition_without_lead_finalizes():
    spec = build(ROOT, page("s1", "s2"), story("s1", [1]), story("s2", [3]))
    assert spec.finalize() == []
    assert spec.root == "page" and set(spec.elements) == {"page", "s1", "s2"}


@pytest.mark.parametrize("line", [
    "not json",
    "```jsonl",
    json.dumps({"op": "move", "from": "/elements/a", "path": "/elements/b"}),
    json.dumps({"op": "copy", "from": "/root", "path": "/elements/x"}),
    json.dumps({"op": "test", "path": "/root", "value": "page"}),
    dump_line("add", "/state/x", 1),
    dump_line("add", "/elements/Bad Id", element("Story", {})),
    dump_line("add", "/somewhere", 1),
    dump_line("remove", "/root"),
    dump_line("add", "/root", "Not An Id"),
])
def test_rejects_disallowed_ops_and_paths(line):
    with pytest.raises(InvalidLine):
        build(ROOT).apply_line(line)


@pytest.mark.parametrize("extra", ["visible", "on", "repeat", "slots", "watch"])
def test_rejects_extra_element_keys(extra):
    el = element("Story", {"headline": "H", "dek": "D", "cites": [1], "weight": "minor"})
    el[extra] = {}
    with pytest.raises(InvalidLine):
        build().apply_line(dump_line("add", "/elements/s1", el))


def test_rejects_children_on_a_leaf():
    with pytest.raises(InvalidLine):
        build().apply_line(add("s1", "Story", {"headline": "H", "dek": "D", "cites": [1],
                                               "weight": "minor"}, ["x"]))


@pytest.mark.parametrize("props", [
    {"headline": "H" * 161, "dek": "D", "cites": [1], "weight": "minor"},
    {"headline": "H", "dek": "D", "weight": "minor"},
    {"headline": "H", "dek": "D", "cites": [], "weight": "minor"},
    {"headline": "H", "dek": "D", "cites": [1], "weight": "huge"},
    {"headline": "H", "dek": "D", "cites": [1], "weight": "minor", "url": "https://x"},
    {"headline": {"$state": "/x"}, "dek": "D", "cites": [1], "weight": "minor"},
])
def test_rejects_invalid_props(props):
    with pytest.raises(InvalidLine):
        build().apply_line(add("s1", "Story", props))


def test_rejects_unknown_component():
    with pytest.raises(InvalidLine):
        build().apply_line(add("q", "Quote", {"text": "x"}))


@pytest.mark.parametrize("cites", [[0], [6], [True], [1.0]])
def test_rejects_cites_outside_the_run(cites):
    with pytest.raises(InvalidLine):
        build().apply_line(story("s1", cites))


def test_invalid_nested_patch_leaves_the_element_unchanged():
    spec = build(ROOT, page("s1"), story("s1", [1]))
    before = json.dumps(spec.elements, sort_keys=True)
    with pytest.raises(InvalidLine):
        spec.apply_line(dump_line("replace", "/elements/s1/props/headline", "H" * 200))
    assert json.dumps(spec.elements, sort_keys=True) == before


def test_nested_patches_apply():
    spec = build(ROOT, page("s1"), story("s1", [1]))
    spec.apply_line(dump_line("replace", "/elements/s1/props/headline", "New"))
    spec.apply_line(dump_line("add", "/elements/page/children/-", "s2"))
    spec.apply_line(story("s2", [3]))
    spec.apply_line(dump_line("remove", "/elements/s2"))
    assert spec.elements["s1"]["props"]["headline"] == "New"
    assert spec.elements["page"]["children"] == ["s1", "s2"]
    assert "s2" not in spec.elements


@pytest.mark.parametrize("lines, message", [
    ((story("s1", [1]),), "root"),
    ((ROOT, story("page", [1])), "root"),
    ((ROOT, page("s1")), "missing"),
    ((ROOT, page("lead", "l2"), lead([1, 3]), lead([4, 5], eid="l2")), "more than one LeadStory"),
    ((ROOT, page("s1", "lead"), story("s1", [1]), lead([1, 3])), "first child"),
])
def test_finalize_rejects_broken_pages(lines, message):
    with pytest.raises(InvalidEdition, match=message):
        build(*lines).finalize()


def test_finalize_rejects_more_than_12_elements():
    ids = [f"s{i}" for i in range(12)]
    spec = build(ROOT, page(*ids), *(story(i, [1]) for i in ids))
    with pytest.raises(InvalidEdition, match="max 12"):
        spec.finalize()


# --- main story rule ---

def test_lead_reported_by_most_outlets_stands():
    spec = build(ROOT, page("lead", "s1"), lead([1, 3, 4]), story("s1", [5]))
    assert spec.finalize() == []
    assert spec.elements["lead"]["type"] == "LeadStory"


def test_lead_from_one_outlet_is_demoted():
    # www.reuters.com and reuters.com are one outlet.
    spec = build(ROOT, page("lead", "s1"), lead([1, 2]), story("s1", [5]))
    extra = spec.finalize()
    assert len(extra) == 1 and json.loads(extra[0])["op"] == "replace"
    demoted = spec.elements["lead"]
    assert demoted["type"] == "Story" and demoted["props"]["weight"] == "major"
    assert "body" not in demoted["props"]
    assert demoted["props"]["headline"] == "Brent jumps" and demoted["props"]["kicker"] == "Oil"


def test_tied_coverage_demotes_the_lead():
    spec = build(ROOT, page("lead", "s1"), lead([1, 3]), story("s1", [4, 5]))
    assert len(spec.finalize()) == 1


def test_timeline_split_analysis_on_lead_sources_do_not_compete():
    spec = build(
        ROOT, page("lead", "t", "sp", "an"), lead([1, 3]),
        add("t", "Timeline", {"title": "How it unfolded", "events": [
            {"date": "Sep 24", "text": "a", "cites": [1, 3, 4]},
            {"date": "Sep 25", "text": "b", "cites": [5]}]}),
        add("sp", "Split", {"title": "Forces", "sides": [
            {"label": "Up", "direction": "up", "points": [{"text": "x", "cites": [1, 3, 4, 5]}]},
            {"label": "Down", "direction": "down", "points": [{"text": "y", "cites": [4]}]}]}),
        add("an", "Analysis", {"heading": "What it means", "paragraphs": ["p"],
                               "cites": [1, 3, 4, 5]}),
    )
    assert spec.finalize() == []


def test_story_on_a_subset_of_the_lead_outlets_does_not_compete():
    spec = build(ROOT, page("lead", "s1"), lead([1, 3]), story("s1", [2, 3]))
    assert spec.finalize() == []


def test_briefs_item_with_equal_coverage_demotes_the_lead():
    spec = build(ROOT, page("lead", "b"), lead([1, 3]),
                 add("b", "Briefs", {"title": "In brief", "items": [{"text": "x", "cites": [4, 5]}]}))
    assert len(spec.finalize()) == 1
