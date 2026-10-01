"""Cheap script/marker based language identification for en / hi / mr / hi-Latn.

Heuristic only (used for fallback and for sanity-checking provider output).
It is *not* a general language identifier and is documented as such in the
model card. Hindi vs Marathi in Devanagari relies on function-word markers.
"""
from __future__ import annotations

import re

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-z]")
_WORD = re.compile(r"[\wऀ-ॿ]+", re.UNICODE)

_MR_MARKERS = {"आहे", "आहेत", "नाही", "नाहीत", "च्या", "चा", "ची", "चे", "मध्ये", "आणि", "येथे", "जवळ",
               "पडला", "पडले", "झाला", "झाली", "झाले", "करा", "कृपया", "पासून", "साठी", "तुंबले", "गेले"}
_HI_MARKERS = {"है", "हैं", "नहीं", "में", "और", "का", "की", "के", "पर", "से", "को", "के पास",
               "रहा", "रही", "रहे", "गया", "गई", "गए", "कृपया", "लिए", "हो"}
_HINGLISH = {"hai", "hain", "nahi", "nahin", "ka", "ke", "ki", "ko", "mein", "me", "par", "pe", "se", "paas",
             "bahut", "bohot", "raha", "rahi", "rahe", "gaya", "gayi", "gaye", "kripya", "kab", "tak",
             "hua", "hui", "hue", "abhi", "pura", "poora", "kal", "din", "bhi", "aur", "kar", "karo",
             "karein", "chahiye", "wala", "wali", "yahan", "wahan", "sadak", "paani", "pani", "kachra"}


def detect_language(text: str, hint: str | None = None) -> str:
    """Return one of ``en``, ``hi``, ``mr``, ``hi-Latn``."""
    if not text or not text.strip():
        return hint if hint in {"en", "hi", "mr", "hi-Latn"} else "en"
    deva = len(_DEVANAGARI.findall(text))
    latin = len(_LATIN.findall(text))
    words = {w.casefold() for w in _WORD.findall(text)}
    if deva and deva >= latin:
        mr = len(words & _MR_MARKERS)
        hi = len(words & _HI_MARKERS)
        if mr > hi:
            return "mr"
        if hi > mr:
            return "hi"
        return hint if hint in {"hi", "mr"} else "hi"
    hits = len(words & _HINGLISH)
    if hits >= 2 or (deva and latin and hits >= 1):
        return "hi-Latn"
    return "en"
