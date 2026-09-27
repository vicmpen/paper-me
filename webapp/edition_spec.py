"""Validate and apply an edition's JSONL patch lines (json-render SpecStream).

Compose (Claude) and the rules-based fallback both produce RFC 6902 patch
lines that build a json-render spec: {"root": id, "elements": {id: element}}.
EditionSpec applies one line at a time and rejects any line that would leave
an invalid element, so every line stored for a run is known-good. Prop
schemas come from webapp/catalog/catalog.schema.json, generated from the
frontend's Zod catalog (npm run export-catalog).

finalize() checks the finished page and applies the main story rule: a
LeadStory stands only when it is reported by at least two outlets and by
more outlets than every competing story; otherwise one "replace" line
demotes it to a major Story.
"""

from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parent / "catalog" / "catalog.schema.json"
MAX_ELEMENTS = 12
_ID_RE = re.compile(r"^[a-z0-9-]{1,32}$")
_ELEMENT_KEYS = {"type", "props", "children"}
_OPS = {"add", "replace", "remove"}


class InvalidLine(ValueError):
    """A patch line that must not be stored."""


class InvalidEdition(ValueError):
    """A finished spec that breaks the page rules."""


def outlet(url: str) -> str:
    """The outlet behind a URL: its lower-case hostname without a leading "www."."""
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return ""
    return host.lower().removeprefix("www.")


def dump_line(op: str, path: str, value: object = None) -> str:
    patch: dict = {"op": op, "path": path}
    if op != "remove":
        patch["value"] = value
    return json.dumps(patch, ensure_ascii=False, separators=(",", ":"))


def element(type_: str, props: dict, children: list[str] | None = None) -> dict:
    return {"type": type_, "props": props, "children": list(children or [])}


@lru_cache(maxsize=1)
def _validators() -> dict[str, Draft202012Validator]:
    schemas = json.loads(SCHEMA_PATH.read_text())
    return {name: Draft202012Validator(schema) for name, schema in schemas.items()}


