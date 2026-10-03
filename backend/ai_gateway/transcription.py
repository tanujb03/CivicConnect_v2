"""Speech-to-text for AUDIO evidence, shared by ``POST /cases/intake/analyze`` and the ``civic:ai_jobs`` worker.

``transcribe_audio`` NEVER raises: an unconfigured or failing provider (Groq Whisper by default, see ``providers.factory``) becomes a visible ``AUDIO_NOT_TRANSCRIBED`` warning
and a record with ``status`` ``unavailable`` / ``failed``; the request or job carries on without the transcript. Each record holds the transcript, the detected language
(code ``en`` / ``hi`` / ``mr`` / ``hi-Latn`` / ``other``, with ``language_source`` saying whether the provider or the local heuristic produced it), model and latency, and is stored
on the ``AIAnalysis`` row (``extra.transcription``) by the callers. Media bytes are never logged or stored here.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from ai.inference.common import provider_ready
from ai.inference.language import detect_language
from ai.inference.schemas import EvidenceInput, W

log = logging.getLogger("civicconnect.transcription")
LANGUAGE_NAMES = {"english": "en", "hindi": "hi", "marathi": "mr"}      # Whisper reports the language by NAME ("hindi"); a few providers use ISO codes
SUPPORTED = {"en", "hi", "mr", "hi-latn"}
Saver = Callable[[str, str, "str | None"], None]


def normalize_language(raw: str | None, text: str, hint: str | None = None) -> tuple[str, str]:
    """(code, source). The provider's language when it is one we handle; the local script/marker heuristic otherwise (and ``other`` for a recognised foreign language)."""
    r = (raw or "").strip().lower()
    if r:
        code = LANGUAGE_NAMES.get(r, r)
        if code in SUPPORTED:
            return ("hi-Latn" if code == "hi-latn" else code), "provider"
        if code.isalpha() and len(code) >= 2:
            return "other", "provider"                                    # e.g. "tamil": say so rather than guessing Hindi
    return detect_language(text, hint), "heuristic"


def transcribe_audio(provider: Any, evidence: list[EvidenceInput], hint: str | None, warnings: list[str], save: Saver | None = None) -> list[dict]:
    """One record per AUDIO item (items that already carry a transcript are reported as ``stored`` and not sent to the provider again).

    Successful items get ``evidence.transcript`` set (so the intake adapter reuses it instead of calling the provider a second time); the caller leaves clips WITHOUT a
    transcript out of what the adapter sees (``usable_for_adapter``), so there is one warning per clip and no retry. ``save(evidence_id, text, language)`` persists the transcript on the evidence row; its failure is logged, never raised.
    """
    records: list[dict] = []
    for ev in evidence:
        if ev.media_type != "AUDIO":
            continue
        rec: dict[str, Any] = {"evidence_id": ev.evidence_id}
        if ev.transcript and ev.transcript.strip():
            lang, src = normalize_language(None, ev.transcript, hint)
            records.append({**rec, "status": "stored", "text": ev.transcript.strip(), "language": lang, "language_source": src, "model": None})
            continue
        if ev.data is None:
            records.append({**rec, "status": "unavailable", "reason": "no audio bytes"})
            warnings.append(W.make(W.AUDIO_NOT_TRANSCRIBED, f"audio {ev.evidence_id} has no readable audio data"))
            continue
        if not provider_ready(provider, "transcription"):
            records.append({**rec, "status": "unavailable", "reason": "no speech-to-text provider configured"})
            warnings.append(W.make(W.AUDIO_NOT_TRANSCRIBED, f"audio {ev.evidence_id} not transcribed (no speech-to-text provider configured)"))
            continue
        try:
            tr = provider.transcribe(ev, hint)
        except Exception as e:                                            # noqa: BLE001  (a provider outage must never fail the request or the job)
            log.warning("transcription failed for %s: %s", ev.evidence_id, type(e).__name__)
            records.append({**rec, "status": "failed", "reason": type(e).__name__})
            warnings.append(W.make(W.AUDIO_NOT_TRANSCRIBED, f"audio {ev.evidence_id} could not be transcribed ({type(e).__name__}); continuing without it"))
            continue
        text = (tr.text or "").strip()
        if not text:
            records.append({**rec, "status": "failed", "reason": "empty transcript"})
            warnings.append(W.make(W.AUDIO_NOT_TRANSCRIBED, f"audio {ev.evidence_id}: the provider returned an empty transcript"))
            continue
        lang, src = normalize_language(getattr(tr, "language", None), text, hint)
        ev.transcript = text
        records.append({**rec, "status": "ok", "text": text, "language": lang, "language_source": src, "model": getattr(tr, "model", None),
                        "latency_ms": getattr(tr, "latency_ms", None)})
        if save is not None:
            try:
                save(ev.evidence_id, text, lang)
            except Exception as e:                                        # noqa: BLE001
                log.warning("saving the transcript of %s failed: %s", ev.evidence_id, type(e).__name__)
    return records


def summarize(records: list[dict]) -> dict:
    """The compact form stored on the analysis: items + the language of the first transcript that has one."""
    langs = [r["language"] for r in records if r.get("language")]
    return {"items": records, "detected_language": langs[0] if langs else None, "ok": sum(r["status"] == "ok" for r in records),
            "failed": sum(r["status"] in ("failed", "unavailable") for r in records)}


def usable_for_adapter(evidence: list[EvidenceInput]) -> list[EvidenceInput]:
    """What the intake adapter may see: everything except audio that still has no transcript (those clips were reported by ``transcribe_audio`` already)."""
    return [e for e in evidence if e.media_type != "AUDIO" or (e.transcript and e.transcript.strip())]
