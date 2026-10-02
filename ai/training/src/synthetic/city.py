"""Seeded SYNTHETIC demo city (system design §58): wards, departments, users, 500+ Civic Cases with multilingual reports,
duplicate groups, recurring problems, hotspots, SLA violations, resolved / reopened cases, active incidents — plus the planted
GROUND TRUTH for each, so deterministic analytics and AI-2/AI-3/AI-5 logic can be checked against known answers.

Everything is fictional and labelled synthetic: ids are ``DEMO``-prefixed, names say "Synthetic", every record carries
``"synthetic": true``. Coordinates are fictional placements around the synthetic city centre (see ``frames.CITY_CENTER``).
Entities follow design §34; case states follow the §35 state machine; priority/SLA come from the deterministic §36 rules in
``ai.inference`` (never from a model).

Nothing here claims real-world behaviour: distributions, durations and reopen rates are chosen to make dashboards meaningful.
"""
from __future__ import annotations

import math
import random
import uuid
from datetime import datetime, timedelta, timezone

from ai.inference.config import load_taxonomy
from ai.inference.schemas import TriageRequest
from ai.inference.triage.service import TriageService

from . import frames as F
from .generator import FAMILIES, offset_point, place_coords, render_report

CITY_VERSION = "synthetic-city/1.0"
NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)
WINDOW_DAYS = 240
NS = uuid.UUID("c1c1c1c1-0000-4000-8000-00000000d3a0")

STATES = ["SUBMITTED", "AI_PROCESSING", "NEEDS_REVIEW", "ASSIGNED", "WORK_ORDER_CREATED", "IN_PROGRESS", "RESOLUTION_SUBMITTED", "AWAITING_VERIFICATION", "VERIFIED", "RESOLVED"]
LEGAL = {"SUBMITTED": {"AI_PROCESSING"}, "AI_PROCESSING": {"NEEDS_REVIEW"}, "NEEDS_REVIEW": {"ASSIGNED", "REJECTED"}, "ASSIGNED": {"WORK_ORDER_CREATED"},
         "WORK_ORDER_CREATED": {"IN_PROGRESS"}, "IN_PROGRESS": {"RESOLUTION_SUBMITTED"}, "RESOLUTION_SUBMITTED": {"AWAITING_VERIFICATION"},
         "AWAITING_VERIFICATION": {"VERIFIED", "REOPENED"}, "VERIFIED": {"RESOLVED"}, "REOPENED": {"WORK_ORDER_CREATED"}, "RESOLVED": set(), "REJECTED": set()}
TERMINAL = {"RESOLVED", "REJECTED"}
CATEGORY_WEIGHTS = {"roads": 22, "sanitation": 22, "water_supply": 16, "drainage_sewerage": 10, "street_lighting": 12, "parks_trees": 5, "public_health": 5, "traffic_encroachment": 6, "other": 2}
RECURRING_SUBS = ["pipe_leakage", "pothole", "blocked_drain", "light_not_working", "garbage_overflow", "sewage_overflow", "missing_manhole_cover", "flickering_light", "low_water_pressure", "damaged_footpath", "road_cave_in", "mosquito_breeding"]
LANG_WEIGHTS = {"en": 40, "hi": 25, "mr": 15, "hl": 20}
SOURCE_TYPES = ["SMARTPHONE"] * 70 + ["VOICE"] * 18 + ["TABLET"] * 4 + ["IMPORT"] * 3 + ["FIELD_WORKER"] * 5
WARD_NAMES = ["Shivaji Nagar", "Gandhi Chowk", "Sai Colony", "Station Road", "Laxmi Market", "Nehru Park", "Tilak Road", "Krishna Heights", "Old Bazaar", "Lake View"]
WARD_LAT_STEP, WARD_LON_STEP = 0.018, 0.012


def uid(kind: str, key) -> str:
    return str(uuid.uuid5(NS, f"{kind}:{key}"))


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hav_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


