"""SYNTHETIC AI-4 (resolution intelligence) scenarios: "a field worker completed a work order" events with planted ground truth.

Each scenario is an overlay on a demo-city case (it borrows the case's category/description/language) and carries what AI-4 may observe
(photo presence, field notes, citizen verification) plus the planted truth the model must not see (``truly_unresolved``) and which signal could
reveal it (``detectable_by``). There are NO images here: photo presence is a flag. Real before/after evidence does not exist anywhere in the project,
so the vision part of AI-4 cannot be evaluated on this data; what it CAN measure is the deterministic baseline (flag-only, monotonic) and how much
of the problem sits outside it.
"""
from __future__ import annotations

import random
import uuid
from typing import Mapping, Sequence

RESOLUTION_VERSION = "resolution-scenarios/1"
DEFAULT_SEED = 20261002

# (archetype, weight, truly_unresolved, citizen_verification choices, after_photo, notes_kind, detectable_by)
ARCHETYPES = [
    ("fixed_confirmed", 30, False, ("YES",), True, "genuine", "none_needed"),
    ("fixed_pending", 25, False, (None,), True, "genuine", "none_needed"),
    ("fixed_sparse", 8, False, (None, "YES"), True, "brief", "none_needed"),
    ("no_after_evidence", 7, False, (None,), False, "empty", "none_needed"),
    ("unfixed_reported", 12, True, ("STILL_OCCURRING", "NO"), True, "genuine", "citizen_signal"),
    ("partial_reported", 6, True, ("PARTIAL",), True, "genuine", "citizen_signal"),
    ("unfixed_silent_notes", 8, True, (None,), True, "deferral", "notes_text"),
    ("unfixed_silent_no_signal", 4, True, (None,), True, "genuine", "images_only"),
]

NOTES = {
    "genuine": {
        "en": ["Filled and compacted the damaged area, site cleared.", "Repair completed, tested and area cleaned up.", "Work done as instructed; debris removed from the site."],
        "hi": ["क्षतिग्रस्त जगह की मरम्मत कर दी गई है और साइट साफ़ कर दी गई।", "काम पूरा हुआ, जाँच कर ली गई और मलबा हटा दिया गया।"],
        "mr": ["खराब झालेल्या जागेची दुरुस्ती केली असून जागा स्वच्छ केली आहे.", "काम पूर्ण झाले, तपासणी केली आणि राडारोडा हटवला."],
        "hi-Latn": ["Kharab jagah ki repair kar di gayi hai aur site saaf kar di.", "Kaam poora ho gaya, check kar liya aur malba hata diya."],
    },
    "brief": {"en": ["done", "fixed"], "hi": ["हो गया"], "mr": ["झाले"], "hi-Latn": ["ho gaya"]},
    "deferral": {
        "en": ["Temporary patch only; permanent repair pending material.", "Could not complete, will return next week; closed for now.",
               "Partly done, remaining work needs another team."],
        "hi": ["सिर्फ़ अस्थायी मरम्मत की है, स्थायी काम सामग्री आने पर होगा।", "काम पूरा नहीं हो सका, अगले हफ़्ते दोबारा आएँगे।"],
        "mr": ["फक्त तात्पुरती दुरुस्ती केली आहे, कायमस्वरूपी काम साहित्य आल्यावर होईल.", "काम पूर्ण झाले नाही, पुढील आठवड्यात पुन्हा येऊ."],
        "hi-Latn": ["Sirf temporary repair ki hai, permanent kaam material aane par hoga.", "Kaam poora nahi hua, agle hafte wapas aayenge."],
    },
    "empty": {"en": [""], "hi": [""], "mr": [""], "hi-Latn": [""]},
}


def build_scenarios(cases: Sequence[Mapping], work_orders: Sequence[Mapping], signals: Mapping[str, Mapping], *, seed: int = DEFAULT_SEED, n: int = 240) -> list[dict]:
    """Deterministic: same inputs + seed => identical output. ``signals`` maps case_id -> primary report signal (for the description text)."""
    rng = random.Random(seed)
    by_id = {c["id"]: c for c in cases}
    completed = sorted((w for w in work_orders if w["status"] == "COMPLETED" and w["case_id"] in by_id), key=lambda w: w["id"])
    rng.shuffle(completed)
    picked = completed[:n]
    names = [a[0] for a in ARCHETYPES]
    weights = [a[1] for a in ARCHETYPES]
    plan = rng.choices(names, weights=weights, k=len(picked))
    spec = {a[0]: a for a in ARCHETYPES}
    out = []
    for wo, arche in zip(picked, plan):
        _, _, unresolved, verifs, after, notes_kind, detect = spec[arche]
        c = by_id[wo["case_id"]]
        lang = c.get("language") or "en"
        pool = NOTES[notes_kind].get(lang) or NOTES[notes_kind]["en"]
        sig = signals.get(c["id"]) or {}
        out.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"civicconnect-demo-resolution/{seed}/{wo['id']}")),
            "case_id": c["id"], "work_order_id": wo["id"], "category": c["category"], "subcategory": c.get("subcategory"),
            "description": sig.get("original_text") or c.get("canonical_description"), "language": lang,
            "archetype": arche, "has_original_photo": True, "has_resolution_photo": after,
            "field_notes": rng.choice(pool), "notes_kind": notes_kind, "citizen_verification": rng.choice(verifs),
            "truly_unresolved": unresolved, "detectable_by": detect, "synthetic": True})
    return sorted(out, key=lambda r: r["id"])
