"""Keeps the notification-template section of docs/I18N_REVIEW.md in sync with ``backend.services.i18n.TEMPLATES``: every Hindi and Marathi string, for native-speaker review.

    python -m backend.scripts.generate_i18n_review

docs/I18N_REVIEW.md is shared with the review checklist of the LLM-written gold set (ML track). This script owns ONLY the block between the two marker comments (it replaces it, or
appends it when the markers are missing) and never touches the rest. A test fails when the block is stale: fix a string in ``backend/services/i18n.py`` and run this again.
Keep the template KEYS and the ``{placeholders}`` unchanged.
"""
from __future__ import annotations

from pathlib import Path

from backend.services import i18n

OUT = Path(__file__).resolve().parents[2] / "docs" / "I18N_REVIEW.md"
BEGIN = "<!-- BEGIN GENERATED: notification templates (backend/services/i18n.py); do not edit by hand -->"
END = "<!-- END GENERATED: notification templates -->"
NAMES = {"en": "English (source)", "hi": "Hindi", "mr": "Marathi"}

HEADER = """## Backend notification templates (Hindi and Marathi): NOT REVIEWED

**Status: NOT REVIEWED.** Every `hi` and `mr` string in this section is a first draft written by the AI assistant (Claude) without a native speaker checking it. Do not treat them
as final wording in a release. The English strings are the source of meaning. This section is generated from `backend/services/i18n.py`
(`python -m backend.scripts.generate_i18n_review`; a test fails if it is out of date): to change a string edit `TEMPLATES` there and regenerate, and tick the box here once a native
speaker has approved the row.

### How the strings are used

- `notify(..., template=<key>, params=...)` renders the title and message from these fixed templates in the **recipient's** `preferred_language` (`en`, `hi`, `mr`; `hi-IN` counts as
  `hi`; any other language falls back to English). No LLM and no translation service is involved. The notification payload carries `template`, `params` and `language`.
- **Keys are a stable contract** with the clients. Never rename or reuse a key; add a new one instead.
- `{case_number}`, `{result}`, `{title}`, `{instructions}` are filled in as written. `{reason_line}` becomes ` Reason: <text>` / ` कारण: <text>` when a reason was given, else nothing.
  Free text typed by people (reasons, instructions, incident titles) is inserted as written and is **not** translated.
- This is different from the *intake* title and summary in the citizen's language (`title_local` / `summary_local`): those are written by the AI provider at intake time,
  are presentation only, and the canonical English fields stay the source of truth (design section 14).

### Please check in particular

- Register: the drafts address the citizen politely (Hindi *आप*, Marathi *तुम्ही*). Is that right for municipal messages?
- Terms: Hindi *शिकायत* / Marathi *तक्रार* (report/complaint), *निपटारा* / *निकाली* (resolved), *सत्यापन* / *पडताळणी* (verification), *कार्य आदेश* / *कामाचा आदेश* (work order),
  *घटना* (incident). Prefer the words the city's own forms use.
- Grammar of gender and number in the status titles (e.g. *सौंपी गई*, *सोपवली*, *नाकारली*).
- Length: these are push/in-app notification titles; shorter is better.

### Strings

| Key | Language | Title | Message | Reviewed |
|---|---|---|---|---|
"""


def render_block() -> str:
    rows = []
    for key, by_lang in i18n.TEMPLATES.items():
        for lang in i18n.SUPPORTED:
            title, message = by_lang[lang]
            mark = "n/a (source)" if lang == "en" else "☐"
            rows.append(f"| `{key}` | {NAMES[lang]} | {title} | {message} | {mark} |")
    return f"{BEGIN}\n{HEADER}" + "\n".join(rows) + f"\n{END}\n"


def block_of(text: str) -> str | None:
    """The generated block as it stands in ``text`` (markers included), or None when the markers are missing."""
    a, b = text.find(BEGIN), text.find(END)
    return text[a:b + len(END)] + "\n" if a != -1 and b > a else None


def merged(existing: str) -> str:
    """``existing`` with the generated block replaced, or appended after the existing content when there is none yet."""
    block = render_block()
    a, b = existing.find(BEGIN), existing.find(END)
    if a != -1 and b > a:
        return existing[:a] + block + existing[b + len(END):].lstrip("\n")
    return existing.rstrip("\n") + "\n\n" + block if existing.strip() else block


if __name__ == "__main__":
    OUT.write_text(merged(OUT.read_text(encoding="utf-8") if OUT.exists() else ""), encoding="utf-8", newline="\n")
    print(f"updated {OUT} ({len(i18n.TEMPLATES)} keys)")
