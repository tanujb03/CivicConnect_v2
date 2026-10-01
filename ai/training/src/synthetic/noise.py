"""Spelling/typing noise that is safe for Latin and Devanagari text."""
from __future__ import annotations

import random
import unicodedata


def clusters(text: str) -> list[str]:
    """Split into base-char + combining-mark clusters so matras stay attached."""
    out: list[str] = []
    for ch in text:
        if out and (unicodedata.category(ch).startswith("M") or ch in "‍‌"):
            out[-1] += ch
        else:
            out.append(ch)
    return out


def add_spelling_noise(text: str, rng: random.Random, rate: float = 0.04) -> str:
    cs = clusters(text)
    i, out = 0, []
    while i < len(cs):
        c = cs[i]
        if c.isspace() or not c.strip() or rng.random() >= rate:
            out.append(c)
            i += 1
            continue
        op = rng.choice(("delete", "duplicate", "swap"))
        if op == "delete":
            pass
        elif op == "duplicate":
            out.extend([c, c])
        elif i + 1 < len(cs) and not cs[i + 1].isspace():
            out.extend([cs[i + 1], c])
            i += 1
        else:
            out.append(c)
        i += 1
    return "".join(out)


def add_surface_noise(text: str, rng: random.Random) -> str:
    """Casing / punctuation noise typical of phone-typed complaints."""
    r = rng.random()
    if r < 0.08:
        return text.upper()
    if r < 0.30:
        return text.lower()
    if r < 0.45:
        return "".join(ch for ch in text if ch not in ".,!:;।")
    return text
