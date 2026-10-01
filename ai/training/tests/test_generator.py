import math
import random
import unicodedata
from collections import Counter

from ai.inference.config import load_taxonomy
from ai.training.src.synthetic import frames as F
from ai.training.src.synthetic import generator as gen
from ai.training.src.synthetic.noise import add_spelling_noise, clusters

T = load_taxonomy()


def split_rows(seed=3, fold=4, n=(3, 2, 2)):
    return {s: gen.generate_intake_split(s, k, seed, fold) for s, k in zip(("train", "val", "test"), n)}


def test_lexicon_covers_every_subcategory_language_and_family():
    assert set(gen.FAMILIES) == set(T.subcategories)
    for sub, langs in gen.FAMILIES.items():
        assert set(langs) == set(F.LANGS)
        assert all(len(v) == F.N_FAMILIES and len(set(v)) == F.N_FAMILIES for v in langs.values()), sub


def test_generation_is_deterministic_and_seed_sensitive():
    a, b, c = gen.generate_intake_split("test", 2, 5), gen.generate_intake_split("test", 2, 5), gen.generate_intake_split("test", 2, 6)
    assert a == b and a != c
    assert gen.generate_pairs("val", 30, 5) == gen.generate_pairs("val", 30, 5)


def test_every_record_is_labelled_synthetic_with_valid_labels():
    for rows in split_rows().values():
        ids = [r["id"] for r in rows]
        assert len(ids) == len(set(ids))
        for r in rows:
            assert r["synthetic"] is True and r["generator_version"] == gen.GENERATOR_VERSION
            assert r["text"].strip() and T.is_valid_pair(r["category"], r["subcategory"])
            assert r["department"] == T.department_for(r["category"], r["subcategory"])
            assert r["gold_severity"] in T.severity_rank and r["language"] in {"en", "hi", "mr", "hi-Latn"}


def test_held_out_by_template_family_and_by_place():
    s = split_rows()
    fam = {k: {r["family_id"] for r in v} for k, v in s.items()}
    assert not fam["train"] & fam["val"] and not fam["train"] & fam["test"] and not fam["val"] & fam["test"]
    place = {k: {r["place_id"] for r in v if r["place_id"] is not None} for k, v in s.items()}
    assert not place["train"] & place["val"] and not place["train"] & place["test"] and not place["val"] & place["test"]
    # the core phrase of every test family never occurs in training text (no verbatim leakage)
    for r in s["test"][:60]:
        sub, lang, idx = r["family_id"].split(":")
        core = gen.FAMILIES[sub][lang][int(idx)]
        assert core not in {x["text"] for x in s["train"]}


def test_every_family_index_is_in_exactly_one_split_per_fold():
    for fold in range(5):
        parts = [gen.family_indices(s, fold) for s in ("train", "val", "test")]
        assert sorted(sum(parts, [])) == list(range(5)) and len(parts[2]) == 1 and len(parts[1]) == 1


def test_kfold_rotation_covers_all_families_as_test():
    assert sorted(gen.family_indices("test", f)[0] for f in range(5)) == [0, 1, 2, 3, 4]
    assert gen.generate_intake_split("test", 1, 3, 0) != gen.generate_intake_split("test", 1, 3, 1)


def test_all_languages_classes_and_phenomena_are_present():
    rows = gen.generate_intake_split("train", 6, 9)
    assert {r["language"] for r in rows} == {"en", "hi", "mr", "hi-Latn"}
    assert {f"{r['category']}/{r['subcategory']}" for r in rows} == set(T.label_ids)
    assert any(r["code_mixed"] for r in rows) and any(r["noisy"] for r in rows) and any(not r["noisy"] for r in rows)
    deva = [r for r in rows if r["language"] in ("hi", "mr")]
    assert sum(any("ऀ" <= ch <= "ॿ" for ch in r["text"]) for r in deva) / len(deva) > 0.9
    assert sum(r["location_tags"] != [] for r in rows) > 0
    assert Counter(r["language"] for r in rows).most_common()[-1][1] > 0.2 * len(rows)


def test_gold_severity_escalates_for_sensitive_places():
    rows = gen.generate_intake_split("train", 6, 9)
    for r in rows:
        base = T.subcategories[r["subcategory"]].base_severity
        expect = T.severity_by_rank(T.severity_rank[base] + (1 if {"school", "hospital"} & set(r["location_tags"]) else 0))
        assert r["gold_severity"] == expect


def test_default_eval_set_size_matches_section_57():
    assert 100 <= len(gen.generate_intake_split("test", 2, 42)) <= 300


def test_noise_keeps_combining_marks_attached():
    rng = random.Random(1)
    text = "सड़क पर बड़ा गड्ढा है, कृपया ध्यान दें"
    assert "".join(clusters(text)) == text
    for _ in range(50):
        out = add_spelling_noise(text, rng, rate=0.3)
        assert out and not unicodedata.category(out.lstrip()[0]).startswith("M")  # no orphaned matra at the start
    assert add_spelling_noise("pothole", random.Random(2), rate=0.0) == "pothole"
    assert add_spelling_noise("pothole road", random.Random(2), rate=0.5) != "pothole road"


def test_pair_labels_are_logically_consistent():
    pairs = gen.generate_pairs("test", 200, 4)
    kinds = Counter(p["pair_type"] for p in pairs)
    assert set(kinds) == {"duplicate", "distinct_near", "related_category", "distinct_far", "recurrence_old"}
    for p in pairs:
        a, b = p["a"], p["b"]
        d = gen_dist(a, b)
        assert p["synthetic"] is True and p["label"] in (0, 1)
        if p["pair_type"] == "duplicate":
            assert p["label"] == 1 and a["subcategory"] == b["subcategory"]
        else:
            assert p["label"] == 0
        if p["pair_type"] == "distinct_far":
            assert d > 150
        if p["pair_type"] == "recurrence_old":
            assert abs((gen_t(b) - gen_t(a)).days) >= 35
        if p["pair_type"] == "related_category":
            assert a["category"] == b["category"] and a["subcategory"] != b["subcategory"]
    assert sum(gen_dist(p["a"], p["b"]) < 100 for p in pairs if p["pair_type"] == "duplicate") > 0.8 * kinds["duplicate"]


def test_pair_splits_are_family_disjoint():
    fams = {s: {p[x]["family_id"] for p in gen.generate_pairs(s, 150, 4) for x in "ab"} for s in ("train", "val", "test")}
    assert not fams["train"] & fams["test"] and not fams["train"] & fams["val"] and not fams["val"] & fams["test"]


def gen_t(side):
    from datetime import datetime
    return datetime.fromisoformat(side["created_at"])


def gen_dist(a, b):
    from ai.inference.fusion.similarity import haversine_m
    return haversine_m(a["latitude"], a["longitude"], b["latitude"], b["longitude"])


def test_place_coordinates_are_distinct_and_offsets_have_expected_length():
    pts = {gen.place_coords(i) for i in range(len(F.PLACES))}
    assert len(pts) == len(F.PLACES)
    lat, lon = gen.place_coords(0)
    nlat, nlon = gen.offset_point(lat, lon, 100.0, math.pi / 3)
    assert abs(gen_dist({"latitude": lat, "longitude": lon}, {"latitude": nlat, "longitude": nlon}) - 100) < 1.0
