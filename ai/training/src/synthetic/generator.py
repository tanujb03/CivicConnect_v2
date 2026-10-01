"""Deterministic SYNTHETIC multilingual civic-report generator.

Everything produced here is synthetic and must be labelled as such. Template
family = one hand-written core phrase (index 0-4 per subcategory x language).
Held-out evaluation splits by family index *and* by place pool so core phrases
and place names in the test set never appear in training.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

from ai.inference.config import Taxonomy, load_taxonomy

from . import frames as F
from .lexicon_lighting_parks_health_traffic import FAMILIES as _L3
from .lexicon_roads_water import FAMILIES as _L1
from .lexicon_sanitation_drainage import FAMILIES as _L2
from .noise import add_spelling_noise, add_surface_noise

GENERATOR_VERSION = "synthetic-civic/1.0"
FAMILIES = {**_L1, **_L2, **_L3}
EPOCH = datetime(2026, 9, 1, tzinfo=timezone.utc)
SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def split_of_index(idx: int, test_fold: int) -> str:
    """Family/place index -> split. Rotating ``test_fold`` gives family-grouped k-fold."""
    if idx % F.N_FAMILIES == test_fold % F.N_FAMILIES:
        return "test"
    if idx % F.N_FAMILIES == (test_fold - 1) % F.N_FAMILIES:
        return "val"
    return "train"


def places_for(split: str, test_fold: int):
    return [(i, p) for i, p in enumerate(F.PLACES) if split_of_index(i, test_fold) == split]


def family_indices(split: str, test_fold: int) -> list[int]:
    return [i for i in range(F.N_FAMILIES) if split_of_index(i, test_fold) == split]


def place_coords(place_idx: int) -> tuple[float, float]:
    """Deterministic fictional coordinates on a ~6x4 km grid around the synthetic city centre."""
    lat0, lon0 = F.CITY_CENTER
    row, col = divmod(place_idx, 5)
    return lat0 + row * 0.012, lon0 + col * 0.012


def offset_point(lat: float, lon: float, dist_m: float, bearing_rad: float) -> tuple[float, float]:
    dlat = dist_m * math.cos(bearing_rad) / 111_320.0
    dlon = dist_m * math.sin(bearing_rad) / (111_320.0 * math.cos(math.radians(lat)))
    return round(lat + dlat, 6), round(lon + dlon, 6)


def _gold_severity(t: Taxonomy, subcategory: str, tags: list[str]) -> str:
    base = t.subcategories[subcategory].base_severity
    rank = t.severity_rank[base] + (1 if ("school" in tags or "hospital" in tags) else 0)
    return t.severity_by_rank(rank)


def render_report(subcategory: str, lang: str, fam_idx: int, place: tuple[str, str, list[str]] | None,
                  rng: random.Random, *, split_famidx_pool: list[int], allow_codemix: bool = True,
                  noise: bool | None = None) -> dict:
    """Render one synthetic report. Returns text + labels + provenance."""
    t = load_taxonomy()
    core = FAMILIES[subcategory][lang][fam_idx]
    code_mixed = False
    frame_lang = lang
    if allow_codemix and lang in ("hi", "mr", "hl") and rng.random() < 0.25:
        core = FAMILIES[subcategory]["en"][rng.choice(split_famidx_pool)]
        code_mixed = True
    n = rng.choice([2, 3, 4, 5, 7, 10])
    parts: list[str] = []
    if rng.random() < 0.4:
        parts.append(rng.choice(F.PREFIXES[frame_lang]))
    place_text = ""
    tags: list[str] = []
    if place is not None:
        latin, deva, tags = place
        pt = deva if frame_lang in ("hi", "mr") and rng.random() < 0.85 else latin
        if frame_lang in ("hi", "mr") and pt == latin:
            code_mixed = True
        place_text = rng.choice(F.PLACE_CLAUSES[frame_lang]).format(p=pt)
    body = [core, place_text] if rng.random() < 0.7 else [place_text, core]
    parts.extend(x for x in body if x)
    if rng.random() < 0.5:
        suf = rng.choice(F.SUFFIXES[frame_lang]).format(n=n)
        parts.append(suf)
    elif lang == "en" and allow_codemix and rng.random() < 0.15:
        parts.append(rng.choice(F.EN_CODEMIX_SUFFIX))
        code_mixed = True
    text = " ".join(parts)
    noisy = rng.random() < 0.5 if noise is None else noise
    if noisy:
        text = add_spelling_noise(text, rng)
    text = add_surface_noise(text, rng)
    sub = t.subcategories[subcategory]
    return {
        "text": text, "language": F.LANG_TAG[lang], "code_mixed": code_mixed, "noisy": noisy,
        "category": sub.category_id, "subcategory": subcategory, "department": sub.department_id,
        "gold_severity": _gold_severity(t, subcategory, tags), "location_tags": tags,
    }


def generate_intake_split(split: str, n_per_family: int, seed: int, test_fold: int = 4) -> list[dict]:
    rng = random.Random(f"{seed}:intake:{split}:{test_fold}")
    fams = family_indices(split, test_fold)
    places = places_for(split, test_fold)            # [(index, (latin, devanagari, tags))]
    rows: list[dict] = []
    for sub in FAMILIES:
        for lang in F.LANGS:
            for fi in fams:
                for _ in range(n_per_family):
                    pick = rng.choice(places) if rng.random() < 0.7 else None
                    place = pick[1] if pick else None
                    rec = render_report(sub, lang, fi, place, rng, split_famidx_pool=fams)
                    rec.update({"split": split, "family_id": f"{sub}:{lang}:{fi}", "synthetic": True,
                                "generator_version": GENERATOR_VERSION,
                                "place_id": pick[0] if pick else None})
                    rows.append(rec)
    rng.shuffle(rows)
    for i, r in enumerate(rows):
        r["id"] = f"{split}-{i:05d}"
    return [{"id": r.pop("id"), **r} for r in rows]


# --------------------------------------------------------------------------- #
# Duplicate / fusion pairs
# --------------------------------------------------------------------------- #
def _report_side(sub: str, lang: str, fam: int, place_idx: int | None, lat: float, lon: float,
                 when: datetime, rng: random.Random, fams: list[int], tag: str) -> dict:
    place = F.PLACES[place_idx] if place_idx is not None else None
    r = render_report(sub, lang, fam, place, rng, split_famidx_pool=fams)
    return {"case_id": tag, "text": r["text"], "language": r["language"], "category": r["category"],
            "subcategory": sub, "latitude": lat, "longitude": lon,
            "created_at": when.isoformat(), "family_id": f"{sub}:{lang}:{fam}"}


def generate_pairs(split: str, n_pairs: int, seed: int, test_fold: int = 4) -> list[dict]:
    t = load_taxonomy()
    rng = random.Random(f"{seed}:pairs:{split}:{test_fold}")
    fams = family_indices(split, test_fold)
    places = places_for(split, test_fold)
    subs = [s for s in FAMILIES if s != "unclassified"]
    kinds = (["duplicate"] * 40 + ["distinct_near"] * 25 + ["related_category"] * 20
             + ["distinct_far"] * 5 + ["recurrence_old"] * 10)
    rows: list[dict] = []
    for i in range(n_pairs):
        kind = kinds[i % len(kinds)]
        sub = rng.choice(subs)
        pidx, _ = rng.choice(places)
        lat0, lon0 = place_coords(pidx)
        lat0, lon0 = offset_point(lat0, lon0, rng.uniform(0, 40), rng.uniform(0, 2 * math.pi))
        t0 = EPOCH + timedelta(hours=rng.uniform(0, 24 * 100))
        lang_a = rng.choice(F.LANGS)
        lang_b = lang_a if rng.random() < 0.6 else rng.choice(F.LANGS)
        fa, fb = rng.sample(fams, 2) if len(fams) > 1 else (fams[0], fams[0])
        keep_place_b = rng.random() < 0.8
        if kind == "duplicate":
            sigma = 60 if rng.random() < 0.1 else 20
            lat_b, lon_b = offset_point(lat0, lon0, abs(rng.gauss(0, sigma)), rng.uniform(0, 2 * math.pi))
            dt = timedelta(hours=rng.choice([rng.uniform(0, 72), rng.uniform(72, 240)]))
            sub_b, label = sub, 1
        elif kind == "distinct_near":
            d = rng.uniform(20, 50) if rng.random() < 0.1 else rng.uniform(60, 145)
            lat_b, lon_b = offset_point(lat0, lon0, d, rng.uniform(0, 2 * math.pi))
            dt = timedelta(hours=rng.uniform(0, 240))
            sub_b, label = sub, 0
        elif kind == "related_category":
            sibs = [s for s in t.categories[t.subcategories[sub].category_id].subcategory_ids if s != sub]
            sub_b = rng.choice(sibs) if sibs else sub
            lat_b, lon_b = offset_point(lat0, lon0, rng.uniform(0, 120), rng.uniform(0, 2 * math.pi))
            dt = timedelta(hours=rng.uniform(0, 240))
            label = 0 if sibs else 1
            if not sibs:
                kind = "duplicate"
        elif kind == "distinct_far":
            lat_b, lon_b = offset_point(lat0, lon0, rng.uniform(250, 2000), rng.uniform(0, 2 * math.pi))
            dt = timedelta(hours=rng.uniform(0, 240))
            sub_b, label = sub, 0
        else:  # recurrence_old: same place, long ago -> outside the time window
            lat_b, lon_b = offset_point(lat0, lon0, rng.uniform(0, 25), rng.uniform(0, 2 * math.pi))
            dt = timedelta(days=rng.uniform(35, 200))
            sub_b, label = sub, 0
        a = _report_side(sub, lang_a, fa, pidx, lat0, lon0, t0, rng, fams, f"{split}-p{i:05d}-a")
        b = _report_side(sub_b, lang_b, fb, pidx if keep_place_b else None, lat_b, lon_b, t0 + dt, rng, fams,
                         f"{split}-p{i:05d}-b")
        rows.append({"pair_id": f"{split}-p{i:05d}", "split": split, "synthetic": True,
                     "generator_version": GENERATOR_VERSION, "pair_type": kind, "label": label,
                     "cross_language": lang_a != lang_b, "a": a, "b": b})
    return rows
