"""Cheap, deterministic checks on generated text: script/language sanity, length, PII-looking strings, duplicates."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_LATIN = re.compile(r"[A-Za-z]")
_PII = [re.compile(p) for p in (r"[\w.+-]+@[\w-]+\.[\w.]+", r"https?://|www\.", r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)", r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)")]
MIN_CHARS, MAX_CHARS = 6, 500


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", " ".join(text.split()))


def dedupe_key(text: str) -> str:
    return re.sub(r"[\W_]+", " ", normalize(text).lower()).strip()


def problems(text: str, language: str) -> list[str]:
    t = normalize(text)
    out: list[str] = []
    if not (MIN_CHARS <= len(t) <= MAX_CHARS):
        out.append("length")
    dev, lat = len(_DEVANAGARI.findall(t)), len(_LATIN.findall(t))
    letters = max(dev + lat, 1)
    if language in ("hi", "mr") and dev / letters < 0.6:
        out.append("script")
    if language in ("en", "hi-Latn") and (dev > 0 or lat / letters < 0.9):
        out.append("script")
    if any(p.search(t) for p in _PII):
        out.append("pii")
    return out


def clean_items(items: list[str], language: str, seen: set[str]) -> tuple[list[str], Counter]:
    """Keep valid, unseen texts (``seen`` is updated). Returns (kept, rejection counts)."""
    kept, rej = [], Counter()
    for raw in items:
        if not isinstance(raw, str):
            rej["not_text"] += 1
            continue
        t = normalize(raw)
        bad = problems(t, language)
        if bad:
            rej.update(bad)
            continue
        k = dedupe_key(t)
        if k in seen:
            rej["duplicate"] += 1
            continue
        seen.add(k)
        kept.append(t)
    return kept, rej
