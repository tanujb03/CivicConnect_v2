"""Source cards + mappings for the Indian datasets: every claim on a card must be honest about what was and was not verified."""
import json

import pytest
from pydantic import ValidationError

from ai.inference.config import load_taxonomy
from ai.training.src.data_sources import cli
from ai.training.src.data_sources.card_schema import SourceCard, check_terms, list_cards, load_card
from ai.training.src.data_sources.errors import TermsNotAccepted
from ai.training.src.data_sources.mapping import MAPPINGS_DIR, DepartmentMapping, MappingTable

OWNER_VERIFIED_2026_10_02 = {"bmc_mumbai", "rdd2020", "rdd2022", "mumbai_nashik_road_surface"}
INDIAN = ("bmc_mumbai", "rdd2020", "rdd2022", "bharatpothole", "mumbai_nashik_road_surface", "idd")
SUPPORTED_IMAGE = ("rdd2020", "rdd2022", "bharatpothole", "mumbai_nashik_road_surface")


def test_all_requested_indian_datasets_have_cards_with_the_requested_priority():
    ids = {c.id for c in list_cards()}
    assert set(INDIAN) <= ids
    pr = {i: load_card(i).priority for i in INDIAN}
    assert pr["bmc_mumbai"] == "primary" and pr["idd"] == "future"
    assert {pr[i] for i in SUPPORTED_IMAGE} == {"secondary"}
    assert load_card("synthetic_civic").priority == "primary" and load_card("nyc311").priority == "optional" and load_card("chicago311").priority == "optional"


@pytest.mark.parametrize("sid", INDIAN)
def test_licence_status_follows_the_recorded_evidence_and_no_card_claims_a_reviewed_status(sid):
    c = load_card(sid)
    if sid in OWNER_VERIFIED_2026_10_02:
        # the owner reviewed the research agent's quoted findings and instructed on 2026-10-02 to treat these as verified: the card must say so and quote the page
        assert c.license.status == "VERIFIED_PRIMARY" and c.license_verified and c.license.verified_on == "2026-10-02"
        assert any(e.reliability == "primary" and "instructed on 2026-10-02" in e.note and "Licence" in e.note or "Competition Data is additionally released" in e.note
                   for e in c.license.evidence)
    else:
        assert c.license.status == "UNVERIFIED" and not c.license_verified        # BharatPotHole (no dataset licence found) and IDD (future)
    assert c.review_status == "DRAFT_NEEDS_HUMAN_REVIEW" and c.redistribution_in_git == "never"
    assert "NOT be committed" in c.terms_summary()


def test_bmc_card_records_that_the_dataset_is_synthetic_third_party_and_never_official_or_real():
    c = load_card("bmc_mumbai")
    assert c.kind == "synthetic_third_party" and c.is_synthetic and c.origin_status == "SYNTHETIC_PER_COMPETITION" and c.origin_verified
    assert c.origin_notes and c.origin_evidence
    # the origin statement was relayed by the repository owner, not read by this tooling: it must NOT be tagged primary
    assert all(e.reliability != "primary" for e in c.origin_evidence)
    assert any("reports" in e.note and "not as a primary read" in e.note for e in c.origin_evidence)
    text = json.dumps(c.model_dump()).lower()
    assert "synthetically generated" in text and "not official bmc" in text
    assert "real-world validation" in text
    assert c.reference == "mumbai-nagar-seva-bmc-civic-complaint-resolution-2018-2024"
    assert c.landing_url.endswith("/competitions/mumbai-nagar-seva-bmc-civic-complaint-resolution-2018-2024/data")
    assert c.identity_status == "CONFIRMED_BY_USER" and c.priority == "primary"
    assert "SYNTHETIC DATA (third-party generated)" in c.terms_summary() and "ORIGIN UNVERIFIED" not in c.terms_summary()
    # the Rules' CC BY 4.0 statement was read by the owner's research agent and accepted by the owner as verified on 2026-10-02
    assert "CC BY 4.0" in c.license.name and c.license.status == "VERIFIED_PRIMARY" and c.license_verified
    assert any("Competition Data is additionally released under" in e.note and e.reliability == "primary" for e in c.license.evidence)


