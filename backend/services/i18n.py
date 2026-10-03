"""Notification text in English, Hindi and Marathi, from fixed templates (no LLM, no translation service): the recipient's ``preferred_language`` selects the language.

``TEMPLATES[key][lang] = (title, message)``. The KEYS are a stable contract (clients and ``docs/I18N_REVIEW.md`` refer to them): never rename or reuse one, add new keys instead.
Placeholders are ``{name}``; ``{reason_line}`` is filled from ``params["reason"]`` with the language's word for "Reason" (empty when there is no reason). Free text typed by people
(rejection reasons, work-order instructions, incident titles) is inserted as written, never translated.

The hi / mr strings are first drafts written without a native-speaker review: ``docs/I18N_REVIEW.md`` lists every one of them (generated from this file by
``python -m backend.scripts.generate_i18n_review``; a test fails when it is stale).
"""
from __future__ import annotations

import re
from typing import Any

SUPPORTED = ("en", "hi", "mr")
DEFAULT = "en"
REASON_LABEL = {"en": "Reason", "hi": "कारण", "mr": "कारण"}

TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    # --- the reporter is told about a status change of their case (workflow.NOTIFY_STATES) -------------------------------------------------------------------------
    "case.status.assigned": {
        "en": ("Case {case_number}: Assigned", "Your report has been assigned to the responsible department.{reason_line}"),
        "hi": ("शिकायत {case_number}: सौंपी गई", "आपकी शिकायत संबंधित विभाग को सौंप दी गई है।{reason_line}"),
        "mr": ("तक्रार {case_number}: सोपवली", "तुमची तक्रार संबंधित विभागाकडे सोपवण्यात आली आहे.{reason_line}"),
    },
    "case.status.work_order_created": {
        "en": ("Case {case_number}: Work order created", "Work on your report has been scheduled.{reason_line}"),
        "hi": ("शिकायत {case_number}: कार्य आदेश बना", "आपकी शिकायत पर काम तय कर दिया गया है।{reason_line}"),
        "mr": ("तक्रार {case_number}: कामाचा आदेश तयार", "तुमच्या तक्रारीवरील काम ठरवण्यात आले आहे.{reason_line}"),
    },
    "case.status.in_progress": {
        "en": ("Case {case_number}: In progress", "Work on your report has started.{reason_line}"),
        "hi": ("शिकायत {case_number}: काम शुरू", "आपकी शिकायत पर काम शुरू हो गया है।{reason_line}"),
        "mr": ("तक्रार {case_number}: काम सुरू", "तुमच्या तक्रारीवरील काम सुरू झाले आहे.{reason_line}"),
    },
    "case.status.awaiting_verification": {
        "en": ("Case {case_number}: Awaiting verification", "The work is done. Please check and confirm that the problem is fixed.{reason_line}"),
        "hi": ("शिकायत {case_number}: सत्यापन की प्रतीक्षा", "काम पूरा हो गया है। कृपया देखकर पुष्टि करें कि समस्या ठीक हो गई है।{reason_line}"),
        "mr": ("तक्रार {case_number}: पडताळणीची प्रतीक्षा", "काम पूर्ण झाले आहे. कृपया पाहून समस्या दूर झाली आहे याची खात्री करा.{reason_line}"),
    },
    "case.status.resolved": {
        "en": ("Case {case_number}: Resolved", "Your report is marked as resolved. Thank you for helping your city.{reason_line}"),
        "hi": ("शिकायत {case_number}: निपटारा हुआ", "आपकी शिकायत का निपटारा हो गया है। अपने शहर की मदद करने के लिए धन्यवाद।{reason_line}"),
        "mr": ("तक्रार {case_number}: निकाली निघाली", "तुमची तक्रार निकाली काढण्यात आली आहे. शहराला मदत केल्याबद्दल धन्यवाद.{reason_line}"),
    },
    "case.status.reopened": {
        "en": ("Case {case_number}: Reopened", "Your report has been reopened for further work.{reason_line}"),
        "hi": ("शिकायत {case_number}: फिर से खोली गई", "आपकी शिकायत आगे की कार्रवाई के लिए फिर से खोली गई है।{reason_line}"),
        "mr": ("तक्रार {case_number}: पुन्हा उघडली", "तुमची तक्रार पुढील कार्यवाहीसाठी पुन्हा उघडण्यात आली आहे.{reason_line}"),
    },
    "case.status.rejected": {
        "en": ("Case {case_number}: Rejected", "Your report could not be accepted.{reason_line}"),
        "hi": ("शिकायत {case_number}: अस्वीकृत", "आपकी शिकायत स्वीकार नहीं की जा सकी।{reason_line}"),
        "mr": ("तक्रार {case_number}: नाकारली", "तुमची तक्रार स्वीकारता आली नाही.{reason_line}"),
    },
    # --- other events ----------------------------------------------------------------------------------------------------------------------------------------------
    "case.contributor_added": {
        "en": ("You were added to case {case_number}", "You can now follow this report and add to it."),
        "hi": ("आपको शिकायत {case_number} में जोड़ा गया", "अब आप इस शिकायत को देख सकते हैं और इसमें जानकारी जोड़ सकते हैं।"),
        "mr": ("तुम्हाला तक्रार {case_number} मध्ये जोडण्यात आले", "आता तुम्ही ही तक्रार पाहू शकता आणि त्यात भर घालू शकता."),
    },
    "staff.case.reopened_by_verification": {
        "en": ("Case {case_number} was reopened by verification ({result})", "The reporter did not confirm the fix."),
        "hi": ("शिकायत {case_number} सत्यापन के बाद फिर से खोली गई ({result})", "शिकायतकर्ता ने सुधार की पुष्टि नहीं की।"),
        "mr": ("तक्रार {case_number} पडताळणीनंतर पुन्हा उघडली ({result})", "तक्रारदाराने दुरुस्तीची पुष्टी केली नाही."),
    },
    "staff.case.partial_fix": {
        "en": ("Case {case_number}: partial fix reported by the citizen; needs a decision", "Please review the case and decide the next step."),
        "hi": ("शिकायत {case_number}: नागरिक ने आंशिक सुधार बताया; निर्णय आवश्यक है", "कृपया शिकायत देखें और अगला कदम तय करें।"),
        "mr": ("तक्रार {case_number}: नागरिकाने अंशतः दुरुस्ती कळवली; निर्णय आवश्यक आहे", "कृपया तक्रार तपासा आणि पुढील पाऊल ठरवा."),
    },
    "incident.created": {
        "en": ("Incident: {title}", "Related reports were grouped into an incident."),
        "hi": ("घटना: {title}", "संबंधित शिकायतों को एक घटना में जोड़ा गया है।"),
        "mr": ("घटना: {title}", "संबंधित तक्रारी एका घटनेत एकत्र करण्यात आल्या आहेत."),
    },
    "work_order.assigned": {
        "en": ("New work order for case {case_number}", "{instructions}"),
        "hi": ("शिकायत {case_number} के लिए नया कार्य आदेश", "{instructions}"),
        "mr": ("तक्रार {case_number} साठी नवीन कामाचा आदेश", "{instructions}"),
    },
}
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


class _Params(dict):
    def __missing__(self, key: str) -> str:
        return ""


def normalize_language(code: str | None) -> str:
    """``hi-IN`` / ``HI`` / ``mr_IN`` -> ``hi`` / ``hi`` / ``mr``; anything we have no templates for -> English."""
    base = re.split(r"[-_]", (code or "").strip().lower())[0]
    return base if base in SUPPORTED else DEFAULT


def placeholders(template: str) -> set[str]:
    return set(_PLACEHOLDER.findall(template))


def render(key: str, language: str | None, params: dict[str, Any] | None = None) -> tuple[str, str, str] | None:
    """(title, message, language_used) or None for an unknown key (the caller then keeps its own text). A missing language falls back to English."""
    entry = TEMPLATES.get(key)
    if entry is None:
        return None
    lang = normalize_language(language)
    lang = lang if lang in entry else DEFAULT
    values = _Params({k: ("" if v is None else str(v)) for k, v in (params or {}).items()})
    reason = values.get("reason", "").strip()
    values["reason_line"] = f" {REASON_LABEL[lang]}: {reason}" if reason else ""
    title, message = entry[lang]
    return title.format_map(values).strip(), message.format_map(values).strip(), lang
