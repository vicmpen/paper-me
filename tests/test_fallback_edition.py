import json
from types import SimpleNamespace as NS

import pytest

from webapp.edition_spec import EditionSpec
from webapp.fallback_edition import build, clean_title, parse_cites, strip_cites, truncate


def item(url, title="A title | Site", summary="A summary."):
    return NS(url=url, title=title, summary=summary)


# Outlets: 1 reuters, 2 apnews, 3 bbc, 4 ft, 5 reuters again.
ITEMS = [item("https://www.reuters.com/a", "Brent tops $106 | Reuters"),
         item("https://apnews.com/b"), item("https://bbc.co.uk/c"),
         item("https://ft.com/d"), item("https://reuters.com/e")]


def check(lines, items=ITEMS):
    """Every fallback edition must validate and keep its lead."""
    spec = EditionSpec([it.url for it in items])
    for line in lines:
        spec.apply_line(line)
    assert spec.finalize() == []
    return spec


def children(spec):
    return [spec.elements[c] for c in spec.elements[spec.root]["children"]]


def test_clear_winner_leads_with_a_bottom_line():
    spec = check(build("- Escalation pushed prices up [1][2][3].\n- Pipeline restart eased prices [4].", ITEMS))
    blocks = children(spec)
    lead = blocks[0]
    assert lead["type"] == "LeadStory"
    assert lead["props"]["headline"] == "Brent tops $106"
    assert lead["props"]["body"] == ["Escalation pushed prices up."]
    assert lead["props"]["cites"] == [1, 2, 3]
    assert spec.elements["page"]["props"]["bottomLine"] == {
        "text": "Escalation pushed prices up.", "cites": [1, 2, 3]}
    assert [b["props"]["cites"] for b in blocks if b["type"] == "Story"] == [[4], [5]]
    briefs = [b for b in blocks if b["type"] == "Briefs"][0]["props"]
    assert briefs["title"] == "In brief"
    assert briefs["items"] == [{"text": "Pipeline restart eased prices.", "cites": [4]}]


def test_tied_bullets_have_no_lead():
    spec = check(build("- A [1][2]\n- B [3][4]", ITEMS))
    assert all(b["type"] != "LeadStory" for b in children(spec))
    assert "bottomLine" not in spec.elements["page"]["props"]


def test_same_outlet_twice_counts_once():
    spec = check(build("- A [1][5]\n- B [2]", ITEMS))
    assert all(b["type"] != "LeadStory" for b in children(spec))


def test_briefs_drop_uncited_bullets_and_cap_at_8():
    answer = "\n".join(f"- Point {i} [2]" for i in range(10)) + "\n- No citation here"
    spec = check(build(answer, ITEMS))
    briefs = [b for b in children(spec) if b["type"] == "Briefs"][0]
    assert len(briefs["props"]["items"]) == 8


def test_citation_lists_are_parsed_deduplicated_and_capped():
    assert parse_cites("X [1, 2, 3] [4,5] [2] [99]", 5) == [1, 2, 3, 4, 5]
    assert parse_cites("[" + ", ".join(str(n) for n in range(1, 13)) + "]", 12) == list(range(1, 11))
    assert strip_cites("Brent surged above $106 [1][2].") == "Brent surged above $106."


def test_long_strings_are_truncated():
    items = [item("https://a.com/1", title="T" * 300, summary="S" * 900)]
    spec = check(build(None, items), items)
    story = children(spec)[0]["props"]
    assert len(story["headline"]) == 160 and story["headline"].endswith("…")
    assert len(story["dek"]) == 400
    assert truncate("short", 10) == "short"


def test_clean_title_strips_a_site_suffix_only():
    assert clean_title("Brent slides | GetFinanceBrief") == "Brent slides"
    assert clean_title("A | B | C") == "A | B"
    assert clean_title("| Only") == "| Only"


def test_prose_answer_becomes_analysis():
    spec = check(build("Prices rose [2].\n\nThen they fell [3].", ITEMS))
    analysis = [b for b in children(spec) if b["type"] == "Analysis"][0]["props"]
    assert analysis["heading"] == "Summary"
    assert analysis["paragraphs"] == ["Prices rose.", "Then they fell."]
    assert analysis["cites"] == [2, 3]


def test_prose_answer_without_citations_cites_the_first_sources():
    spec = check(build("Markets were calm this week.", ITEMS))
    analysis = [b for b in children(spec) if b["type"] == "Analysis"][0]["props"]
    assert analysis["cites"] == [1, 2, 3, 4, 5]


def test_no_answer_uses_item_titles():
    items = ITEMS + [item("https://cnbc.com/f", "Sixth story | CNBC")]
    spec = check(build(None, items), items)
    blocks = children(spec)
    assert [b["props"]["cites"] for b in blocks if b["type"] == "Story"] == [[1], [2], [3]]
    briefs = [b for b in blocks if b["type"] == "Briefs"][0]["props"]["items"]
    assert briefs[-1] == {"text": "Sixth story", "cites": [6]}


def test_no_items_gives_no_lines():
    assert build("- x [1]", []) == []


@pytest.mark.parametrize("answer", [
    None, "", "Nothing notable.", "- A [1][2][3]", "- A [1]\n- B [2]", "- [1]",
    "- Escalation pushed Brent above $106 [1][2].\n- A two-night pause in strikes sent Brent down 9% [3].\n"
    "- The pipeline restart eased prices [4].\n- OPEC+ paused output hikes [5].",
])
def test_output_always_validates(answer):
    lines = build(answer, ITEMS)
    check(lines)
    assert json.loads(lines[0]) == {"op": "add", "path": "/root", "value": "page"}
