"""End-to-end HTTP smoke test of a running API (WP11). Stdlib + httpx; synthetic demo data only; prints a pass/fail table and exits non-zero on any failure.

    python scripts/dev/smoke.py --base-url http://localhost:8000/api/v1 [--no-ai] [--scan] [--forwarded-for]

The loop: a new citizen registers -> intake/analyze -> evidence (init, PUT, complete) -> case (the same Idempotency-Key replays the same case) -> fusion -> the department
operator triages (explicit decision) -> work order -> the field worker starts, uploads proof and completes -> flags cross the threshold -> the citizen verifies YES ->
RESOLVED -> analytics counted it. Negative checks: no / forged token (401), another citizen cannot read the case, a missing Idempotency-Key (400), the change-password flow
(old access token refused, new password works), a device registration, a rate-limited route (429 + Retry-After, using a throwaway identifier), and with ``--scan`` an
an EICAR upload that must be refused and a clean upload that must end CLEAN (needs the ``scan`` compose profile and SCAN_ENABLED=true). ``--forwarded-for`` additionally proves the sign-in buckets behind a tunnel (the API must run with
RATE_LIMIT_TRUST_FORWARDED_FOR=true and be reachable only through the proxy). ``--no-ai`` skips the one intake/analyze call (a provider request).

Needs the seeded demo city (accounts ``citizen002..4``, ``operator.<dept>``, ``worker.<dept>``, ``admin``). The demo password is DEMO_PASSWORD (env var, else the development
default). Nothing secret is printed. It leaves one RESOLVED case and one new citizen behind, dismisses the flags it raised and removes its device. It is for a LOCAL or throwaway server: it
registers a user, creates cases, changes a password and deliberately trips the sign-in rate limit, so a non-local --base-url needs --allow-remote.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from typing import Any

import httpx

DOMAIN = "demo.civicconnect.test"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00" + b"civicconnect-smoke-image-bytes" * 8
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
RESULTS: list[tuple[str, bool, str]] = []


class Smoke:
    def __init__(self, base: str, password: str, timeout: float = 60.0) -> None:
        self.base = base.rstrip("/")
        self.origin = self.base.split("/api/")[0] if "/api/" in self.base else self.base
        self.password = password
        self.http = httpx.Client(timeout=timeout)
        self.tokens: dict[str, str] = {}

    # ---------------------------------------------------------------------------------------------- plumbing
    def url(self, path: str) -> str:
        return path if path.startswith("http") else f"{self.base}{path}"

    def h(self, who: str | None = None, idem: str | bool = False, **extra: str) -> dict[str, str]:
        out: dict[str, str] = dict(extra)
        if who:
            out["Authorization"] = f"Bearer {self.tokens[who]}"
        if idem:
            out["Idempotency-Key"] = idem if isinstance(idem, str) else str(uuid.uuid4())
        return out

    def call(self, method: str, path: str, who: str | None = None, idem: str | bool = False, headers: dict[str, str] | None = None, **kw: Any) -> httpx.Response:
        for attempt in range(2):
            r = self.http.request(method, self.url(path), headers={**self.h(who, idem), **(headers or {})}, **kw)
            if r.status_code == 429 and attempt == 0 and not getattr(self, "expect_429", False):    # a shared sign-in bucket: wait it out once
                time.sleep(min(float(r.headers.get("retry-after", "5")), 65.0) + 1.0)
                continue
            return r
        return r

    def login(self, who: str, identifier: str, password: str | None = None) -> httpx.Response:
        r = self.call("POST", "/auth/login", json={"identifier": identifier, "password": password or self.password})
        if r.status_code == 200:
            self.tokens[who] = r.json()["access_token"]
        return r

    def upload(self, who: str, data: bytes, name: str, mime: str = "image/jpeg", purpose: str = "REPORT") -> httpx.Response:
        init = self.call("POST", "/evidence/upload-init", who, True, json={"filename": name, "mime_type": mime, "size_bytes": len(data),
                                                                           "sha256": hashlib.sha256(data).hexdigest(), "purpose": purpose, "source": "SMARTPHONE"})
        if init.status_code != 201:
            return init
        body = init.json()
        put = self.http.put(body["upload_url"], content=data, headers={"Content-Type": mime})
        if put.status_code not in (200, 204):
            return put
        return self.call("POST", f"/evidence/{body['evidence_id']}/complete", who)


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   [{detail}]" if detail and not ok else ""), flush=True)
    return bool(ok)


def _items(body: Any) -> list[dict]:
    """A list endpoint answers a bare array or {"items": [...]}."""
    return body if isinstance(body, list) else body.get("items", [])


def forged_jwt(sub: str, alg_none: bool = False) -> str:
    """A syntactically valid JWT for ``sub`` that the server must refuse: signed with a key it does not have, or not signed at all."""
    def b64(x: bytes) -> str:
        return base64.urlsafe_b64encode(x).rstrip(b"=").decode()
    head = b64(json.dumps({"alg": "none" if alg_none else "HS256", "typ": "JWT"}).encode())
    body = b64(json.dumps({"sub": sub, "role": "city_admin", "exp": int(time.time()) + 3600, "iat": int(time.time())}).encode())
    sig = "" if alg_none else b64(hmac.new(b"not-the-server-key", f"{head}.{body}".encode(), hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"


def err_code(r: httpx.Response) -> str:
    try:
        return str(r.json().get("error", {}).get("code", ""))
    except Exception:                                                            # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------------------------- the scenarios
def run(a: argparse.Namespace) -> int:
    s = Smoke(a.base_url, a.password)
    started = time.time()
    ready = s.http.get(s.url("/health/ready"))
    if not check("API is ready (database, storage, redis)", ready.status_code == 200 and ready.json().get("status") == "ready", f"HTTP {ready.status_code}"):
        return summarize(started)

    # --- accounts
    email = f"smoke.{uuid.uuid4().hex[:10]}@{DOMAIN}"
    new_pw = "Smoke-Test-Pass-9x"
    reg = s.call("POST", "/auth/register", json={"name": "Smoke Test Citizen", "email": email, "password": new_pw})
    check("citizen registers", reg.status_code in (200, 201), f"HTTP {reg.status_code} {err_code(reg)}")
    check("citizen signs in", s.login("c", email, new_pw).status_code == 200)
    me = s.call("GET", "/auth/me", "c")
    check("GET /auth/me returns the citizen", me.status_code == 200 and me.json().get("email") == email)
    for who, ident in (("c2", f"citizen002@{DOMAIN}"), ("c3", f"citizen003@{DOMAIN}"), ("c4", f"citizen004@{DOMAIN}"), ("admin", f"admin@{DOMAIN}")):
        check(f"demo account {who} signs in", s.login(who, ident).status_code == 200)
    if not all(k in s.tokens for k in ("c", "c2", "c3", "c4", "admin")):
        return summarize(started)

    # --- negative: authentication and idempotency
    check("no token -> 401", s.call("GET", "/cases").status_code == 401)
    junk = s.http.get(s.url("/cases"), headers={"Authorization": "Bearer " + "A" * 20 + "." + "B" * 20 + "." + "C" * 20})
    check("malformed token -> 401", junk.status_code == 401)
    uid = s.call("GET", "/auth/me", "c").json().get("id", "x")
    forged = s.http.get(s.url("/cases"), headers={"Authorization": "Bearer " + forged_jwt(uid)})
    check("well-formed token signed with the wrong key -> 401", forged.status_code == 401, f"HTTP {forged.status_code}")
    unsigned = s.http.get(s.url("/cases"), headers={"Authorization": "Bearer " + forged_jwt(uid, alg_none=True)})
    check("unsigned (alg=none) token -> 401", unsigned.status_code == 401, f"HTTP {unsigned.status_code}")
    where = {"latitude": 19.0901, "longitude": 72.8885}
    body = {"description": "Deep pothole near the school gate, a cyclist fell this morning", "category": "roads", "subcategory": "pothole", "location": where, "language": "en"}
    missing = s.call("POST", "/cases", "c", False, json=body)
    check("missing Idempotency-Key -> 400 IDEMPOTENCY_KEY_REQUIRED", missing.status_code == 400 and err_code(missing) == "IDEMPOTENCY_KEY_REQUIRED", f"HTTP {missing.status_code}")

    # --- overview before, intake, evidence, case
    before = s.call("GET", "/analytics/overview", "admin")
    total_before = before.json().get("total_cases") if before.status_code == 200 else None
    if a.no_ai:
        print("  SKIP  intake/analyze (--no-ai)")
    else:
        ia = s.call("POST", "/cases/intake/analyze", "c", json={"text": "There is a big pothole near the school gate on Station Road"})
        check("intake/analyze answers with a proposal", ia.status_code == 200 and "proposal" in ia.json(), f"HTTP {ia.status_code} {err_code(ia)}")
    photo = s.upload("c", JPEG, "smoke.jpg")
    check("evidence upload (init -> PUT -> complete) is READY", photo.status_code == 200 and photo.json().get("status") == "READY", f"HTTP {photo.status_code} {err_code(photo)}")
    if photo.status_code != 200:
        return summarize(started)
    key = str(uuid.uuid4())
    created = s.call("POST", "/cases", "c", key, json={**body, "evidence_ids": [photo.json()["id"]]})
    check("case is created (201)", created.status_code == 201, f"HTTP {created.status_code} {err_code(created)}")
    if created.status_code != 201:
        return summarize(started)
    case = created.json()["case"]
    cid = case["id"]
    replay = s.call("POST", "/cases", "c", key, json={**body, "evidence_ids": [photo.json()["id"]]})
    check("same Idempotency-Key replays the same case", replay.status_code in (200, 201) and replay.json().get("case", {}).get("id") == cid, f"HTTP {replay.status_code}")
    check("another citizen cannot read the case", s.call("GET", f"/cases/{cid}", "c2").status_code in (403, 404))
    check("the reporter can read it", s.call("GET", f"/cases/{cid}", "c").status_code == 200)

    # --- staff: fusion, triage, work order
    dept = s.call("GET", f"/cases/{cid}", "admin").json().get("department_id") or "road_maintenance"
    check("operator signs in", s.login("op", f"operator.{dept}@{DOMAIN}").status_code == 200)
    check("field worker signs in", s.login("fw", f"worker.{dept}@{DOMAIN}").status_code == 200)
    if "op" not in s.tokens or "fw" not in s.tokens:
        return summarize(started)
    fusion = s.call("POST", f"/cases/{cid}/fusion/analyze", "op")
    check("duplicate fusion answers", fusion.status_code == 200 and "recommendation" in fusion.json(), f"HTTP {fusion.status_code} {err_code(fusion)}")
    listed = s.call("GET", "/cases?limit=50", "op")
    check("the operator lists the new case", listed.status_code == 200 and cid in [c["id"] for c in listed.json().get("items", [])], f"HTTP {listed.status_code}")
    triage = s.call("POST", f"/cases/{cid}/triage/decision", "op", True, json={"severity": "HIGH", "priority": "HIGH", "department_id": dept, "sla_hours": 48, "reason": "smoke test triage"})
    check("operator triage decision", triage.status_code == 200, f"HTTP {triage.status_code} {err_code(triage)}")
    wo = s.call("POST", f"/cases/{cid}/work-orders", "op", True, json={"assignee_id": s.call("GET", "/auth/me", "fw").json()["id"], "instructions": "Fill and compact the pothole",
                                                                      "due_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 3 * 86400))})
    check("work order is created for the field worker", wo.status_code == 201, f"HTTP {wo.status_code} {err_code(wo)}")
    if wo.status_code != 201:
        return summarize(started)
    wid = wo.json()["id"]
    check("the worker sees it; a citizen does not", wid in [w["id"] for w in s.call("GET", "/work-orders", "fw").json().get("items", [])] and s.call("GET", f"/work-orders/{wid}", "c").status_code in (403, 404))
    early = s.call("POST", f"/work-orders/{wid}/complete", "fw", True, json={"notes": "done", "resolution_evidence_ids": []})
    check("completing before starting -> 409 INVALID_STATE", early.status_code == 409 and err_code(early) == "INVALID_STATE", f"HTTP {early.status_code} {err_code(early)}")
    check("worker starts the work", s.call("POST", f"/work-orders/{wid}/start", "fw", True).status_code == 200)
    nope = s.call("POST", f"/work-orders/{wid}/complete", "fw", True, json={"notes": "fixed", "resolution_evidence_ids": []})
    check("completing without proof -> 422 RESOLUTION_EVIDENCE_REQUIRED", nope.status_code == 422 and err_code(nope) == "RESOLUTION_EVIDENCE_REQUIRED", f"HTTP {nope.status_code} {err_code(nope)}")
    after = s.upload("fw", JPEG + b"after", "after.jpg", purpose="RESOLUTION")
    done = s.call("POST", f"/work-orders/{wid}/complete", "fw", True, json={"notes": "Pothole filled and compacted", "resolution_evidence_ids": [after.json().get("id")] if after.status_code == 200 else []})
    check("worker completes with proof", done.status_code == 200 and done.json().get("status") == "COMPLETED", f"HTTP {done.status_code} {err_code(done)}")
    st = s.call("GET", f"/cases/{cid}", "c").json().get("status")
    check("case is AWAITING_VERIFICATION (completing does not close it)", st == "AWAITING_VERIFICATION", str(st))

    # --- flags cross the threshold (system setting, default 3), then are dismissed
    th = 3
    sett = s.call("GET", "/admin/settings", "admin")
    if sett.status_code == 200:
        raw = sett.json()
        vals = raw.get("values", raw) if isinstance(raw, dict) else {}
        v = vals.get("flag_review_threshold") if isinstance(vals, dict) else None
        try:
            th = int(v.get("value", 3) if isinstance(v, dict) else v or 3)
        except (TypeError, ValueError):
            th = 3
    flaggers = [w for w in ("c2", "c3", "c4")][:max(1, min(th, 3))]
    flag_ids = []
    for w in flaggers:
        s.call("POST", f"/cases/{cid}/support", w, True)                          # a citizen sees (and may flag) the cases they reported or support
        fr = s.call("POST", f"/cases/{cid}/flags", w, True, json={"kind": "STILL_EXISTS", "comment": "smoke test flag"})
        if fr.status_code == 201:
            flag_ids.append(fr.json()["id"])
    check(f"{len(flaggers)} citizens flagged the case", len(flag_ids) == len(flaggers), f"created {len(flag_ids)}")
    staff = s.call("GET", f"/cases/{cid}", "op").json()
    if th <= 3:
        check(f"open flags reach the threshold ({th}): staff see needs_flag_review", staff.get("open_flag_count") == len(flag_ids) and staff.get("needs_flag_review") is True,
              f"count={staff.get('open_flag_count')} review={staff.get('needs_flag_review')}")
    else:
        print(f"  SKIP  flag threshold is {th} (>3 citizens needed)")
    own = s.call("GET", f"/cases/{cid}", "c")
    check("the reporter's own view never says needs_flag_review", own.status_code == 200 and own.json().get("needs_flag_review") in (False, None) and not own.json().get("open_flag_count"))
    for fid in flag_ids:
        s.call("POST", f"/flags/{fid}/resolve", "op", True, json={"status": "DISMISSED"})

    # --- verification and analytics
    ver = s.call("POST", f"/cases/{cid}/verification", "c", True, json={"result": "YES", "comment": "road is smooth again"})
    check("citizen verifies YES -> RESOLVED", ver.status_code == 201 and ver.json().get("case_status") == "RESOLVED", f"HTTP {ver.status_code} {err_code(ver)}")
    ov = s.call("GET", "/analytics/overview", "admin")
    check("analytics counted the new case", ov.status_code == 200 and total_before is not None and ov.json().get("total_cases") == total_before + 1,
          f"before={total_before} after={ov.json().get('total_cases') if ov.status_code == 200 else ov.status_code}")
    tl = [t["event_type"] for t in s.call("GET", f"/cases/{cid}/timeline?limit=100", "admin").json().get("items", [])]
    check("timeline holds triage, work, verification", {"TRIAGE_DECIDED", "WORK_STARTED", "VERIFICATION_RECORDED"} <= set(tl), ",".join(sorted(set(tl)))[:120])

    # --- device registration
    dev = s.call("POST", "/me/devices", "c", True, json={"platform": "android", "expo_push_token": f"ExponentPushToken[smoke{uuid.uuid4().hex[:12]}]", "device_id": "smoke-device"})
    check("device registration (201)", dev.status_code in (200, 201), f"HTTP {dev.status_code} {err_code(dev)}")
    if dev.status_code in (200, 201):
        did = dev.json().get("id")
        check("the device is listed, then removed", did in [d["id"] for d in _items(s.call("GET", "/me/devices", "c").json())] and s.call("DELETE", f"/me/devices/{did}", "c", True).status_code in (200, 204))

    # --- change password: the old access token dies, the new password works
    old_access = s.tokens["c"]
    changed_pw = "Smoke-Changed-Pass-7y"
    cp = s.call("POST", "/auth/change-password", "c", True, json={"current_password": new_pw, "new_password": changed_pw})
    check("change-password succeeds", cp.status_code == 200, f"HTTP {cp.status_code} {err_code(cp)}")
    time.sleep(1.1)                                                              # `iat` has one-second resolution
    stale = s.http.get(s.url("/auth/me"), headers={"Authorization": f"Bearer {old_access}"})
    check("the access token issued before the change is refused (401)", stale.status_code == 401, f"HTTP {stale.status_code}")
    check("the new password signs in; the old one does not", s.login("c", email, changed_pw).status_code == 200 and s.login("c_old", email, new_pw).status_code == 401)

    # --- rate limit (throwaway identifier: never locks a real account)
    s.expect_429 = True
    ghost = f"ghost.{uuid.uuid4().hex[:8]}@{DOMAIN}"
    codes: list[httpx.Response] = []
    for _ in range(14):                                                           # the windows are fixed minutes: 14 attempts always put 6 in one window (limit 5)
        codes.append(s.call("POST", "/auth/login", json={"identifier": ghost, "password": "wrong-password-1"}))
        if codes[-1].status_code == 429:
            break
    hit = codes[-1] if codes[-1].status_code == 429 else None
    check("repeated failed sign-ins are rate limited (429 + Retry-After)", hit is not None and "retry-after" in hit.headers and err_code(hit) == "RATE_LIMITED",
          ",".join(str(r.status_code) for r in codes))
    s.expect_429 = False

    # --- optional: malware scan (the API must run with SCAN_ENABLED=true and clamd up; every accepted type is also sniffed by magic bytes, so plain EICAR never reaches clamd here:
    #     the real-clamd EICAR detection is backend/tests/test_malware_scan.py::test_eicar_against_a_real_clamd, which this profile makes runnable)
    if a.scan:
        bad = s.upload("c", EICAR, "eicar.jpg", mime="image/jpeg")
        check("an EICAR file posing as a JPEG is refused by the type check (EVIDENCE_REJECTED; NOT a clamd test, see the comment above)", bad.status_code == 422 and err_code(bad) == "EVIDENCE_REJECTED", f"HTTP {bad.status_code} {err_code(bad)}")
        clean = s.upload("c", JPEG + b"scan", "clean.jpg")
        status = clean.json().get("scan_status") if clean.status_code == 200 else None
        for _ in range(12):                                                       # the scan worker runs every few seconds
            if status == "CLEAN" or clean.status_code != 200:
                break
            time.sleep(5)
            status = s.call("GET", f"/evidence/{clean.json()['id']}", "c").json().get("scan_status")
        check("a clean upload is scanned by clamd and ends CLEAN", status == "CLEAN", f"scan_status={status}")
    else:
        print("  SKIP  malware scan (--scan not given; needs the scan compose profile and SCAN_ENABLED=true)")

    # --- optional: behind a tunnel
    if a.forwarded_for:
        s.expect_429 = True
        ip_a, ip_b = f"198.51.100.{int(time.time()) % 200 + 1}", f"203.0.113.{int(time.time()) % 200 + 1}"
        la: list[int] = []
        for i in range(25):                                                       # fixed one-minute windows: 25 attempts always put 11 in one window (limit 10)
            la.append(s.call("POST", "/auth/login", headers={"X-Forwarded-For": ip_a}, json={"identifier": f"x{i}.{uuid.uuid4().hex[:6]}@{DOMAIN}", "password": "wrong-password-1"}).status_code)
            if la[-1] == 429:
                break
        lb = s.call("POST", "/auth/login", headers={"X-Forwarded-For": ip_b}, json={"identifier": f"y.{uuid.uuid4().hex[:6]}@{DOMAIN}", "password": "wrong-password-1"}).status_code
        lf = s.call("POST", "/auth/login", headers={"X-Forwarded-For": f"7.7.7.{int(time.time()) % 200 + 1}, {ip_a}"}, json={"identifier": f"z.{uuid.uuid4().hex[:6]}@{DOMAIN}", "password": "wrong-password-1"}).status_code
        check("two client IPs get separate sign-in buckets", la[-1] == 429 and lb == 401, f"A={la[-3:]} B={lb}")
        check("a forged leftmost X-Forwarded-For does not buy a fresh bucket", lf == 429, f"HTTP {lf}")
        s.expect_429 = False
    else:
        print("  SKIP  X-Forwarded-For buckets (--forwarded-for not given; run it behind the tunnel)")
    return summarize(started)


def summarize(started: float) -> int:
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)} passed, {len(failed)} failed, in {time.time() - started:.1f} s")
    for name, _, detail in failed:
        print(f"  FAILED: {name}  [{detail}]")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://localhost:8000/api/v1")
    ap.add_argument("--password", default=os.environ.get("DEMO_PASSWORD", "civicconnect-demo"), help="demo account password (default: env DEMO_PASSWORD or the development default)")
    ap.add_argument("--no-ai", action="store_true", help="skip the intake/analyze call (one provider request)")
    ap.add_argument("--scan", action="store_true", help="also upload an EICAR file (the API must run with the scan profile)")
    ap.add_argument("--allow-remote", action="store_true", help="allow a --base-url whose host is not localhost / 127.0.0.1 / a private address (it writes data and trips rate limits)")
    ap.add_argument("--forwarded-for", action="store_true", help="also check the per-IP sign-in buckets behind a proxy (RATE_LIMIT_TRUST_FORWARDED_FOR=true)")
    a = ap.parse_args(argv)
    host = httpx.URL(a.base_url).host
    if not a.allow_remote and not _is_local(host):
        print(f"REFUSED: {host} is not a local or private address; this test registers users, creates cases and trips rate limits. Pass --allow-remote to run it anyway.", file=sys.stderr)
        return 2
    return step_main(a)


def _is_local(host: str) -> bool:
    import ipaddress
    if host in ("localhost", "host.docker.internal"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def step_main(a: argparse.Namespace) -> int:
    try:
        return run(a)
    except httpx.HTTPError as e:
        print(f"FAIL  cannot talk to {a.base_url}: {type(e).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
