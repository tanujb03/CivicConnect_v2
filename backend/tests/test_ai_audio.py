"""AUDIO evidence: Groq-Whisper-style transcription through the gateway into POST /cases/intake/analyze and the civic:ai_jobs worker (mocked provider).
The transcript and the detected language are stored on the analysis; an unconfigured or failing provider degrades with a visible warning and never fails the request."""
from __future__ import annotations

import pytest

from ai.inference.providers.fake import FakeProvider
from backend.tests.ai_helpers import SpeechProvider, down, install
from backend.tests.helpers import WAV, create_case, upload

INTAKE_OK = {"title": "No water supply", "description": "No water in the tap since morning", "category": "water_supply", "subcategory": "no_supply", "severity": "MEDIUM",
             "language": "hi", "transcript": None, "confidence": 0.9, "reasons": ["says no water"], "image_observations": []}


def audio(e, who="alice"):
    return upload(e, who, data=WAV, mime="audio/wav", name="voice.wav")["id"]


def analyse(e, ids, who="alice", text=None):
    r = e.client.post("/api/v1/cases/intake/analyze", headers=e.headers(who), json={"text": text, "evidence_ids": ids, "language_hint": "hi"})
    assert r.status_code == 200, r.text
    return r.json()


def rows(e, model, **where):
    with e.session_factory() as db:
        return db.query(model).filter_by(**where).order_by(model.created_at).all()


def intake_analysis(e):
    from backend.models import AIAnalysis
    got = rows(e, AIAnalysis, task_type="intake")
    assert got, "no intake analysis stored"
    return got[-1]


def test_intake_transcribes_audio_stores_text_and_detected_language_on_the_analysis(staffed):
    from backend.models import EvidenceItem
    e = staffed
    p = SpeechProvider(transcript="paani nahi aa raha subah se", language="hindi", structured={"intake": INTAKE_OK})
    install(p)
    ev = audio(e)
    body = analyse(e, [ev])
    assert body["proposal"]["transcript"] and "paani nahi aa raha" in body["proposal"]["transcript"]
    assert not [w for w in body["warnings"] if w.startswith("AUDIO_NOT_TRANSCRIBED")]
    a = intake_analysis(e)
    t = a.extra["transcription"]
    assert t["ok"] == 1 and t["detected_language"] == "hi" and a.extra["detected_language"] == "hi"
    assert t["items"][0] | {"text": None} == {"evidence_id": ev, "status": "ok", "text": None, "language": "hi", "language_source": "provider", "model": "whisper-test", "latency_ms": 3}
    assert t["items"][0]["text"] == "paani nahi aa raha subah se"
    assert rows(e, EvidenceItem, id=ev)[0].transcript == "paani nahi aa raha subah se"                    # persisted on the evidence item
    assert p.count("transcribe") == 1                                                                   # the adapter reused our transcript; no second provider call


def test_a_stored_transcript_is_reused_and_the_provider_is_not_called_again(staffed):
    e = staffed
    p = SpeechProvider(structured={"intake": INTAKE_OK})
    install(p)
    ev = audio(e)
    analyse(e, [ev])
    analyse(e, [ev])
    assert p.count("transcribe") == 1
    assert intake_analysis(e).extra["transcription"]["items"][0]["status"] == "stored"


def test_without_a_language_from_the_provider_the_local_heuristic_detects_it(staffed):
    e = staffed
    install(SpeechProvider(transcript="रस्त्यावर मोठा खड्डा पडला आहे", language=None, structured={"intake": {**INTAKE_OK, "language": "mr"}}))
    analyse(e, [audio(e)])
    item = intake_analysis(e).extra["transcription"]["items"][0]
    assert item["language"] == "mr" and item["language_source"] == "heuristic"


def test_a_language_we_do_not_handle_is_reported_as_other_not_guessed(staffed):
    e = staffed
    install(SpeechProvider(transcript="neer varuvathillai", language="tamil", structured={"intake": INTAKE_OK}))
    analyse(e, [audio(e)])
    assert intake_analysis(e).extra["detected_language"] == "other"


def test_no_provider_configured_degrades_with_one_visible_warning(staffed):
    e = staffed
    install(None)
    ev = audio(e)
    body = analyse(e, [ev], text="water problem near the temple")
    warns = [w for w in body["warnings"] if w.startswith("AUDIO_NOT_TRANSCRIBED")]
    assert len(warns) == 1 and ev in warns[0] and "no speech-to-text provider configured" in warns[0]
    assert ev in body["proposal"]["evidence_refs"] and body["proposal"]["category"]                         # still a usable proposal
    assert intake_analysis(e).extra["transcription"]["items"][0]["status"] == "unavailable"


@pytest.mark.parametrize("error", [down(), RuntimeError("socket exploded"), ValueError("bad payload")])
def test_a_failing_provider_never_fails_the_request(staffed, error):
    e = staffed
    p = SpeechProvider(error=error, structured={"intake": INTAKE_OK})
    install(p)
    ev = audio(e)
    body = analyse(e, [ev], text="no water since morning")
    warns = [w for w in body["warnings"] if w.startswith("AUDIO_NOT_TRANSCRIBED")]
    assert len(warns) == 1 and ev in warns[0] and type(error).__name__ in warns[0]
    assert p.count("transcribe") == 1                                                                   # tried once, not again inside the adapter
    t = intake_analysis(e).extra["transcription"]
    assert t["failed"] == 1 and t["items"][0]["status"] == "failed" and t["detected_language"] is None


