import json

import pytest
from pydantic import ValidationError

from ai.inference.config import load_taxonomy
from ai.training.src.data_sources.canonical import BBox, CaseRecord, Provenance
from ai.training.src.data_sources.card_schema import CARDS_DIR, LicenseInfo, SourceCard, check_terms, list_cards, load_card
from ai.training.src.data_sources.errors import DataSourceError, MappingError, TermsNotAccepted
from ai.training.src.data_sources.mapping import MAPPINGS_DIR, CoverageReport, MappingTable

REAL = ("nyc311", "chicago311", "rdd2022")


def prov(**kw):
    base = dict(kind="real_public", source_id="x", source_dataset="X", license_id="L", license_verified=False, label_origin="mapped_from_source")
    return Provenance(**{**base, **kw})


# ------------------------------------------------------------------ source cards
def test_all_cards_validate_and_cover_the_requested_datasets():
    ids = {c.id for c in list_cards()}
    assert {"nyc311", "chicago311", "rdd2022", "synthetic_civic"} <= ids


@pytest.mark.parametrize("sid", REAL)
def test_real_cards_record_the_required_provenance_fields(sid):
    c = load_card(sid)
    assert c.landing_url and c.version_note and c.subset_used and c.intended_use and c.restrictions
    assert c.license.name and c.license.attribution and c.license.evidence
    assert c.redistribution_in_git == "never" and c.supports and c.does_not_support and c.known_limitations
    assert c.last_reviewed and c.review_status == "DRAFT_NEEDS_HUMAN_REVIEW"
    assert "NOT be committed" in c.terms_summary()


def test_licence_status_is_honest_about_what_was_verified():
    for sid in ("nyc311", "chicago311"):
        c = load_card(sid)
        assert c.license.status == "UNVERIFIED" and not any(e.reliability == "primary" for e in c.license.evidence)
    rdd = load_card("rdd2022")
    assert rdd.license.status == "UNVERIFIED" and rdd.license.conflicts and rdd.license.share_alike is True   # strict reading until resolved
    assert "CC BY-SA" in rdd.license.name and "CC BY 4.0" in rdd.license.name
    assert load_card("synthetic_civic").license_verified


def test_a_card_cannot_claim_verified_without_primary_evidence():
    with pytest.raises(ValidationError):
        LicenseInfo(name="x", status="VERIFIED_PRIMARY", attribution="a", evidence=[{"source": "s", "reliability": "secondary", "note": "n"}], verified_on="2026-10-01")
    with pytest.raises(ValidationError):
        LicenseInfo(name="x", status="VERIFIED_PRIMARY", attribution="a", evidence=[{"source": "s", "reliability": "primary", "note": "n"}])
    LicenseInfo(name="x", status="VERIFIED_PRIMARY", attribution="a", verified_on="2026-10-01", evidence=[{"source": "s", "reliability": "primary", "note": "n"}])


def test_capability_claims_match_what_each_dataset_can_legitimately_support():
    caps = {sid: {s.capability for s in load_card(sid).supports} for sid in REAL}
    assert "AI-1" not in caps["nyc311"] and "AI-1" not in caps["chicago311"]       # no narrative text => no text-intake claims
    assert {"AI-5", "AI-3"} <= caps["nyc311"] and {"AI-2", "AI-5"} <= caps["chicago311"]
    assert caps["rdd2022"] == {"AI-1", "AI-2"}
    for sid in ("nyc311", "chicago311"):
        gaps = " ".join(g.capability + g.why for g in load_card(sid).does_not_support).lower()
        assert "text intake" in gaps and "leakage" in gaps or "narrative" in gaps
    assert any("AI-4" in g.capability for g in load_card("rdd2022").does_not_support)


def test_terms_gate():
    nyc = load_card("nyc311")
    with pytest.raises(TermsNotAccepted, match="--accept-terms nyc311"):
        check_terms(nyc, accepted=[], ack_unverified=True)
    with pytest.raises(TermsNotAccepted, match="UNVERIFIED"):
        check_terms(nyc, accepted=["nyc311"], ack_unverified=False)
    with pytest.raises(TermsNotAccepted):
        check_terms(nyc, accepted=["chicago311"], ack_unverified=True)      # accepting another dataset's terms does not count
    check_terms(nyc, accepted=["nyc311"], ack_unverified=True)
    check_terms(load_card("synthetic_civic"), accepted=[], ack_unverified=False)
    d = json.loads(nyc.model_dump_json())
    d["license"].update(status="VERIFIED_PRIMARY", verified_on="2026-10-01")
    d["license"]["evidence"].append({"source": "official", "reliability": "primary", "note": "read", "retrieved_on": "2026-10-01"})
    verified = SourceCard.model_validate(d)
    check_terms(verified, accepted=["nyc311"], ack_unverified=False)


def test_unknown_card():
    with pytest.raises(DataSourceError):
        load_card("does_not_exist")


