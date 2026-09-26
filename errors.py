"""Error-message sanitization shared by the email pipeline and the web app."""

from __future__ import annotations

import re


# Provider exceptions routinely embed account identifiers (org UUIDs,
# request IDs) and the recipient address back from the API. Strip those
# before the message hits token_usage.jsonl or the digest email body —
# the repo is public, so anything written to disk is published.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_API_KEY_RE = re.compile(r"\b(?:sk-[A-Za-z0-9_-]+|AIza[A-Za-z0-9_-]+|re_[A-Za-z0-9_-]+)\b")
_REQ_ID_RE = re.compile(r"\breq_[A-Za-z0-9]+\b")


def sanitize_error(e: BaseException) -> str:
    msg = str(e)
    msg = _EMAIL_RE.sub("[email]", msg)
    msg = _API_KEY_RE.sub("[apikey]", msg)
    msg = _UUID_RE.sub("[uuid]", msg)
    msg = _REQ_ID_RE.sub("[reqid]", msg)
    return f"{type(e).__name__}: {msg}"