def test_an_empty_transcript_counts_as_a_failure_with_a_warning(staffed):
    e = staffed
    install(SpeechProvider(transcript="   ", structured={"intake": INTAKE_OK}))
    body = analyse(e, [audio(e)], text="no water")
    assert any(w.startswith("AUDIO_NOT_TRANSCRIBED") and "empty" in w for w in body["warnings"])


# ---- the civic:ai_jobs worker ---------------------------------------------------------------------------------------------------------------------------------
def test_jobs_are_queued_in_order_and_transcribe_only_for_cases_with_audio(staffed, monkeypatch):
    e = staffed
    sent = []
    monkeypatch.setattr("backend.events.emit_ai_job", lambda job, case_id, report_id, payload: sent.append((job, case_id)))
    plain = create_case(e, "alice")
    voice = create_case(e, "alice", evidence_ids=[audio(e)])
    assert [j for j, c in sent if c == plain["id"]] == ["embed", "triage", "fusion"]
    assert [j for j, c in sent if c == voice["id"]] == ["transcribe", "embed", "triage", "fusion"]


def test_the_transcribe_job_stores_transcript_language_and_a_timeline_note(staffed):
    from backend.models import AIAnalysis, CaseEvent, EvidenceItem
    from backend.services.ai_jobs import run_job
    e = staffed
    p = SpeechProvider(transcript="paani nahi aa raha", language="hindi")
    install(p)
    ev = audio(e)
    case = create_case(e, "alice", evidence_ids=[ev])
    assert run_job("transcribe", case["id"]) == "transcribe: ok (1)"
    assert rows(e, EvidenceItem, id=ev)[0].transcript == "paani nahi aa raha"
    [a] = rows(e, AIAnalysis, case_id=case["id"], task_type="transcription")
    assert a.model == "whisper-test" and a.source == "provider" and a.degraded is False and a.extra["detected_language"] == "hi"
    assert a.result_json["items"][0]["text"] == "paani nahi aa raha" and a.result_json["detected_language"] == "hi"
    ev_row = [x for x in rows(e, CaseEvent, case_id=case["id"]) if x.event_type == "AUDIO_TRANSCRIBED"]
    assert len(ev_row) == 1 and ev_row[0].visibility == "INTERNAL" and ev_row[0].event_metadata["detected_language"] == "hi"
    assert run_job("transcribe", case["id"]) == "transcribe: nothing_to_do (0)" and p.count("transcribe") == 1       # idempotent
    own = e.client.get(f"/api/v1/cases/{case['id']}", headers=e.headers("alice")).json()
    assert "AUDIO_TRANSCRIBED" not in [t["event_type"] for t in own["timeline"]]                          # internal only


def test_the_transcript_becomes_case_text_for_the_ai(staffed):
    from backend.ai_gateway import get_gateway
    from backend.services.ai_jobs import run_job
    e = staffed
    install(SpeechProvider(transcript="drain is blocked near the market"))
    case = create_case(e, "alice", description="please look", evidence_ids=[audio(e)])
    assert "drain is blocked" not in get_gateway().repo.get_case(case["id"]).text
    run_job("transcribe", case["id"])
    text = get_gateway().repo.get_case(case["id"]).text
    assert text.startswith("please look") and "drain is blocked near the market" in text


@pytest.mark.parametrize("provider", [None, "down"])
def test_the_transcribe_job_degrades_visibly_when_the_provider_is_missing_or_down(staffed, provider):
    from backend.models import AIAnalysis, CaseEvent
    from backend.services.ai_jobs import run_job
    e = staffed
    install(None if provider is None else SpeechProvider(error=down()))
    case = create_case(e, "alice", evidence_ids=[audio(e)])
    out = run_job("transcribe", case["id"])
    assert out.startswith("transcribe: unavailable") and not out.startswith("failed")
    [a] = rows(e, AIAnalysis, case_id=case["id"], task_type="transcription")
    assert a.degraded is True and a.source == "none" and any(w.startswith("AUDIO_NOT_TRANSCRIBED") for w in a.result_json["warnings"])
    ev = [x for x in rows(e, CaseEvent, case_id=case["id"]) if x.event_type == "AUDIO_NOT_TRANSCRIBED"]
    assert len(ev) == 1 and ev[0].event_metadata["warnings"]
    assert e.client.get(f"/api/v1/cases/{case['id']}", headers=e.headers("alice")).status_code == 200      # the case is untouched


def test_a_case_without_audio_has_nothing_to_transcribe(staffed):
    from backend.services.ai_jobs import run_job
    e = staffed
    p = FakeProvider()
    install(p)
    case = create_case(e, "alice")
    assert run_job("transcribe", case["id"]) == "transcribe: nothing_to_do (0)" and not p.calls


def test_the_audio_endpoint_requests_verbose_json_so_the_language_comes_back():
    import httpx

    from ai.inference.schemas import EvidenceInput
    from backend.ai_gateway.providers import ChatCompletionsProvider
    seen = {}

    def handler(req):
        seen["body"] = req.content
        return httpx.Response(200, json={"text": "paani nahi aa raha", "language": "hindi", "duration": 2.1})

    p = ChatCompletionsProvider("groq", "https://api.example.test/v1", "SECRET-KEY-123", {"transcription": "whisper-x"}, client=httpx.Client(transport=httpx.MockTransport(handler)))
    t = p.transcribe(EvidenceInput(evidence_id="a", media_type="AUDIO", mime_type="audio/wav", data=b"RIFF"), None)
    assert b"verbose_json" in seen["body"] and t.language == "hindi" and t.text == "paani nahi aa raha"
