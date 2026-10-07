"""Test doubles for the AI gateway in the database-backed tests (scripted providers, no network)."""
from __future__ import annotations

from ai.inference.errors import ProviderUnavailable
from ai.inference.provider import TranscriptResult
from ai.inference.providers.fake import FakeProvider
from ai.inference.service import AIService


def install(provider=None, classifier=None, embedder=None):
    """Swap the provider / classifier / local embedder of the process-wide (SQL-backed) gateway; returns the gateway. ``env`` resets it after each test."""
    from backend.ai_gateway import get_gateway
    gw = get_gateway()
    gw.ai = AIService(provider, classifier, None, gw.facts.executor)
    gw.embedder = embedder
    return gw


class SpeechProvider(FakeProvider):
    """FakeProvider whose speech-to-text can return a language (Whisper reports it by name, e.g. ``hindi``) or fail in any way."""

    def __init__(self, transcript="paani nahi aa raha", language: str | None = "hindi", error: Exception | None = None, **kw):
        super().__init__(**kw)
        self._text, self._lang, self._error = transcript, language, error

    def transcribe(self, audio, language_hint=None):
        self.calls.append(("transcribe", audio.evidence_id))
        if self._error is not None:
            raise self._error
        return TranscriptResult(text=self._text, model="whisper-test", latency_ms=3, language=self._lang)

    def count(self, kind: str) -> int:
        return sum(1 for k, *_ in self.calls if k == kind)


def down() -> Exception:
    return ProviderUnavailable("groq: HTTP 503", status_code=503)
