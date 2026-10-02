"""What the LLM-written training corpus covers: every taxonomy subcategory x language x style. All text is SYNTHETIC (written by a language model); it is never real citizen data."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ai.inference.config import Taxonomy, load_taxonomy

LANGUAGES = {
    "en": "English as written by Indian citizens (municipal corporation, ward office, society, lane/gali, etc.)",
    "hi": "Hindi in Devanagari script",
    "mr": "Marathi in Devanagari script",
    "hi-Latn": "Hinglish: Hindi written in Roman (English) letters, the way people type on a phone",
}
STYLES = {
    "voice_transcript": "a speech-to-text transcript of a spoken complaint: run-on sentence, no punctuation, filler words, a mis-heard word or two",
    "sms_short": "very short SMS/WhatsApp style, abbreviations, under 15 words",
    "angry": "frustrated tone with strong feeling, but no abuse and no slurs",
    "polite_formal": "formal letter-style complaint addressed to the municipal officer",
    "elderly_simple": "simple words, as an elderly person would write, mentions how it affects them",
    "code_mixed": "a natural mix of two languages as people really type (e.g. Marathi or Hindi with English words)",
    "typo_noisy": "typed fast on a phone with spelling mistakes and missing punctuation",
    "landmark": "names a nearby landmark (school, temple, bus stop, market, hospital) and an invented locality",
    "detailed_story": "two or three sentences: how long it has been happening and how it affects daily life",
}
# Short plain-English meanings so the writer model does not guess what a label means. Only used inside generation prompts.
HINTS = {
    "other/unclassified": "an issue that does not fit any civic category (noise, air pollution, illegal construction on private land, unclear or very vague complaint, or non-civic request)",
}


@dataclass(frozen=True)
class Cell:
    category: str
    subcategory: str
    label_en: str
    label_hi: str
    label_mr: str
    language: str
    style: str
    k: int

    @property
    def label_id(self) -> str:
        return f"{self.category}/{self.subcategory}"

    @property
    def cell_id(self) -> str:
        return hashlib.sha1(f"{self.label_id}|{self.language}|{self.style}|{self.k}".encode()).hexdigest()[:16]


def build_cells(taxonomy: Taxonomy | None = None, languages=None, styles=None, k: int = 12) -> list[Cell]:
    t = taxonomy or load_taxonomy()
    langs = list(languages or LANGUAGES)
    stys = list(styles or STYLES)
    out = []
    for sid, sub in sorted(t.subcategories.items()):
        for lang in langs:
            for sty in stys:
                out.append(Cell(sub.category_id, sid, sub.label.get("en", sid), sub.label.get("hi", ""), sub.label.get("mr", ""), lang, sty, k))
    return out


SYSTEM = ("You write realistic complaints that Indian citizens submit to a municipal grievance system, for training a classifier. "
          "Reply with ONE JSON object only. Never include real people's names, phone numbers, e-mail addresses or links.")
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["items"],
          "properties": {"items": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["text"], "properties": {"text": {"type": "string"}}}}}}


def prompt_for(c: Cell) -> tuple[str, str]:
    hint = HINTS.get(c.label_id, "")
    issue = f"{c.label_en}" + (f" (Hindi: {c.label_hi}; Marathi: {c.label_mr})" if c.label_hi else "") + (f" - {hint}" if hint else "")
    user = (f"Write {c.k} DIFFERENT complaints about this issue: {issue}\n"
            f"Language: {LANGUAGES[c.language]}\nStyle: {STYLES[c.style]}\n\n"
            "Rules:\n- Every item is a separate citizen complaining about exactly this issue type, in the language above.\n"
            "- Vary vocabulary, sentence structure, length, locality names and details; do not repeat openings.\n"
            "- Do not mention category names or ids; write what a person would actually say or type.\n"
            "- Use invented localities and landmarks only.\n"
            f'Return {{"items": [{{"text": "..."}}, ...]}} with exactly {c.k} items.')
    return SYSTEM, user