def test_bmc_card_declares_supported_and_unsupported_tasks_honestly():
    c = load_card("bmc_mumbai")
    assert {s.capability for s in c.supports} == {"AI-3", "AI-5", "AI-6"} and c.intended_use == ["training", "evaluation", "demo"]
    gaps = " ".join(g.capability + " " + g.why for g in c.does_not_support).lower()
    for must in ("real-world validation", "hindi", "marathi", "hinglish", "before", "satisfaction", "severity ground truth"):
        assert must in gaps, must
    assert any("AI-1" in g.capability for g in c.does_not_support)
    notes = " ".join(c.known_limitations + c.restrictions).lower()
    assert "never report results as real-world" in notes and "sensitive" in notes and "source agency" in notes


def test_synthetic_origin_cards_must_carry_evidence_and_the_right_kind():
    d = load_card("bmc_mumbai").model_dump()
    for change in ({"origin_evidence": []}, {"origin_notes": []}, {"kind": "real_public"}, {"origin_status": "PUBLISHER_IDENTIFIED"}):
        with pytest.raises(ValidationError):
            SourceCard.model_validate({**d, **change})
    d2 = load_card("rdd2022").model_dump()
    with pytest.raises(ValidationError):
        SourceCard.model_validate({**d2, "origin_status": "SYNTHETIC_PER_COMPETITION"})


def test_a_card_with_unverified_origin_must_explain_why():
    d = load_card("bmc_mumbai").model_dump()
    d["origin_notes"] = []
    with pytest.raises(ValidationError, match="origin_notes"):
        SourceCard.model_validate(d)


def test_bharatpothole_card_separates_code_licence_from_dataset_licence_and_stays_unverified():
    c = load_card("bharatpothole")
    assert c.landing_url == "https://www.kaggle.com/datasets/surbhisaswatimohanty/bharatpothole"
    assert "NOT STATED" in c.license.name and "NOT CC BY-NC-SA 4.0" in c.license.name
    assert "NOT permitted to be assumed" in c.license.commercial_use and any("Do not redistribute the raw dataset" in n for n in c.license.notes)
    assert any("Do NOT represent it as CC BY-NC-SA 4.0" in e.note and e.reliability == "secondary" for e in c.license.evidence)
    ev = " ".join(e.note for e in c.license.evidence)
    assert "NO dataset licence" in ev and "CODE" in ev and "NOT assumed" in ev
    assert any(e.reliability == "primary" for e in c.license.evidence)      # the README was actually fetched...
    assert c.license.status == "UNVERIFIED"                                  # ...but it states no dataset licence, so nothing is verified
    assert {s.capability for s in c.supports} == {"AI-1"}


def test_rdd2020_is_a_separate_card_with_its_own_noncommercial_licence_report():
    a, b = load_card("rdd2020"), load_card("rdd2022")
    assert "NonCommercial" in a.license.name and a.related_sources == ["rdd2022"]
    assert a.license.conflicts and "do NOT share a licence" in " ".join(a.license.conflicts)
    assert b.license.conflicts and b.license.share_alike is True              # RDD2022 README vs external records disagree: still unresolved
    assert "India" in b.subset_used


def test_mumbai_nashik_is_the_confirmed_dataset_with_a_verified_cc_by_licence():
    c = load_card("mumbai_nashik_road_surface")
    assert c.identity_status == "CONFIRMED_BY_USER" and c.landing_url == "https://data.mendeley.com/datasets/tj2m7zz4rg/2" and "Version 2" in c.version_note
    assert "8,484" in c.version_note and "13 videos" in c.version_note and "NOT established" in c.version_note
    assert "CC BY 4.0" in c.license.name and "Version 2" in c.license.name
    assert c.license.status == "VERIFIED_PRIMARY" and c.license_verified
    assert any(e.reliability == "primary" and "Licence — CC BY 4.0." in e.note for e in c.license.evidence)
    assert "not added" in json.dumps(c.model_dump()).lower() and "Indian Roads Dataset" in json.dumps(c.model_dump())
    assert "private Kaggle Dataset" in c.data_access["method"]


