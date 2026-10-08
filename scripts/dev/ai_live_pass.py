"""WP1 step 4: exercise the real AI endpoints of a running API once and record, per call, provider, latency, schema validity, confidence and warnings.

    python scripts/dev/ai_live_pass.py --base-url http://localhost:8000/api/v1 --photo D:\\civic-test-media\\photos\\Pot_holes.jpg \\
        --audio hi=D:\\civic-test-media\\voice\\pothole_hi.mp3 --audio mr=D:\\civic-test-media\\voice\\pothole_mr.mp3 --json-out pass.json

Synthetic content only (demo accounts of the seeded demo city, the public test photo and the synthetic voice clips). The demo password is the development setting
DEMO_PASSWORD (env var of the same name, else backend settings); no key or token is ever printed. Run it twice, once with the provider keys set and once against an API started
without them, to record the degraded path. Exit code 0 even when a provider is rate limited: the point is to record what happened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pydantic import ValidationError  # noqa: E402

from backend.ai_gateway import contracts as C  # noqa: E402

DOMAIN = "demo.civicconnect.test"
ACCOUNTS = {"citizen": f"citizen001@{DOMAIN}", "operator": f"operator.drainage_sewerage@{DOMAIN}", "admin": f"admin@{DOMAIN}"}
TEXTS = {
    "en": "There is a big pothole near the school gate on Station Road, it is dangerous for children and two-wheelers.",
    "hi": "स्टेशन रोड पर स्कूल के गेट के पास सड़क में बड़ा गड्ढा है, बच्चों और दोपहिया वाहनों के लिए खतरनाक है।",
    "mr": "स्टेशन रोडवर शाळेच्या गेटजवळ रस्त्यात मोठा खड्डा आहे, मुलांसाठी आणि दुचाकींसाठी धोकादायक आहे.",
}


class Runner:
    def __init__(self, base: str, password: str):
        self.base, self.password, self.rows, self.tokens = base.rstrip("/"), password, [], {}
        self.http = httpx.Client(timeout=120.0)

    def login(self, who: str) -> dict:
        r = self.http.post(f"{self.base}/auth/login", json={"identifier": ACCOUNTS[who], "password": self.password})
        r.raise_for_status()
        self.tokens[who] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return self.tokens[who]

    def call(self, name: str, who: str, method: str, path: str, model, **kw) -> dict | None:
        t0 = time.perf_counter()
        r = self.http.request(method, f"{self.base}{path}", headers=self.tokens[who], **kw)
        ms = int((time.perf_counter() - t0) * 1000)
        row = {"call": name, "http": r.status_code, "latency_ms": ms}
        body = None
        try:
            body = r.json()
        except ValueError:
            row["error"] = "non-JSON body"
        if r.status_code == 200 and body is not None:
            try:
                model.model_validate(body)
                row["schema_valid"] = True
            except ValidationError as exc:
                row["schema_valid"] = False
                row["error"] = f"{len(exc.errors())} schema errors"
            meta = body.get("ai_metadata") or {}
            row.update({"source": meta.get("source"), "provider": meta.get("provider"), "model": meta.get("model"), "degraded": meta.get("degraded"),
                        "confidence": body.get("confidence"), "warnings": [str(w)[:90] for w in (body.get("warnings") or [])][:4]})
            if "proposal" in body:
                row["proposal"] = {k: body["proposal"].get(k) for k in ("category", "subcategory", "severity", "language")}
            if "recommendation" in body:
                row["recommendation"] = body["recommendation"] if isinstance(body["recommendation"], str) else {k: body["recommendation"].get(k) for k in ("severity", "priority", "department_id")}
            if "answer" in body:
                row["answer_chars"] = len(body["answer"] or "")
                row["tool_calls"] = len(body.get("tool_calls") or [])
        elif body is not None:
            err = (body.get("error") or {}) if isinstance(body, dict) else {}
            row["error"] = f"{err.get('code')}: {str(err.get('message'))[:100]}"
        self.rows.append(row)
        return body if r.status_code == 200 else None

    def upload(self, who: str, path: Path, mime: str) -> str:
        data = path.read_bytes()
        init = self.http.post(f"{self.base}/evidence/upload-init", headers={**self.tokens[who], "Idempotency-Key": f"pass-{hashlib.sha256(data).hexdigest()[:16]}-{time.time_ns()}"},
                              json={"filename": path.name, "mime_type": mime, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "purpose": "REPORT"})
        init.raise_for_status()
        j = init.json()
        put = self.http.put(j["upload_url"], content=data, headers={**j.get("headers", {}), "Content-Type": mime})
        put.raise_for_status()
        done = self.http.post(f"{self.base}/evidence/{j['evidence_id']}/complete", headers={**self.tokens[who], "Idempotency-Key": f"done-{time.time_ns()}"})
        done.raise_for_status()
        return j["evidence_id"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default="http://localhost:8000/api/v1")
    ap.add_argument("--photo", type=Path)
    ap.add_argument("--audio", action="append", default=[], help="LANG=path (repeatable)")
    ap.add_argument("--scene", action="append", default=[], metavar="LABEL=PATH:EXPECTED",
                    help="photo-only intake: the image is the ONLY input (no text, no language hint), so the answer cannot come from words; EXPECTED is the taxonomy category the scene "
                         "should map to (roads, sanitation, street_lighting, ...). Repeatable. With --scene only the scenes are run (no other calls)")
    ap.add_argument("--json-out", type=Path)
    ap.add_argument("--pause", type=float, default=7.0, help="seconds between calls; at least 6 s for gemini-3.5-flash-lite (15 requests/min), see --flash")
    ap.add_argument("--flash", action="store_true", help="the scarce gemini-3.5-flash is configured (5 requests/min, 20/day): pause at least 13 s and send at most 5 AI calls in total. "
                                                         "Only when Tanuj says the quota has rested (docs/AI_LIVE_CHECK.md)")
    ap.add_argument("--keep-going", action="store_true", help="do not stop at the first call that degraded because the provider failed (default: stop, so a 429 is not hammered)")
    a = ap.parse_args()
    password = os.environ.get("DEMO_PASSWORD")
    if not password:
        from backend.core.config import settings
        password = settings.DEMO_PASSWORD
    a.pause = max(a.pause, 13.0 if a.flash else 6.0)
    run = Runner(a.base_url, password)
    for who in ACCOUNTS:
        run.login(who)

    budget = {"ai": 5 if a.flash else None}             # Gemini-backed calls still allowed (flash: 5 in total)

    def ai_call_allowed() -> bool:
        if budget["ai"] is None:
            return True
        if budget["ai"] <= 0:
            print("flash call budget (5) used up: stopping")
            return False
        budget["ai"] -= 1
        return True

    def failed() -> bool:
        """True when the last call degraded because the PROVIDER failed (quota 429, outage): do not keep sending (the exact message is in the API log line 'provider call failed')."""
        row = run.rows[-1] if run.rows else {}
        bad = any(str(w).startswith("PROVIDER_UNAVAILABLE") for w in row.get("warnings") or []) or "PROVIDER_UNAVAILABLE" in str(row.get("error", ""))
        if bad and not a.keep_going:
            print(f"STOP: '{row.get('call')}' degraded because the provider failed. Not sending more calls. Read the API log line 'provider call failed' for the provider's exact message "
                  f"and quota id; do not rerun until the limit has reset.")
        return bad and not a.keep_going

    def pause():
        time.sleep(a.pause)

    steps: list = []
    scenes: dict[str, str] = {}                                  # label -> expected category
    for spec in a.scene:
        label, _, rest = spec.partition("=")
        path_, _, expected = rest.rpartition(":")
        scenes[f"photo only: {label}"] = expected
        steps.append((f"photo only: {label}", "citizen", "/cases/intake/analyze", C.IntakeAnalyzeResponse,
                      lambda path_=path_: {"evidence_ids": [run.upload("citizen", Path(path_), "image/jpeg")]}))
    for lang, text in ({} if scenes else TEXTS).items():
        steps.append((f"intake text {lang}", "citizen", "/cases/intake/analyze", C.IntakeAnalyzeResponse, lambda lang=lang, text=text: {"text": text, "language_hint": lang}))
    if a.photo and not scenes:
        steps.append(("intake photo + text en", "citizen", "/cases/intake/analyze", C.IntakeAnalyzeResponse,
                      lambda: {"text": "Road damage here", "evidence_ids": [run.upload("citizen", a.photo, "image/jpeg")]}))
    for spec in ([] if scenes else a.audio):
        lang, _, ap_ = spec.partition("=")
        steps.append((f"intake audio {lang}", "citizen", "/cases/intake/analyze", C.IntakeAnalyzeResponse,
                      lambda lang=lang, ap_=ap_: {"evidence_ids": [run.upload("citizen", Path(ap_), "audio/mpeg")], "language_hint": lang}))
    cases = [] if scenes else run.http.get(f"{a.base_url.rstrip('/')}/cases", headers=run.tokens["operator"], params={"limit": 5}).json().get("items", [])
    if cases:
        cid = cases[0]["id"]
        steps.append(("triage on a demo case", "operator", f"/cases/{cid}/triage/analyze", C.TriageAnalyzeResponse, lambda: {}))
    if not scenes:
        steps.append(("copilot: open cases by category", "admin", "/copilot/query", C.CopilotQueryResponse, lambda: {"query": "How many open cases are there per category in the city?"}))
    for i, (name, who, path, model, body) in enumerate(steps):
        if not ai_call_allowed():
            break
        if i:
            pause()
        run.call(name, who, "POST", path, model, json=body())
        if failed():
            break
    if cases and not any(r["call"].startswith("fusion") for r in run.rows):            # fusion is rules + embeddings, not a text-model call: always cheap
        run.call("fusion on a demo case", "operator", "POST", f"/cases/{cases[0]['id']}/fusion/analyze", C.FusionAnalyzeResponse, json={})

    print(f"{'call':36} {'http':>4} {'ms':>6} {'valid':>5}  provider / model / source  confidence  notes")
    for r in run.rows:
        notes = r.get("error") or ("; ".join(r.get("warnings") or []) or "")
        print(f"{r['call']:36} {r['http']:>4} {r['latency_ms']:>6} {str(r.get('schema_valid', '-')):>5}  {r.get('provider')}/{r.get('model')}/{r.get('source')}  {r.get('confidence')}  {notes[:110]}")
    if scenes:
        print("\nphoto-only scenes (no text, no hint; 3 samples: no accuracy claim):")
        for r in run.rows:
            if r["call"] in scenes:
                got = (r.get("proposal") or {}).get("category")
                print(f"  {r['call']:28} expected {scenes[r['call']]:14} got {str(got):14} {'MATCH' if got == scenes[r['call']] else 'DIFFERENT'}  sub={(r.get('proposal') or {}).get('subcategory')}  conf={r.get('confidence')}")
    if a.json_out:
        a.json_out.write_text(json.dumps(run.rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