# --------------------------------------------------------------------------------------------- static entities
def build_wards() -> list[dict]:
    lat0, lon0 = F.CITY_CENTER
    wards = []
    for i, name in enumerate(WARD_NAMES):
        row, col = divmod(i, 5)
        s, w = lat0 - 0.003 + row * WARD_LAT_STEP, lon0 - 0.006 + col * WARD_LON_STEP
        n, e = s + WARD_LAT_STEP, w + WARD_LON_STEP
        wards.append({"id": uid("ward", i + 1), "label": f"W{i + 1:02d}", "name": f"Synthetic Ward {i + 1:02d} — {name}", "municipality_id": uid("municipality", 1),
                      "centroid": {"latitude": round((s + n) / 2, 6), "longitude": round((w + e) / 2, 6)},
                      "boundary": {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}, "bbox": [s, w, n, e], "synthetic": True})
    return wards


def build_departments() -> list[dict]:
    t = load_taxonomy()
    return [{"id": d.id, "code": d.code, "name": d.label["en"], "name_i18n": dict(d.label), "category_coverage": list(d.category_ids), "synthetic": True} for d in t.departments.values()]


def build_users(rng: random.Random, departments: list[dict], wards: list[dict]) -> list[dict]:
    users = []
    for i in range(60):
        lang = rng.choices(list(LANG_WEIGHTS), weights=list(LANG_WEIGHTS.values()))[0]
        users.append({"id": uid("user", f"citizen{i}"), "name": f"Synthetic Citizen {i + 1:03d}", "role": "CITIZEN", "preferred_language": F.LANG_TAG[lang], "synthetic": True})
    for d in departments:
        users.append({"id": uid("user", f"op-{d['id']}"), "name": f"Synthetic Operator — {d['name']}", "role": "DEPARTMENT_OPERATOR", "department_id": d["id"], "preferred_language": "en", "synthetic": True})
        users.append({"id": uid("user", f"mgr-{d['id']}"), "name": f"Synthetic Manager — {d['name']}", "role": "DEPARTMENT_MANAGER", "department_id": d["id"], "preferred_language": "en", "synthetic": True})
    for w in wards:
        users.append({"id": uid("user", f"wo-{w['label']}"), "name": f"Synthetic Ward Officer {w['label']}", "role": "WARD_OFFICER", "ward_id": w["id"], "preferred_language": "mr", "synthetic": True})
    for i in range(8):
        users.append({"id": uid("user", f"fw{i}"), "name": f"Synthetic Field Worker {i + 1:02d}", "role": "FIELD_WORKER", "department_id": departments[i % len(departments)]["id"], "preferred_language": "hi", "synthetic": True})
    users.append({"id": uid("user", "admin"), "name": "Synthetic City Administrator", "role": "CITY_ADMINISTRATOR", "preferred_language": "en", "synthetic": True})
    users.append({"id": uid("user", "overlooker"), "name": "Synthetic Overlooker", "role": "OVERLOOKER", "preferred_language": "en", "synthetic": True})
    return users


def ward_of(wards: list[dict], lat: float, lon: float) -> dict:
    best = min(wards, key=lambda w: hav_m((lat, lon), (w["centroid"]["latitude"], w["centroid"]["longitude"])))
    for w in wards:
        s, west, n, e = w["bbox"]
        if s <= lat <= n and west <= lon <= e:
            return w
    return best


def place_point(rng: random.Random, wards: list[dict]) -> tuple[float, float, int | None, dict]:
    """A location: 70% near one of the named PLACES (so school/hospital/market tags occur), else uniform in a random ward."""
    if rng.random() < 0.7:
        pi = rng.randrange(len(F.PLACES))
        lat, lon = place_coords(pi)
        lat, lon = offset_point(lat, lon, rng.uniform(0, 45), rng.uniform(0, 2 * math.pi))
        return lat, lon, pi, ward_of(wards, lat, lon)
    w = rng.choice(wards)
    s, west, n, e = w["bbox"]
    return round(rng.uniform(s, n), 6), round(rng.uniform(west, e), 6), None, w


