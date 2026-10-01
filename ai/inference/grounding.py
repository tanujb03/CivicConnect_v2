"""Numeric grounding checks: every number a model writes must come from facts.

Used by AI-5 (analytics explanations) and AI-6 (copilot answers) so a model can
explain deterministic results but cannot invent figures (Sections 11 AI-5, 40).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def _ascii_digits(text: str) -> str:
    return "".join(str(unicodedata.digit(c)) if c.isdigit() and not c.isascii() else c for c in text)


def _canon(tok: str) -> str:
    t = tok.replace(",", "")
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    t = t.lstrip("0") or "0"
    return t if not t.startswith(".") else "0" + t


def numeric_tokens(text: str) -> set[str]:
    """Canonical numeric tokens in ``text`` (thousands separators and trailing zeros normalised)."""
    out: set[str] = set()
    for m in _NUM.findall(_ascii_digits(text)):
        out.add(_canon(m))
        # "1,234.5" style and plain digit runs both covered; also add integer part for "7.0"
        if "." in m:
            out.add(_canon(m.split(".")[0]))
    return out


def allowed_numbers(sources: Iterable[object]) -> set[str]:
    allowed: set[str] = set()
    for s in sources:
        allowed |= numeric_tokens(str(s))
    return allowed


def ungrounded_numbers(text: str, allowed: set[str]) -> set[str]:
    return numeric_tokens(text) - allowed