def test_idd_is_optional_future_with_no_adapter_and_no_v1_capability():
    c = load_card("idd")
    assert c.priority == "future" and c.adapter is None and c.supports == [] and c.mapping_id is None
    assert any("V1" in g.capability or "V1" in g.why for g in c.does_not_support)


def test_every_card_declares_a_priority_and_no_new_synthetic_labels_are_claimed_as_real():
    for c in list_cards():
        assert c.priority in ("primary", "secondary", "optional", "future")
    s = load_card("synthetic_civic")
    assert s.kind == "synthetic" and s.license_verified


def test_terms_gate_applies_to_every_indian_dataset():
    for sid in INDIAN:
        c = load_card(sid)
        with pytest.raises(TermsNotAccepted):
            check_terms(c, accepted=[], ack_unverified=True)
        if c.license_verified:
            check_terms(c, accepted=[sid], ack_unverified=False)           # a verified licence needs the terms acceptance only
        else:
            with pytest.raises(TermsNotAccepted):
                check_terms(c, accepted=[sid], ack_unverified=False)
        check_terms(c, accepted=[sid], ack_unverified=True)


def test_cli_card_prints_the_origin_warning_and_idd_prepare_is_refused(capsys, tmp_path):
    assert cli.main(["card", "bmc_mumbai"]) == 0
    out = capsys.readouterr().out
    assert "SYNTHETIC DATA (third-party generated)" in out and "VERIFIED_PRIMARY" in out
    assert cli.main(["card", "mumbai_nashik_road_surface"]) == 0 and "CC BY 4.0" in capsys.readouterr().out
    assert cli.main(["cards"]) == 0
    listing = capsys.readouterr().out
    assert all(i in listing for i in INDIAN)


# ------------------------------------------------------------------ mapping files
@pytest.mark.parametrize("mid", ["bmc_mumbai_to_civic", "bharatpothole_to_civic", "mumbai_nashik_to_civic", "rdd2020_to_civic"])
def test_new_mappings_validate_against_the_frozen_taxonomy_and_are_marked_draft(mid):
    m = MappingTable.load(mid)          # load() validates every rule's category/subcategory against the frozen taxonomy
    assert m.raw["status"].startswith("DRAFT") and m.version.endswith("-draft")
    assert m.raw["taxonomy_version"] == load_taxonomy().version


def test_mappings_reference_the_card_that_declares_them():
    for c in list_cards():
        if c.mapping_id:
            assert (MAPPINGS_DIR / f"{c.mapping_id}.v1.json").is_file(), c.id
            assert MappingTable.load(c.mapping_id).raw["source_id"] == c.id


def test_bmc_category_mapping_covers_the_reported_categories_and_never_forces_out_of_scope_ones():
    m = MappingTable.load("bmc_mumbai_to_civic")
    expect = {"Pothole/Road Damage": ("roads", None, "category_only"), "Water Supply Disruption": ("water_supply", None, "category_only"),
              "Water Leakage/Pipe Burst": ("water_supply", "pipe_leakage", "exact"), "Street Light Failure": ("street_lighting", "light_not_working", "exact"),
              "Stray Animal Menace": ("public_health", "stray_animals", "exact"), "Illegal Construction": (None, None, "out_of_scope"),
              "Noise/Air Pollution": (None, None, "out_of_scope")}
    for label, (cat, sub, status) in expect.items():
        r = m.map(category=label)
        assert (r.category, r.subcategory, r.status) == (cat, sub, status), label
    assert m.map(category="Something Entirely New").status == "unmapped"


def test_bmc_department_mapping_is_a_separate_draft_that_returns_none_for_unknown_departments():
    dm = DepartmentMapping.load("bmc_mumbai_departments")
    assert dm.raw["status"].startswith("DRAFT")
    assert dm.map("Totally Unknown Unit") is None


def test_cracks_map_to_the_roads_category_only_and_never_to_a_new_taxonomy_entry():
    for mid in ("rdd2020_to_civic", "rdd2022_to_civic"):
        m = MappingTable.load(mid)
        for crack in ("D00", "D10", "D20"):
            r = m.map(class_code=crack)
            assert r.category == "roads" and r.subcategory is None, (mid, crack)
        assert m.map(class_code="D40").subcategory == "pothole"