# --------------------------------------------------------------------------------------------- builder
class CityBuilder:
    def __init__(self, seed: int = 20261001, n_cases: int = 560):
        self.seed, self.n_target = seed, n_cases
        self.rng = random.Random(f"{seed}:city")
        self.t = load_taxonomy()
        self.triage = TriageService(None, self.t)
        self.wards, self.departments = build_wards(), build_departments()
        self.users = build_users(random.Random(f"{seed}:users"), self.departments, self.wards)
        self.citizens = [u for u in self.users if u["role"] == "CITIZEN"]
        self.workers = [u for u in self.users if u["role"] == "FIELD_WORKER"]
        self.cases: list[dict] = []
        self.signals: list[dict] = []
        self.relations: list[dict] = []
        self.events: list[dict] = []
        self.work_orders: list[dict] = []
        self.verifications: list[dict] = []
        self.incidents: list[dict] = []
        self.truth: dict = {"duplicate_groups_merged": [], "possible_duplicate_pairs": [], "near_distinct_pairs": [], "recurring_sites": [], "hotspots": [], "incident_cases": {}}
        self._n = 0
        self._site_counts: dict[tuple, int] = {}

    # ---- helpers
    def _random_sub(self) -> str:
        """Subcategory drawn by category weight; ``other`` (~2%) is the vague/off-topic class ``unclassified``."""
        cat = self.rng.choices(list(CATEGORY_WEIGHTS), weights=list(CATEGORY_WEIGHTS.values()))[0]
        if cat == "other":
            return "unclassified"
        return self.rng.choice([s for s in self.t.subcategories if s != "unclassified" and self.t.subcategories[s].category_id == cat])

    def _when(self, lo_days: float, hi_days: float) -> datetime:
        """created_at between ``lo_days`` and ``hi_days`` days before NOW, biased toward working hours."""
        d = self.rng.uniform(hi_days, lo_days) if hi_days < lo_days else self.rng.uniform(lo_days, hi_days)
        base = NOW - timedelta(days=d)
        hour = self.rng.choices(range(24), weights=[1, 1, 1, 1, 1, 2, 4, 7, 9, 9, 8, 7, 6, 6, 7, 8, 8, 7, 6, 5, 4, 3, 2, 1])[0]
        return base.replace(hour=hour, minute=self.rng.randrange(60), second=self.rng.randrange(60), microsecond=0)

    def _report(self, sub: str, place_idx: int | None, lang: str | None = None, fam: int | None = None) -> dict:
        lang = lang or self.rng.choices(list(LANG_WEIGHTS), weights=list(LANG_WEIGHTS.values()))[0]
        fam = self.rng.randrange(F.N_FAMILIES) if fam is None else fam
        place = F.PLACES[place_idx] if place_idx is not None else None
        r = render_report(sub, lang, fam, place, self.rng, split_famidx_pool=list(range(F.N_FAMILIES)))
        r["lang_code"], r["family_id"], r["family_index"] = lang, f"{sub}:{lang}:{fam}", fam
        return r

    def _signal(self, case_id: str, rep: dict, when: datetime, reporter: dict | None = None, lat=None, lon=None, primary: bool = True) -> dict:
        reporter = reporter or self.rng.choice(self.citizens)
        sig = {"id": uid("signal", len(self.signals)), "case_id": case_id, "reporter_id": reporter["id"], "original_text": rep["text"], "original_language": rep["language"],
               "source_type": self.rng.choice(SOURCE_TYPES), "created_at": iso(when), "is_primary": primary, "code_mixed": rep["code_mixed"],
               "family_id": rep["family_id"], "text_split_pool": {0: "train", 1: "train", 2: "train", 3: "val", 4: "test"}[rep["family_index"]] if rep["family_index"] in (0, 1, 2, 3, 4) else "train",
               "latitude": lat, "longitude": lon, "synthetic": True}
        self.signals.append(sig)
        return sig

    def add_case(self, sub: str, when: datetime, lat: float, lon: float, place_idx: int | None, *, recurrence_count: int = 0, incident_id: str | None = None,
                 scenario: str = "filler", lang: str | None = None, fam: int | None = None, force_final: str | None = None, force_reopen: bool | None = None,
                 force_stall: bool | None = None) -> dict:
        self._n += 1
        s = self.t.subcategories[sub]
        rep = self._report(sub, place_idx, lang, fam)
        ward = ward_of(self.wards, lat, lon)
        tags = list(rep["location_tags"])
        support = int(min(25, self.rng.expovariate(1 / 3.0)))
        tri = self.triage.analyze(TriageRequest(category=s.category_id, subcategory=sub, support_count=support, case_age_hours=0, recurrence_count=recurrence_count,
                                                location_tags=tags, incident_active=incident_id is not None))
        r = tri.recommendation
        cid = uid("case", self._n)
        title = f"{s.label['en']}" + (f" near {F.PLACES[place_idx][0]}" if place_idx is not None else f" in {ward['label']}")
        case = {"id": cid, "public_case_id": f"DEMO-2026-{self._n:06d}", "title": title, "canonical_description": FAMILIES[sub]["en"][rep["family_index"]],
                "category": s.category_id, "subcategory": sub, "severity": r.severity, "priority": r.priority, "priority_score": tri.priority_score, "sla_class": r.sla_class,
                "sla_hours": r.sla_hours, "status": "SUBMITTED", "location": {"latitude": lat, "longitude": lon}, "location_tags": tags, "ward_id": ward["id"],
                "department_id": s.department_id, "created_at": iso(when), "updated_at": iso(when), "closed_at": None, "reopen_count": 0, "support_count": support,
                "recurrence_count": recurrence_count, "incident_id": incident_id, "language": rep["language"], "scenario": scenario, "synthetic": True}
        self.cases.append(case)
        primary = self._signal(cid, rep, when, lat=lat, lon=lon)
        case["primary_signal_id"] = primary["id"]
        self._lifecycle(case, when, force_final, force_reopen, force_stall)
        return case

    # ---- lifecycle following the §35 state machine
    def _lifecycle(self, case: dict, t0: datetime, force_final: str | None, force_reopen: bool | None, force_stall: bool | None = None) -> None:
        rng, sla = self.rng, case["sla_hours"]
        speed = rng.lognormvariate(0, 0.5)            # per-case speed: some cases are simply slow
        events: list[tuple[str, datetime, str]] = [("SUBMITTED", t0, "SYSTEM")]

        def push(state: str, dt: timedelta, actor: str) -> datetime:
            at = events[-1][1] + dt * speed
            events.append((state, at, actor))
            return at
        push("AI_PROCESSING", timedelta(seconds=rng.randint(5, 40)), "SYSTEM")
        push("NEEDS_REVIEW", timedelta(seconds=rng.randint(20, 120)), "SYSTEM")
        reject = force_final == "REJECTED" or (force_final is None and rng.random() < 0.03)
        reopen = False
        if reject:
            push("REJECTED", timedelta(hours=rng.uniform(1, 30)), "DEPARTMENT_OPERATOR")
        else:
            push("ASSIGNED", timedelta(hours=rng.uniform(0.3, sla * 0.12 + 1)), "DEPARTMENT_OPERATOR")
            push("WORK_ORDER_CREATED", timedelta(minutes=rng.uniform(2, 120)), "DEPARTMENT_OPERATOR")
            push("IN_PROGRESS", timedelta(hours=rng.uniform(0.5, sla * 0.25 + 2)), "FIELD_WORKER")
            push("RESOLUTION_SUBMITTED", timedelta(hours=rng.uniform(1, sla * rng.lognormvariate(-0.2, 0.55))), "FIELD_WORKER")
            push("AWAITING_VERIFICATION", timedelta(minutes=rng.uniform(1, 30)), "SYSTEM")
            reopen = force_reopen if force_reopen is not None else rng.random() < 0.09
            if reopen:
                push("REOPENED", timedelta(hours=rng.uniform(6, 96)), "CITIZEN")
                push("WORK_ORDER_CREATED", timedelta(hours=rng.uniform(1, 12)), "DEPARTMENT_OPERATOR")
                push("IN_PROGRESS", timedelta(hours=rng.uniform(1, sla * 0.2 + 2)), "FIELD_WORKER")
                push("RESOLUTION_SUBMITTED", timedelta(hours=rng.uniform(2, sla * 0.5 + 2)), "FIELD_WORKER")
                push("AWAITING_VERIFICATION", timedelta(minutes=rng.uniform(1, 30)), "SYSTEM")
            push("VERIFIED", timedelta(hours=rng.uniform(2, 120)), "CITIZEN")
            push("RESOLVED", timedelta(seconds=rng.randint(1, 60)), "SYSTEM")
        stall = force_stall if force_stall is not None else (not reject and rng.random() < 0.26)
        if reopen and force_stall is None and rng.random() < 0.4:      # currently in the REOPENED state (waiting for a new work order)
            events = events[: next(i for i, e in enumerate(events) if e[0] == "REOPENED") + 1]
        elif stall:                                     # backlog: the case stops at an intermediate state (not closed)
            cut = rng.choices(["NEEDS_REVIEW", "ASSIGNED", "WORK_ORDER_CREATED", "IN_PROGRESS", "AWAITING_VERIFICATION"], weights=[3, 4, 3, 4, 3])[0]
            idx = max(i for i, e in enumerate(events) if e[0] == cut) if cut != "AWAITING_VERIFICATION" else max(i for i, e in enumerate(events) if e[0] == "AWAITING_VERIFICATION")
            events = events[: idx + 1]
        kept = [e for e in events if e[1] <= NOW]
        for (st, at, actor), prev in zip(kept, [None] + kept[:-1], strict=False):
            ev = {"id": f"DEMO-EV-{len(self.events) + 1:06d}", "case_id": case["id"], "from_state": prev[0] if prev else None, "to_state": st, "at": iso(at), "actor_role": actor,
                  "synthetic": True}
            if st == "REJECTED":
                ev["reason"] = "synthetic rejection: out of scope"
            self.events.append(ev)
        last_state, last_at, _ = kept[-1]
        case["status"], case["updated_at"] = last_state, iso(last_at)
        case["reopen_count"] = sum(1 for e in kept if e[0] == "REOPENED")
        case["closed_at"] = iso(last_at) if last_state in TERMINAL else None
        deadline = t0 + timedelta(hours=sla)
        case["sla_deadline"] = iso(deadline)
        res_at = next((at for st, at, _ in kept if st == "RESOLUTION_SUBMITTED"), None)
        case["sla_breached"] = bool((res_at and res_at > deadline) or (last_state not in TERMINAL and last_state != "AWAITING_VERIFICATION" and NOW > deadline and not res_at))
        wo_at = next((at for st, at, _ in kept if st == "WORK_ORDER_CREATED"), None)
        if wo_at:
            worker = rng.choice([w for w in self.workers if w["department_id"] == case["department_id"]] or self.workers)
            done = next((at for st, at, _ in reversed(kept) if st == "RESOLUTION_SUBMITTED"), None)
            self.work_orders.append({"id": uid("wo", len(self.work_orders)), "case_id": case["id"], "department_id": case["department_id"], "assigned_worker_id": worker["id"],
                                     "priority": case["priority"], "deadline": iso(deadline), "status": "COMPLETED" if done else "IN_PROGRESS" if any(s == "IN_PROGRESS" for s, _, _ in kept) else "ASSIGNED",
                                     "created_at": iso(wo_at), "completed_at": iso(done) if done else None, "synthetic": True})
        reporter_id = next(sg["reporter_id"] for sg in self.signals if sg["id"] == case["primary_signal_id"])
        for st, at, _ in kept:
            if st in ("VERIFIED", "REOPENED"):
                self.verifications.append({"id": uid("verif", len(self.verifications)), "case_id": case["id"], "citizen_id": reporter_id,
                                           "result": "CONFIRMED_FIXED" if st == "VERIFIED" else "NOT_FIXED", "evidence_id": None, "created_at": iso(at), "synthetic": True})

    # ---- planted structures
    def plant_merged_duplicates(self, n_groups: int = 25) -> None:
        for _ in range(n_groups):
            sub = self._random_sub()
            if sub == "unclassified":
                sub = "pothole"
            lat, lon, pi, _ = place_point(self.rng, self.wards)
            when = self._when(150, 3)
            case = self.add_case(sub, when, lat, lon, pi, scenario="merged_duplicates")
            group = [case["primary_signal_id"]]
            for _ in range(self.rng.randint(1, 3)):
                lang = self.rng.choice(list(LANG_WEIGHTS))
                la, lo = offset_point(lat, lon, abs(self.rng.gauss(0, 18)), self.rng.uniform(0, 2 * math.pi))
                rep = self._report(sub, pi if self.rng.random() < 0.8 else None, lang)
                sig = self._signal(case["id"], rep, when + timedelta(hours=self.rng.uniform(0.2, 72)), lat=la, lon=lo, primary=False)
                group.append(sig["id"])
            self.truth["duplicate_groups_merged"].append({"case_id": case["id"], "signal_ids": group, "subcategory": sub})

    def plant_possible_duplicates(self, n_groups: int = 18, n_negatives: int = 18) -> None:
        for _ in range(n_groups):
            sub = self._random_sub()
            if sub == "unclassified":
                sub = "garbage_overflow"
            lat, lon, pi, _ = place_point(self.rng, self.wards)
            when = self._when(100, 6)
            a = self.add_case(sub, when, lat, lon, pi, scenario="possible_duplicate")
            for _k in range(self.rng.randint(1, 2)):
                la, lo = offset_point(lat, lon, abs(self.rng.gauss(0, 20)), self.rng.uniform(0, 2 * math.pi))
                b = self.add_case(sub, when + timedelta(hours=self.rng.uniform(0.5, 120)), la, lo, pi if self.rng.random() < 0.8 else None, scenario="possible_duplicate",
                                  lang=self.rng.choice(list(LANG_WEIGHTS)))
                d = hav_m((lat, lon), (la, lo))
                self.relations.append({"id": uid("rel", len(self.relations)), "case_a": a["id"], "case_b": b["id"], "relation_type": "POSSIBLE_DUPLICATE",
                                       "similarity_score": round(max(0.55, 0.95 - d / 200), 3), "created_at": b["created_at"], "synthetic": True})
                self.truth["possible_duplicate_pairs"].append({"case_a": a["id"], "case_b": b["id"], "distance_m": round(d, 1)})
        for _ in range(n_negatives):
            sub = self._random_sub()
            if sub == "unclassified":
                sub = "pothole"
            lat, lon, pi, _ = place_point(self.rng, self.wards)
            when = self._when(100, 6)
            a = self.add_case(sub, when, lat, lon, pi, scenario="near_distinct")
            la, lo = offset_point(lat, lon, self.rng.uniform(70, 150), self.rng.uniform(0, 2 * math.pi))
            b = self.add_case(sub, when + timedelta(hours=self.rng.uniform(1, 200)), la, lo, None, scenario="near_distinct")
            self.truth["near_distinct_pairs"].append({"case_a": a["id"], "case_b": b["id"], "distance_m": round(hav_m((lat, lon), (la, lo)), 1)})

    def plant_recurring(self, n_sites: int = 12) -> None:
        for s in range(n_sites):
            sub = RECURRING_SUBS[s % len(RECURRING_SUBS)]
            lat0, lon0, pi, _ = place_point(self.rng, self.wards)
            k = self.rng.randint(4, 6)
            offs = sorted(self.rng.uniform(15, 235) for _ in range(k))
            ids = []
            for j, days_ago in enumerate(reversed(offs)):
                la, lo = offset_point(lat0, lon0, abs(self.rng.gauss(0, 55)), self.rng.uniform(0, 2 * math.pi))
                case = self.add_case(sub, self._when(days_ago + 1, days_ago), la, lo, pi, recurrence_count=j, scenario="recurring_site", force_reopen=(j == 2),
                                     force_stall=False if j < 3 else None)
                ids.append(case["id"])
            self.truth["recurring_sites"].append({"site_id": f"RS{s + 1:02d}", "subcategory": sub, "center": {"latitude": lat0, "longitude": lon0}, "radius_m": 150, "case_ids": ids,
                                                  "window_days": 240})

    def plant_hotspots(self) -> None:
        specs = [("garbage_overflow", 3), ("pipe_leakage", 6), ("mosquito_breeding", 1)]
        for h, (sub, ward_i) in enumerate(specs):
            w = self.wards[ward_i]
            lat0, lon0 = w["centroid"]["latitude"], w["centroid"]["longitude"]
            ids = []
            for _ in range(self.rng.randint(13, 18)):
                la, lo = offset_point(lat0, lon0, abs(self.rng.gauss(0, 140)), self.rng.uniform(0, 2 * math.pi))
                ids.append(self.add_case(sub, self._when(13, 0.2), la, lo, None, scenario="emerging_hotspot")["id"])
            for _ in range(2):    # thin baseline in the same area earlier: the surge must stand out
                la, lo = offset_point(lat0, lon0, abs(self.rng.gauss(0, 140)), self.rng.uniform(0, 2 * math.pi))
                self.add_case(sub, self._when(200, 30), la, lo, None, scenario="hotspot_baseline")
            self.truth["hotspots"].append({"hotspot_id": f"HS{h + 1:02d}", "subcategory": sub, "ward_id": w["id"], "center": {"latitude": lat0, "longitude": lon0}, "recent_days": 14, "case_ids": ids})

    def plant_incidents(self) -> None:
        specs = [("Synthetic water main failure — W03", ["pipe_leakage", "no_water_supply", "low_water_pressure"], 2, "ACTIVE", 6, 380),
                 ("Synthetic waterlogging after heavy rain — W07", ["blocked_drain", "sewage_overflow", "missing_manhole_cover"], 6, "ACTIVE", 4, 450),
                 ("Synthetic street-light outage — W09", ["light_not_working", "flickering_light", "exposed_live_wire"], 8, "ACTIVE", 2, 350),
                 ("Synthetic road cave-in closure — W05 (ended)", ["road_cave_in", "pothole", "damaged_footpath"], 4, "ENDED", 70, 300),
                 ("Synthetic garbage strike — W02 (ended)", ["garbage_overflow", "missed_garbage_collection", "illegal_dumping"], 1, "ENDED", 110, 400)]
        for i, (title, subs, wi, status, started_days, radius) in enumerate(specs):
            w = self.wards[wi]
            lat0, lon0 = w["centroid"]["latitude"], w["centroid"]["longitude"]
            iid = uid("incident", i + 1)
            started = NOW - timedelta(days=started_days)
            ended = None if status == "ACTIVE" else started + timedelta(days=9)
            ring = [[round(lon0 + radius / (111_320 * math.cos(math.radians(lat0))) * math.cos(a), 6), round(lat0 + radius / 111_320 * math.sin(a), 6)]
                    for a in [k * math.pi / 8 for k in range(17)]]
            self.incidents.append({"id": iid, "title": title, "description": f"{title}. SYNTHETIC incident for demo dashboards.", "geometry": {"type": "Polygon", "coordinates": [ring]},
                                   "center": {"latitude": lat0, "longitude": lon0}, "radius_m": radius, "status": status, "created_by": uid("user", "admin"),
                                   "started_at": iso(started), "ended_at": iso(ended) if ended else None, "ward_id": w["id"], "synthetic": True})
            ids = []
            for _ in range(self.rng.randint(8, 12)):
                la, lo = offset_point(lat0, lon0, self.rng.uniform(0, radius * 0.9), self.rng.uniform(0, 2 * math.pi))
                when = started + timedelta(hours=self.rng.uniform(1, 24 * (9 if ended else started_days)))
                when = min(when, NOW - timedelta(hours=1))
                ids.append(self.add_case(self.rng.choice(subs), when, la, lo, None, incident_id=iid, scenario="incident")["id"])
            self.truth["incident_cases"][iid] = ids

    def fill(self) -> None:
        while len(self.cases) < self.n_target:
            sub = self._random_sub()
            for _ in range(12):       # keep filler from forming accidental recurring sites (the planted ones must be the ground truth)
                lat, lon, pi, _ = place_point(self.rng, self.wards)
                if pi is None or self._site_counts.get((sub, pi), 0) < 2:
                    break
            else:
                lat, lon, pi = *place_point(self.rng, self.wards)[:2], None
            if pi is not None:
                self._site_counts[(sub, pi)] = self._site_counts.get((sub, pi), 0) + 1
            # mild growth toward the present
            days = WINDOW_DAYS * (1 - math.sqrt(self.rng.random()))
            self.add_case(sub, self._when(days + 0.5, days), lat, lon, pi)

    def build(self) -> dict:
        self.plant_merged_duplicates()
        self.plant_possible_duplicates()
        self.plant_recurring()
        self.plant_hotspots()
        self.plant_incidents()
        self.fill()
        order = {c["id"]: i for i, c in enumerate(sorted(self.cases, key=lambda c: c["created_at"]))}
        self.cases.sort(key=lambda c: c["created_at"])
        for i, c in enumerate(self.cases):
            c["seq"] = i + 1
            c["public_case_id"] = f"DEMO-2026-{i + 1:06d}"          # numbered in creation order, like a real register
        self.signals.sort(key=lambda s: (order[s["case_id"]], s["created_at"]))
        return {"wards": self.wards, "departments": self.departments, "users": self.users, "cases": self.cases, "report_signals": self.signals, "case_relations": self.relations,
                "status_events": self.events, "work_orders": self.work_orders, "verifications": self.verifications, "incidents": self.incidents, "ground_truth": self.truth}


def build_city(seed: int = 20261001, n_cases: int = 560) -> dict:
    return CityBuilder(seed, n_cases).build()
