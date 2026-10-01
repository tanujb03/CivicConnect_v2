import json
import re

from ai.inference.config import CONFIG_DIR, Taxonomy, load_fusion_policy, load_triage_rules

SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
UPPER = re.compile(r"^[A-Z][A-Z_]*$")


def raw():
    return json.loads((CONFIG_DIR / "taxonomy.v1.json").read_text(encoding="utf-8"))


def test_review_gate_is_explicit():
    d = raw()
    assert set(d["review"]["required_reviewers"]) == {"Tanuj", "Parth"}
    if d["status"] == "APPROVED":  # once reviewed, both sign-offs must be recorded
        assert {"Tanuj", "Parth"} <= set(d["review"]["approved_by"])
    else:
        assert d["status"] == "DRAFT_REQUIRES_REVIEW"


def test_ids_are_stable_machine_ids_and_unique(taxonomy):
    # IDs are unique inside each namespace. A category and its department may deliberately share an ID
    # (water_supply, drainage_sewerage, street_lighting): they live in separate API fields.
    d = raw()
    for key in ("categories", "departments", "severities", "priorities", "sla_classes"):
        ids = [e["id"] for e in d[key]]
        assert len(ids) == len(set(ids)), key
    sub_ids = [s["id"] for c in d["categories"] for s in c["subcategories"]]
    assert len(sub_ids) == len(set(sub_ids))
    # subcategory IDs never collide with category/department IDs (keeps 'category/subcategory' labels unambiguous)
    assert not set(sub_ids) & (set(taxonomy.categories) | set(taxonomy.departments))
    names = [*taxonomy.categories, *taxonomy.subcategories, *taxonomy.departments]
    assert all(SNAKE.match(i) for i in names)
    assert all(UPPER.match(i) for i in [*taxonomy.severity_rank, *taxonomy.priority_rank, *taxonomy.sla_hours])


def test_hierarchy_and_department_mapping(taxonomy):
    assert len(taxonomy.departments) == 8  # Section 58: 8 departments
    for c in taxonomy.categories.values():
        if c.id == "other":
            assert c.department_id is None  # unclear reports need human routing
            continue
        assert c.department_id in taxonomy.departments
        assert c.id in taxonomy.departments[c.department_id].category_ids
    for d in taxonomy.departments.values():
        assert d.category_ids, f"department {d.id} covers no category"
    assert all(s.category_id in taxonomy.categories for s in taxonomy.subcategories.values())
    assert len(taxonomy.label_ids) == len(taxonomy.subcategories) == 27


def test_labels_in_all_supported_languages(taxonomy):
    for table in (taxonomy.categories, taxonomy.subcategories, taxonomy.departments):
        for e in table.values():
            assert all(e.label.get(l) for l in ("en", "hi", "mr")), e.id
    d = raw()
    for s in (*d["severities"], *d["sla_classes"], *d["priorities"]):
        assert all(s["label"].get(l) for l in ("en", "hi", "mr"))


def test_severity_priority_sla_chain(taxonomy):
    assert list(taxonomy.severity_rank) == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]  # Section 51A.5
    assert list(taxonomy.priority_rank) == ["LOW", "NORMAL", "HIGH", "URGENT"]
    ranks = [taxonomy.priority_rank[p] for p in taxonomy.priority_rank]
    hours = [taxonomy.sla_hours[taxonomy.priority_sla_class[p]] for p in taxonomy.priority_rank]
    assert ranks == sorted(ranks) and hours == sorted(hours, reverse=True)  # higher priority => tighter SLA
    assert taxonomy.sla_hours["EMERGENCY"] < taxonomy.sla_hours["URGENT"]


def test_resolves_the_documented_naming_inconsistencies(taxonomy):
    # Section 11 used lowercase ids ('roads', 'road_maintenance'); 51A.8 used 'WATER' / 'URGENT'.
    assert taxonomy.resolve_department("WATER") == "water_supply"
    assert taxonomy.resolve_department("water_supply") == "water_supply"
    assert taxonomy.resolve_department("road_maintenance") == "road_maintenance"
    assert taxonomy.resolve_department("nonexistent") is None
    assert taxonomy.resolve_category("ROADS") == "roads"
    assert taxonomy.department_for("roads", "pothole") == "road_maintenance"
    # 51A.8 example (HIGH / URGENT / WATER / 24h) is representable
    assert taxonomy.priority_sla_class["URGENT"] == "URGENT" and taxonomy.sla_hours["URGENT"] == 24


def test_safety_critical_subcategories_are_high_or_critical(taxonomy):
    for s in taxonomy.subcategories.values():
        if s.safety_critical:
            assert taxonomy.severity_rank[s.base_severity] >= taxonomy.severity_rank["HIGH"], s.id


def test_valid_pair_and_label_helpers(taxonomy):
    assert taxonomy.is_valid_pair("roads", "pothole")
    assert not taxonomy.is_valid_pair("sanitation", "pothole")
    assert "roads/pothole" in taxonomy.label_ids


def test_triage_rules_reference_valid_enums(taxonomy):
    r = load_triage_rules()
    assert set(r["severity_score"]) == set(taxonomy.severity_rank)
    assert {t["priority"] for t in r["priority_thresholds"]} == set(taxonomy.priority_rank)
    assert [t["min_score"] for t in r["priority_thresholds"]] == sorted((t["min_score"] for t in r["priority_thresholds"]), reverse=True)
    for o in r["sla_overrides"]:
        assert o["sla_class"] in taxonomy.sla_hours and o["when_severity"] in taxonomy.severity_rank
    for e in r["severity_escalators"]:
        assert e["patterns"] and e["bump"] >= 1


def test_fusion_policy_is_consistent():
    p = load_fusion_policy()
    assert 0 < p["thresholds"]["related"] < p["thresholds"]["possible_duplicate"] < 1
    assert p["candidate_generation"]["radius_m"] > 0 and p["candidate_generation"]["time_window_days"] > 0


def test_from_dict_rejects_dangling_references():
    d = raw()
    d["categories"][0]["department_id"] = "no_such_department"
    import pytest

    from ai.inference.errors import TaxonomyError
    with pytest.raises(TaxonomyError):
        Taxonomy.from_dict(d)