def _cite_lists(value):
    """Every `cites` list anywhere inside a props value."""
    if isinstance(value, dict):
        for key, inner in value.items():
            if key == "cites":
                yield inner
            else:
                yield from _cite_lists(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _cite_lists(inner)


def _index(part: str, size: int) -> int:
    if not part.isdigit() or int(part) >= size:
        raise InvalidLine(f"bad array index {part!r}")
    return int(part)


def _step(target, part: str):
    if isinstance(target, dict) and part in target:
        return target[part]
    if isinstance(target, list):
        return target[_index(part, len(target))]
    raise InvalidLine(f"no such path segment {part!r}")


def _apply_nested(target, parts: list[str], op: str, value) -> None:
    for part in parts[:-1]:
        target = _step(target, part)
    last = parts[-1]
    if isinstance(target, dict):
        if op == "remove":
            if last not in target:
                raise InvalidLine(f"nothing to remove at {last!r}")
            del target[last]
        else:
            target[last] = value
    elif isinstance(target, list):
        if op == "add" and last == "-":
            target.append(value)
            return
        index = _index(last, len(target) + (1 if op == "add" else 0))
        if op == "add":
            target.insert(index, value)
        elif op == "replace":
            target[index] = value
        else:
            del target[index]
    else:
        raise InvalidLine("path goes through a value that is not an object or array")


class EditionSpec:
    def __init__(self, item_urls: list[str]) -> None:
        self.item_urls = list(item_urls)   # cite n -> item_urls[n - 1]
        self.root: str | None = None
        self.elements: dict[str, dict] = {}

    def apply_line(self, line: str) -> None:
        """Validate one patch line and apply it. Raises InvalidLine and leaves
        the spec unchanged when the line is malformed or would produce an
        invalid element."""
        try:
            patch = json.loads(line)
        except ValueError as e:
            raise InvalidLine(f"not JSON: {e}") from e
        if not isinstance(patch, dict) or set(patch) - {"op", "path", "value"}:
            raise InvalidLine("not a patch object")
        op, path = patch.get("op"), patch.get("path")
        if op not in _OPS or not isinstance(path, str) or not path.startswith("/"):
            raise InvalidLine(f"unsupported op {op!r} or path {path!r}")
        if op != "remove" and "value" not in patch:
            raise InvalidLine("missing value")
        value = patch.get("value")
        parts = [p.replace("~1", "/").replace("~0", "~") for p in path[1:].split("/")]

        if parts == ["root"]:
            if op == "remove" or not isinstance(value, str) or not _ID_RE.match(value):
                raise InvalidLine("root must be set to an element id")
            self.root = value
            return
        if parts[0] != "elements" or len(parts) < 2 or not _ID_RE.match(parts[1]):
            raise InvalidLine(f"path not allowed: {path}")
        eid = parts[1]
        if len(parts) == 2:
            if op == "remove":
                self.elements.pop(eid, None)
                return
            self._check_element(value)
            self.elements[eid] = copy.deepcopy(value)
            return
        if eid not in self.elements:
            raise InvalidLine(f"no element {eid!r}")
        updated = copy.deepcopy(self.elements[eid])
        _apply_nested(updated, parts[2:], op, copy.deepcopy(value))
        self._check_element(updated)
        self.elements[eid] = updated

    def _check_element(self, el: object) -> None:
        if not isinstance(el, dict) or set(el) != _ELEMENT_KEYS:
            raise InvalidLine("element must be exactly {type, props, children}")
        type_, props, children = el["type"], el["props"], el["children"]
        validator = _validators().get(type_) if isinstance(type_, str) else None
        if validator is None:
            raise InvalidLine(f"unknown component {type_!r}")
        if not isinstance(children, list) or not all(
                isinstance(c, str) and _ID_RE.match(c) for c in children):
            raise InvalidLine("children must be a list of element ids")
        if children and type_ != "Page":
            raise InvalidLine(f"{type_} cannot have children")
        error = next(iter(validator.iter_errors(props)), None)
        if error is not None:
            raise InvalidLine(f"{type_} props: {error.message}")
        k = len(self.item_urls)
        for cites in _cite_lists(props):
            if any(isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= k
                   for n in cites):
                raise InvalidLine(f"cites must be source numbers 1..{k}: {cites}")

    def outlets(self, cites: list[int]) -> set[str]:
        return {o for n in cites if (o := outlet(self.item_urls[n - 1]))}

    def finalize(self) -> list[str]:
        """Check the finished page. Returns the lines added by the main story
        rule (the lead demotion, or nothing). Raises InvalidEdition."""
        page = self.elements.get(self.root) if self.root else None
        if page is None or page["type"] != "Page":
            raise InvalidEdition("root is not a Page element")
        if len(self.elements) > MAX_ELEMENTS:
            raise InvalidEdition(f"{len(self.elements)} elements (max {MAX_ELEMENTS})")
        if sum(e["type"] == "Page" for e in self.elements.values()) != 1:
            raise InvalidEdition("more than one Page")
        missing = [c for c in page["children"] if c not in self.elements]
        if missing:
            raise InvalidEdition(f"missing children: {missing}")
        if self.root in page["children"]:
            raise InvalidEdition("Page lists itself as a child")
        if len(set(page["children"])) != len(page["children"]):
            raise InvalidEdition("Page has repeated children")
        leads = [eid for eid, e in self.elements.items() if e["type"] == "LeadStory"]
        if len(leads) > 1:
            raise InvalidEdition("more than one LeadStory")
        if not leads:
            return []
        lead_id = leads[0]
        if not page["children"] or page["children"][0] != lead_id:
            raise InvalidEdition("LeadStory must be the first child of Page")
        if self._lead_stands(lead_id, page["children"]):
            return []
        lead = self.elements[lead_id]["props"]
        props = {k: lead[k] for k in ("kicker", "headline", "dek", "cites") if k in lead}
        props["weight"] = "major"
        demotion = dump_line("replace", f"/elements/{lead_id}", element("Story", props))
        self.apply_line(demotion)
        return [demotion]

    def _lead_stands(self, lead_id: str, children: list[str]) -> bool:
        lead = self.outlets(self.elements[lead_id]["props"]["cites"])
        if len(lead) < 2:
            return False
        for eid in children:
            el = self.elements[eid]
            if eid == lead_id:
                continue
            if el["type"] == "Story":
                groups = [el["props"]["cites"]]
            elif el["type"] == "Briefs":
                groups = [item["cites"] for item in el["props"]["items"]]
            else:
                continue  # Split, Timeline, Figures and Analysis never compete
            for cites in groups:
                other = self.outlets(cites)
                if not other <= lead and len(other) >= len(lead):
                    return False
        return True