# ------------------------------------------------------------------ canonical schema
def test_case_record_enforces_text_and_mapping_consistency():
    CaseRecord(record_id="a", provenance=prov())
    with pytest.raises(ValidationError):
        CaseRecord(record_id="a", provenance=prov(), text="x")                                       # text without origin
    with pytest.raises(ValidationError):
        CaseRecord(record_id="a", provenance=prov(), text_origin="citizen_narrative")                 # origin without text
    with pytest.raises(ValidationError):
        CaseRecord(record_id="a", provenance=prov(), category="roads", mapping_status="exact")        # exact needs subcategory
    with pytest.raises(ValidationError):
        CaseRecord(record_id="a", provenance=prov(), category="roads", subcategory="pothole", mapping_status="unmapped")
    with pytest.raises(ValidationError):
        CaseRecord(record_id="a", provenance=prov(), subcategory="pothole")
    with pytest.raises(ValidationError):
        CaseRecord(record_id="a", provenance=prov(), latitude=95)
    with pytest.raises(ValidationError):
        CaseRecord(record_id="a", provenance=prov(), unexpected_field=1)                              # extra=forbid
    with pytest.raises(ValidationError):
        CaseRecord(record_id="a")                                                                     # provenance is mandatory


def test_bbox_rejects_degenerate_boxes():
    BBox(class_code="D40", xmin=0, ymin=0, xmax=1, ymax=1)
    with pytest.raises(ValidationError):
        BBox(class_code="D40", xmin=5, ymin=0, xmax=5, ymax=1)


# ------------------------------------------------------------------ mapping layer
@pytest.mark.parametrize("mid", ["nyc311_to_civic", "chicago311_to_civic", "rdd2022_to_civic"])
def test_mapping_tables_are_valid_versioned_drafts(mid):
    t = MappingTable.load(mid)
    assert t.version and t.raw["taxonomy_version"] == load_taxonomy().version and "DRAFT" in t.raw["status"]
    assert t.raw["provenance_note"] and len(t.rules) >= 4
    assert t.fingerprint() == MappingTable.load(mid).fingerprint()


def test_mapping_first_match_wins_and_is_case_insensitive():
    t = MappingTable.load("nyc311_to_civic")
    r = t.map(complaint_type="STREET CONDITION", descriptor="POTHOLE")
    assert (r.status, r.category, r.subcategory, r.rule_id) == ("exact", "roads", "pothole", "nyc-pothole")
    r = t.map(complaint_type="Street Condition", descriptor="Cave-In")
    assert (r.status, r.category, r.subcategory) == ("category_only", "roads", None)
    assert t.map(complaint_type="Noise - Residential", descriptor="x").status == "out_of_scope"
    assert t.map(complaint_type="Never Heard Of It", descriptor="x").status == "unmapped"
    assert t.map(complaint_type="Street Condition").status == "category_only"      # missing descriptor cannot satisfy a descriptor rule
    assert t.map(descriptor="Pothole").status == "unmapped"                          # missing complaint_type never matches


def test_rdd_mapping_is_explicit_about_what_taxonomy_v1_cannot_express():
    t = MappingTable.load("rdd2022_to_civic")
    assert (t.map(class_code="D40").status, t.map(class_code="D40").subcategory) == ("exact", "pothole")
    for crack in ("D00", "D10", "D20"):
        r = t.map(class_code=crack)
        assert (r.status, r.category, r.subcategory) == ("category_only", "roads", None)
    assert t.map(class_code="D43").status == "unmapped"


def test_mapping_validation_rejects_bad_tables():
    base = json.loads((MAPPINGS_DIR / "rdd2022_to_civic.v1.json").read_text(encoding="utf-8"))

    def bad(mutate):
        d = json.loads(json.dumps(base)); mutate(d)
        with pytest.raises(MappingError):
            MappingTable.from_dict(d)

    bad(lambda d: d["rules"][0].update(category="no_such_category"))
    bad(lambda d: d["rules"][0].update(category="sanitation", subcategory="pothole"))      # pair not in taxonomy
    bad(lambda d: d["rules"][1].update(id=d["rules"][0]["id"]))                              # duplicate rule id
    bad(lambda d: d["rules"][0].update(when={"unknown_field": "x"}))
    bad(lambda d: d["rules"][0].update(when={"class_code": {"fuzzy": "x"}}))
    bad(lambda d: d["rules"].append({"id": "oos", "when": {"class_code": "Z"}, "out_of_scope": True, "category": "roads"}))


def test_coverage_report():
    t = MappingTable.load("nyc311_to_civic")
    cov = CoverageReport()
    for ct, d in [("Street Condition", "Pothole"), ("Street Condition", "Other"), ("Noise - Residential", "x"), ("Weird", "y"), ("Weird", "y")]:
        cov.add(t.map(complaint_type=ct, descriptor=d), f"{ct} | {d}")
    r = cov.to_dict()
    assert r["total"] == 5 and r["counts"] == {"category_only": 1, "exact": 1, "out_of_scope": 1, "unmapped": 2}
    assert r["mapped_to_subcategory_share"] == 0.2 and r["mapped_any_share"] == 0.4 and tuple(r["top_unmapped_source_labels"][0]) == ("Weird | y", 2)
    assert r["by_label"] == {"roads/pothole": 1, "roads/*": 1}


def test_cards_and_mappings_directory_layout():
    assert {p.stem for p in CARDS_DIR.glob("*.json")} >= {"nyc311", "chicago311", "rdd2022", "synthetic_civic"}
    assert {p.name for p in MAPPINGS_DIR.glob("*.json")} == {"nyc311_to_civic.v1.json", "chicago311_to_civic.v1.json", "rdd2022_to_civic.v1.json"}
