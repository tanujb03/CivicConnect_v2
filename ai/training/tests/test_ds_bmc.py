"""BMC Mumbai: column-role policy, adapter, leakage audits, evaluation plumbing.

Everything here runs on an INVENTED fixture with the *shape* we expect (``FMT-B*`` ids, ``INVENTED`` names): the real
Kaggle file was never available to this repo, so column names are expectations, not facts. The fixture deliberately
contains leakage traps (deterministic severity/department per category, echoing remarks/descriptions, PII columns,
an unclassified sentinel column) so these tests prove the protections, not just the happy path.
"""
import copy
import csv
import json

import pytest

from ai.evaluation import eval_real, run_eval
from ai.evaluation.provenance import claims_for
from ai.training.src.data_sources import cli
from ai.training.src.data_sources import prepare as prep
from ai.training.src.data_sources.adapters.bmc_mumbai import BMCMumbaiAdapter
from ai.training.src.data_sources.canonical import CaseRecord
from ai.training.src.data_sources.card_schema import load_card
from ai.training.src.data_sources.column_roles import POLICY_DIR, LeakageError, TaskPolicy
from ai.training.src.data_sources.errors import DataSourceError, SchemaMismatch
from ai.training.src.data_sources.leakage import (
    audit_task,
    censoring_report,
    spatiotemporal_straddle,
    split_straddle,
    target_determinism,
    text_contains_label,
    views_clean,
)
from ai.training.src.data_sources.mapping import DepartmentMapping, MappingTable
from ai.training.src.data_sources.profile import profile_bmc
from ai.training.src.io_utils import read_jsonl

from .conftest_real import FIXTURES

BMC_CSV = FIXTURES / "bmc_mumbai_format_sample.csv"
ACCEPT = ["--accept-terms", "bmc_mumbai", "--acknowledge-unverified-license"]
SENTINELS = ("INVENTED PERSON", "INVENTED CONTRACTOR", "SENTINEL-", "attended by team", "Resolved:")


@pytest.fixture(scope="module")
def policy():
    return TaskPolicy.load("bmc_mumbai")


@pytest.fixture(scope="module")
def card():
    return load_card("bmc_mumbai")


def hypothetical_real_card(card):
    """The real BMC card describes SYNTHETIC data, so confirmed-citizen-text machinery can only be exercised on a hypothetical real-origin copy."""
    return card.model_copy(update={"kind": "real_public", "origin_status": "PUBLISHER_IDENTIFIED", "origin_evidence": []})


def make_adapter(card, policy, **kw):
    return BMCMumbaiAdapter(card, MappingTable.load(card.mapping_id), DepartmentMapping.load("bmc_mumbai_departments"), policy, retrieved_at="2026-10-01", **kw)


@pytest.fixture(scope="module")
def records(card, policy):
    return list(make_adapter(card, policy).iter_records(BMC_CSV))


@pytest.fixture(scope="module")
def prepared(tmp_path_factory, card):
    out = tmp_path_factory.mktemp("bmc") / "prep"
    m = prep.prepare_bmc(card, BMC_CSV, out, holdout_after="2024-03-01", retrieved_at="2026-10-01")
    return out, m


def raw_policy() -> dict:
    return json.loads((POLICY_DIR / "bmc_mumbai_columns.v1.json").read_text(encoding="utf-8"))


def mutate(fn) -> dict:
    d = copy.deepcopy(raw_policy())
    fn(d)
    return d


def task_of(d, name):
    return next(t for t in d["tasks"] if t["task"] == name)


# ------------------------------------------------------------------ policy structure (default-deny, phases)
def test_shipped_policy_validates_and_never_exposes_sensitive_or_pii_roles(policy):
    never = {r for r, s in policy.roles.items() if s.phase in ("sensitive_attribute", "pii_never_read")}
    assert {"complainant_profile", "pii"} <= never
    for task, t in policy.tasks.items():
        assert not (set(t.inputs) | set(t.targets)) & never, task
        assert never <= policy.effective_forbidden(task)


def test_no_evaluation_or_descriptive_task_takes_post_resolution_inputs_and_only_demo_may_exceed_post_triage(policy):
    for t in policy.tasks.values():
        if t.purpose in ("evaluation", "descriptive"):
            assert t.max_phase != "post_resolution"
            assert not [r for r in t.inputs if policy.roles[r].phase == "post_resolution"], t.task
    assert [t.task for t in policy.tasks.values() if t.max_phase == "post_resolution"] == ["demo_seed"]


def test_intake_and_triage_never_see_the_label_or_post_triage_fields(policy):
    intake = policy.tasks["intake_text"]
    assert "source_category" not in intake.inputs and "category" not in intake.inputs     # the label's source must not be an input
    assert set(intake.targets) == {"category", "subcategory"} and intake.status == "conditional"
    assert intake.operator_confirmations == ["description_is_citizen_text"]
    triage = policy.tasks["triage_priority_prior"]
    assert not {"department", "severity", "priority", "status", "closed_at", "resolution_hours", "resolution_remarks"} & set(triage.inputs)
    assert "department" not in policy.tasks["routing_agreement"].inputs and policy.tasks["routing_agreement"].targets == ["department"]


def test_resolution_time_prior_may_use_post_triage_inputs_but_not_outcomes(policy):
    t = policy.tasks["resolution_time_prior"]
    assert t.max_phase == "post_triage" and t.targets == ["resolution_hours"]
    assert not {"status", "closed_at", "resolution_remarks", "reopened", "escalated", "sla_breached", "reassigned"} & set(t.inputs)


def test_citizen_satisfaction_is_not_pursued_and_its_columns_are_not_stored(policy):
    assert policy.tasks["citizen_satisfaction"].status == "not_pursued"
    assert not policy.roles["citizen_satisfied"].store and not policy.roles["citizen_rating"].store
    with pytest.raises(LeakageError):
        policy.view(CaseRecord.model_validate(_rec_dict()), "citizen_satisfaction")


@pytest.mark.parametrize("label,fn", [
    ("input_is_also_target", lambda d: task_of(d, "routing_agreement")["inputs"].append("department")),
    ("target_phase_input_post_resolution", lambda d: task_of(d, "triage_priority_prior")["inputs"].append("status")),
    ("pii_input", lambda d: task_of(d, "taxonomy_coverage")["inputs"].append("pii")),
    ("sensitive_target", lambda d: task_of(d, "resolution_time_prior")["targets"].append("complainant_profile")),
    ("input_exceeds_max_phase", lambda d: task_of(d, "intake_text")["inputs"].append("severity")),
    ("descriptive_post_resolution_max_phase", lambda d: task_of(d, "recurrence_hotspot").update(max_phase="post_resolution")),
    ("forbidden_overlap", lambda d: task_of(d, "resolution_time_prior")["forbidden"].append("severity")),
])
def test_mutated_policies_that_open_a_leak_are_rejected(label, fn):
    with pytest.raises(LeakageError):
        TaskPolicy.from_dict(mutate(fn))


def test_policy_rejects_unknown_roles_duplicate_aliases_and_unconditioned_conditional_tasks():
    with pytest.raises(DataSourceError):
        TaskPolicy.from_dict(mutate(lambda d: task_of(d, "taxonomy_coverage")["inputs"].append("no_such_role")))
    with pytest.raises(DataSourceError):
        TaskPolicy.from_dict(mutate(lambda d: d["roles"][2]["aliases"].append("complaint_id")))
    with pytest.raises(DataSourceError):
        TaskPolicy.from_dict(mutate(lambda d: task_of(d, "intake_text").update(requires=[], requires_any=[], operator_confirmations=[])))


# ------------------------------------------------------------------ header classification
def test_classify_headers_by_alias_default_denies_unknown_columns_and_ignores_pii(policy):
    res = policy.classify_headers(["complaint_no", "filed_date", "ward", "complaint_category", "mystery_col", "complainant_age", "complainant_name"])
    assert res.columns["complaint_id"] == "complaint_no" and res.columns["created_at"] == "filed_date"
    assert res.unclassified == ["mystery_col"]
    assert res.sensitive_ignored == ["complainant_age"] and res.pii_ignored == ["complainant_name"]


def test_several_sensitive_or_pii_columns_are_not_an_ambiguity(policy):
    res = policy.classify_headers(["complainant_age", "complainant_gender", "complainant_name", "contractor_name"])
    assert sorted(res.sensitive_ignored) == ["complainant_age", "complainant_gender"] and sorted(res.pii_ignored) == ["complainant_name", "contractor_name"]


def test_ambiguous_aliases_fail_loudly_instead_of_guessing(policy):
    with pytest.raises(SchemaMismatch, match="ambiguous"):
        policy.classify_headers(["complaint_date", "registered_date", "ward"])


def test_role_map_resolves_ambiguity_and_takes_precedence_over_aliases(policy):
    res = policy.classify_headers(["complaint_date", "registered_date", "weird_cat"], {"registered_date": "created_at", "weird_cat": "source_category"})
    assert res.columns["created_at"] == "registered_date" and res.columns["source_category"] == "weird_cat"
    assert res.unclassified == ["complaint_date"]       # the loser is NOT silently used


def test_role_map_errors_are_loud(policy):
    with pytest.raises(SchemaMismatch, match="unknown roles"):
        policy.classify_headers(["a"], {"a": "not_a_role"})
    with pytest.raises(SchemaMismatch, match="not in the file"):
        policy.classify_headers(["a"], {"zzz": "ward"})
    with pytest.raises(SchemaMismatch, match="assigned to both"):
        policy.classify_headers(["a", "b"], {"a": "ward", "b": "ward"})


def test_an_operator_can_reclassify_a_column_as_pii_or_sensitive(policy):
    res = policy.classify_headers(["complaint_id", "contact_blob"], {"contact_blob": "pii"})
    assert res.pii_ignored == ["contact_blob"] and not res.unclassified


# ------------------------------------------------------------------ adapter: what is and is not read/stored
def test_adapter_requires_the_roles_it_cannot_do_without(card, policy, tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(SchemaMismatch, match="cannot resolve required role"):
        list(make_adapter(card, policy).iter_records(p))
    q = tmp_path / "y.csv"
    q.write_text("complaint_category,complaint_date\nPothole/Road Damage,2024-01-01\n", encoding="utf-8")
    with pytest.raises(SchemaMismatch, match="complaint_id"):
        list(make_adapter(card, policy).iter_records(q))
    rows = list(make_adapter(card, policy, row_index_ids=True).iter_records(q))
    assert [r.record_id for r in rows] == ["bmc_mumbai:row0"]


def test_pii_sensitive_unclassified_and_post_resolution_text_never_reach_the_prepared_output(prepared):
    out, m = prepared
    raw = (out / "records.jsonl").read_text(encoding="utf-8")
    for s in SENTINELS:
        assert s not in raw, s
    for key in ("complainant_age", "complainant_gender", "complainant_profile", "contractor_name", "resolution_remarks", "UNCLASSIFIED_SENTINEL_COL"):
        assert key not in raw, key
    cols = m["columns"]
    assert cols["unclassified_columns_default_denied"] == ["UNCLASSIFIED_SENTINEL_COL"]
    assert set(cols["pii_columns_never_read"]) == {"complainant_name", "contractor_name"}
    assert set(cols["sensitive_columns_never_stored"]) == {"complainant_age", "complainant_gender"}
    assert cols["post_resolution_text_never_stored"] == ["resolution_remarks"]


def test_citizen_satisfaction_values_are_not_copied_into_records(records):
    assert all("citizen_satisfied" not in r.attributes and "citizen_rating" not in r.attributes for r in records)


def test_description_is_never_stored_as_text_for_the_synthetic_bmc_source_and_confirmation_is_refused(card, policy):
    assert all(r.text is None and r.text_origin == "none" for r in make_adapter(card, policy).iter_records(BMC_CSV))
    with pytest.raises(SchemaMismatch, match="synthetic"):
        make_adapter(card, policy, confirm_citizen_text=True)


def test_citizen_text_machinery_still_requires_explicit_confirmation_on_a_hypothetical_real_source(card, policy):
    real = hypothetical_real_card(card)
    assert all(r.text is None for r in make_adapter(real, policy).iter_records(BMC_CSV))
    with_text = list(make_adapter(real, policy, confirm_citizen_text=True).iter_records(BMC_CSV))
    assert all(r.text and r.text_origin == "citizen_narrative" for r in with_text)
    assert all("Resolved:" not in r.text for r in with_text)               # remarks are a different, never-stored column


def test_department_on_the_canonical_record_is_never_filled_from_the_taxonomy(records):
    assert all(r.department is None for r in records)
    assert {r.source_agency for r in records} >= {"Roads Department", "Hydraulic Engineer"}      # the SOURCE value is kept, as source_agency only


def test_provenance_marks_the_data_as_third_party_synthetic_with_the_cc_by_licence_and_unknown_language(records):
    for r in records:
        p = r.provenance
        assert p.kind == "synthetic_third_party" and p.license_verified is True and p.origin_verified is True
        assert r.language is None
    assert all(r.record_id.startswith("bmc_mumbai:FMT-B") for r in records)


def test_resolution_hours_are_computed_only_from_two_timestamps_and_negative_durations_are_dropped(records, card, policy):
    done = [r for r in records if r.attributes.get("resolution_hours") is not None]
    assert done and all(r.closed_at and r.attributes["resolution_hours"] >= 0 for r in done)
    assert all(r.attributes.get("resolution_hours") is None for r in records if not r.closed_at)
    ad = make_adapter(card, policy)
    list(ad.iter_records(BMC_CSV))
    assert ad.stats["negative_duration"] == 1 and ad.stats["unresolved_no_closed_at"] > 0


def test_duration_column_requires_an_explicit_unit(card, policy, tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("complaint_id,complaint_category,complaint_date,resolution_time\nA,Pothole/Road Damage,2024-01-01,48\n", encoding="utf-8")
    rp = {"resolution_time": "resolution_duration"}
    ad = make_adapter(card, policy, role_map=rp)
    assert [r.attributes["resolution_hours"] for r in ad.iter_records(p)] == [None] and ad.stats["duration_unit_unknown"] == 1
    assert [r.attributes["resolution_hours"] for r in make_adapter(card, policy, role_map=rp, resolution_unit="days").iter_records(p)] == [1152.0]
    with pytest.raises(SchemaMismatch):
        make_adapter(card, policy, resolution_unit="weeks")


def test_unparseable_dates_fail_instead_of_silently_producing_a_dataset(card, policy, tmp_path):
    p = tmp_path / "bad.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["complaint_id", "complaint_category", "complaint_date"])
        for i in range(80):
            w.writerow([f"A{i}", "Pothole/Road Damage", "banana"])
    with pytest.raises(SchemaMismatch, match="unparseable created_at"):
        list(make_adapter(card, policy).iter_records(p))


def test_category_mapping_stays_taxonomy_native_and_out_of_scope_is_not_forced(records):
    by = {r.source_category: (r.category, r.subcategory, r.mapping_status) for r in records}
    assert by["Pothole/Road Damage"] == ("roads", None, "category_only")
    assert by["Street Light Failure"] == ("street_lighting", "light_not_working", "exact")
    assert by["Illegal Construction"][2] == "out_of_scope" and by["Noise/Air Pollution"][2] == "out_of_scope"
    assert {r.category for r in records} - {None} <= {"roads", "water_supply", "sanitation", "drainage_sewerage", "street_lighting", "traffic_encroachment", "parks_trees", "public_health"}


# ------------------------------------------------------------------ the task view is the only door; reads are default-deny
def _rec_dict():
    return {"record_id": "bmc_mumbai:X", "provenance": {"kind": "real_public", "source_id": "bmc_mumbai", "source_dataset": "x", "license_id": "L",
                                                         "license_verified": False, "origin_verified": False, "label_origin": "mapped_from_source"},
            "category": "roads", "mapping_status": "category_only", "department": None, "source_category": "Pothole/Road Damage", "status": "Closed",
            "attributes": {"severity": "High", "priority": "P1", "resolution_hours": 10.0}}


def test_task_view_exposes_exactly_the_allowed_roles(policy):
    rec = CaseRecord.model_validate(_rec_dict())
    for task, t in policy.tasks.items():
        if t.status == "not_pursued":
            continue
        v = policy.view(rec, task)
        assert set(v.inputs) == set(t.inputs) and set(v.targets) == set(t.targets)
    v = policy.view(rec, "triage_priority_prior")
    assert v.targets == {"severity": "High", "priority": "P1"} and "status" not in v.inputs


def test_reading_a_forbidden_role_for_a_task_raises(policy):
    rec = CaseRecord.model_validate(_rec_dict())
    for task, role in [("triage_priority_prior", "status"), ("triage_priority_prior", "resolution_hours"), ("intake_text", "source_category"),
                       ("routing_agreement", "severity"), ("recurrence_hotspot", "department"), ("taxonomy_coverage", "pii")]:
        with pytest.raises(LeakageError):
            policy.read(rec, task, role)
    assert policy.read(rec, "triage_priority_prior", "severity") == "High"


def test_views_clean_over_real_records(records, policy):
    assert views_clean(records, policy) == {"tasks_checked": len(policy.tasks), "violations": []}


# ------------------------------------------------------------------ runnable conditions
def test_conditional_tasks_report_why_they_cannot_run(policy):
    ok, why = policy.runnable("intake_text", {"description", "source_category"}, set())
    assert not ok and "description_is_citizen_text" in why[0]
    assert policy.runnable("intake_text", {"description", "source_category"}, {"description_is_citizen_text"}) == (True, [])
    ok, why = policy.runnable("fusion_pairs", {"created_at"})
    assert not ok and "duplicate_flag" in why[0]
    assert not policy.runnable("citizen_satisfaction", set())[0]


def test_prepare_marks_intake_unrunnable_for_synthetic_bmc_and_confirmable_only_on_a_hypothetical_real_source(card, tmp_path):
    m0 = prep.prepare_bmc(card, BMC_CSV, tmp_path / "a")
    assert m0["task_status"]["intake_text"]["runnable"] is False and m0["citizen_narrative_text_available"] is False
    with pytest.raises(SchemaMismatch):
        prep.prepare_bmc(card, BMC_CSV, tmp_path / "x", confirm_citizen_text=True)
    m1 = prep.prepare_bmc(hypothetical_real_card(card), BMC_CSV, tmp_path / "b", confirm_citizen_text=True)
    assert m1["citizen_narrative_text_available"] is True and m1["task_status"]["intake_text"]["runnable"] is True
    # ... and its audit then BLOCKS it: the fixture's descriptions echo the category on purpose
    assert m1["task_status"]["intake_text"]["audit"]["passed"] is False and any("echoes the label" in b for b in m1["task_status"]["intake_text"]["audit"]["blocking"])


# ------------------------------------------------------------------ leakage audits
def test_deterministic_targets_are_flagged_as_vacuous(records, policy):
    for task, tgt in [("routing_agreement", "department"), ("triage_priority_prior", "severity"), ("triage_priority_prior", "priority")]:
        d = target_determinism(records, policy, task, tgt)
        assert d["vacuous"] is True and d["purity"] >= 0.99, (task, tgt)


def test_target_determinism_is_not_vacuous_when_the_target_varies_within_input_groups(records, policy):
    import random
    rng = random.Random(1)
    noisy = [r.model_copy(update={"attributes": {**r.attributes, "severity": rng.choice(["Low", "Medium", "High"])}}) for r in records]
    d = target_determinism(noisy, policy, "triage_priority_prior", "severity", key_roles=["category"])
    assert d["vacuous"] is False and d["lift_over_baseline"] < 0.5


def test_audit_task_blocks_vacuous_targets_and_passes_non_deterministic_tasks(records, policy):
    a = audit_task(records, policy, "routing_agreement")
    assert a["passed"] is False and "deterministic" in a["blocking"][0]
    assert audit_task(records, policy, "resolution_time_prior")["passed"] is True
    assert "censoring_reported" in audit_task(records, policy, "resolution_time_prior")["checks"]


def test_text_echo_detects_label_leakage():
    def r(text):
        return CaseRecord.model_validate({**_rec_dict(), "text": text, "text_origin": "citizen_narrative"})
    rows = [r("Pothole/Road Damage near the school")] * 3 + [r("big hole outside my house")] * 17
    d = text_contains_label(rows)
    assert d["n_text_rows"] == 20 and d["echo_rate"] == 0.15 and d["blocking"] is True
    assert text_contains_label([r("big hole outside my house")] * 5)["blocking"] is False
    assert text_contains_label([CaseRecord.model_validate(_rec_dict())])["echo_rate"] is None


def test_split_straddle_and_spatiotemporal_twins_are_reported():
    base = _rec_dict()

    def c(i, split, lat, day):
        return CaseRecord.model_validate({**base, "record_id": f"bmc_mumbai:{i}", "split_hint": split, "latitude": lat, "longitude": 72.85,
                                          "created_at": f"2024-01-{day:02d}T09:00:00"})
    rows = [c(1, "train", 19.0, 3), c(2, "holdout", 19.0, 4), c(3, "holdout", 19.5, 4), c(4, "train", 19.2, 20)]
    st = spatiotemporal_straddle(rows)
    assert st["holdout_rows"] == 2 and st["holdout_rows_with_train_twin"] == 1 and st["share"] == 0.5
    sg = split_straddle(rows, lambda r: r.category)
    assert sg["n_groups"] == 1 and sg["straddling_groups"] == 1 and sg["straddle_share"] == 1.0


def test_censoring_is_reported_not_hidden(records):
    c = censoring_report(records)
    assert c["n"] == 120 and c["with_resolution_time"] == 83 and c["censored_share"] == round(37 / 120, 4)
    assert "censored" in c["note"]


def test_recurrence_audit_declares_split_straddle(policy):
    assert policy.tasks["recurrence_hotspot"].leakage_checks == ["split_straddle"]


# ------------------------------------------------------------------ prepared manifest honesty
def test_manifest_is_honest_about_synthetic_origin_licence_identity_and_text(prepared):
    out, m = prepared
    assert m["license_verified"] is True and m["origin_status"] == "SYNTHETIC_PER_COMPETITION" and m["source_kind"] == "synthetic_third_party" and m["origin_notes"]
    assert m["citizen_narrative_text_available"] is False and m["text_origin_counts"] == {"none": 120}
    assert m["views_clean"]["violations"] == [] and m["split_counts"] == {"train": 56, "holdout": 64}
    assert "NOT permitted" in m["redistribution"] and m["column_policy"]["status"].startswith("DRAFT")
    assert m["task_status"]["citizen_satisfaction"]["runnable"] is False and m["task_status"]["demo_seed"]["runnable"] is True
    assert m["task_status"]["routing_agreement"]["audit"]["passed"] is False
    recs = [CaseRecord.model_validate(r) for r in read_jsonl(out / "records.jsonl")]
    assert len(recs) == m["records"] == 120


def test_since_until_filter_and_reservoir_sampling_are_applied(card, policy):
    a = list(make_adapter(card, policy).iter_records(BMC_CSV, since="2024-02-01"))
    assert a and all(r.created_at[:10] >= "2024-02-01" for r in a) and len(a) < 120
    s1 = [r.record_id for r in make_adapter(card, policy).iter_records(BMC_CSV, max_rows=20, sample_seed=1)]
    s2 = [r.record_id for r in make_adapter(card, policy).iter_records(BMC_CSV, max_rows=20, sample_seed=1)]
    assert s1 == s2 and len(s1) == 20


# ------------------------------------------------------------------ evaluation plumbing (descriptive track)
def rows_of(prepared):
    return read_jsonl(prepared[0] / "records.jsonl")


def test_resolution_time_prior_reports_censoring_inputs_used_and_never_reads_forbidden_roles(prepared):
    r = eval_real.evaluate_resolution_time_prior(rows_of(prepared))
    blob = json.dumps(r)
    assert r["overall"]["n"] > 0 and "median_h" in r["overall"]
    assert "status" not in r["inputs_used"] and "resolution_remarks" not in r["inputs_used"]
    assert {"resolution_remarks", "status", "pii", "complainant_profile"} <= set(r["roles_never_read"])     # role NAMES, listed as not read
    assert not any(s in blob for s in SENTINELS)
    assert r["leakage"]["passed"] is True and r["censoring"]["censored_share"] > 0


def test_resolution_time_prior_refuses_when_there_are_no_durations(prepared):
    rows = [{**x, "attributes": {k: v for k, v in x["attributes"].items() if k != "resolution_hours"}} for x in rows_of(prepared)]
    with pytest.raises(Exception, match="no resolution durations"):
        eval_real.evaluate_resolution_time_prior(rows)


def test_routing_and_triage_evaluations_surface_the_vacuity_blocker_instead_of_a_score(prepared):
    for fn in (eval_real.evaluate_routing_agreement, eval_real.evaluate_triage_priority_prior):
        r = fn(rows_of(prepared))
        assert r["leakage"]["passed"] is False and r["leakage"]["blocking"]


def test_recurrence_hotspot_runs_and_reports_only_descriptives(prepared):
    r = eval_real.evaluate_recurrence_hotspot(rows_of(prepared))
    assert "inputs_used" in r and "status" not in r["inputs_used"] and "department" not in r["inputs_used"]


def test_run_eval_cli_puts_bmc_on_the_synthetic_track_and_never_allows_a_real_world_claim(prepared, tmp_path, capsys):
    out = tmp_path / "rep"
    rc = run_eval.main(["--task", "resolution_time_prior", "--real-data", str(prepared[0] / "records.jsonl"), "--out", str(out), "--name", "bmc"])
    assert rc == 0
    rep = json.loads((out / "bmc.json").read_text(encoding="utf-8"))
    assert rep["track"] == "synthetic" and rep["claims"]["real_world_accuracy_claim_allowed"] is False
    assert "THIRD-PARTY SYNTHETIC" in rep["claims"]["banner"] and "not real-world" in rep["claims"]["banner"]
    assert rep["provenance"]["kinds"] == {"synthetic_third_party": 120}
    assert "synthetic_third_party" in (out / "bmc.md").read_text(encoding="utf-8")
    assert run_eval.main(["--task", "resolution_time_prior", "--track", "real_holdout", "--real-data", str(prepared[0] / "records.jsonl"), "--out", str(out)]) == 2
    assert run_eval.main(["--task", "taxonomy_coverage", "--real-data", str(prepared[0] / "records.jsonl"), "--out", str(out), "--name", "cov"]) == 0
    cov = json.loads((out / "cov.json").read_text(encoding="utf-8"))
    assert cov["track"] == "descriptive" and "THIRD-PARTY SYNTHETIC" in cov["claims"]["banner"]


def test_third_party_synthetic_is_never_mixed_with_project_synthetic_real_or_hybrid_reports():
    from ai.evaluation.provenance import TrackError, validate_track
    tp = {"kinds": {"synthetic_third_party": 5}}
    validate_track("synthetic", tp)
    validate_track("descriptive", tp)
    for track, kinds in [("synthetic", {"synthetic_third_party": 5, "synthetic": 5}), ("synthetic", {"synthetic_third_party": 5, "real_public": 5}),
                         ("real_holdout", {"synthetic_third_party": 5}), ("hybrid", {"synthetic_third_party": 5, "real_public": 5}),
                         ("hybrid", {"synthetic_third_party": 5, "synthetic": 5}), ("descriptive", {"synthetic_third_party": 5, "real_public": 5})]:
        with pytest.raises(TrackError):
            validate_track(track, {"kinds": kinds}, rows=[])


def test_project_synthetic_still_cannot_be_evaluated_as_third_party_and_banners_differ():
    from ai.evaluation.provenance import claims_for
    ours = {"n": 3, "kinds": {"synthetic": 3}, "sources": {"synthetic_civic": {"kind": "synthetic", "n": 3, "license_verified": True}}}
    theirs = {"n": 3, "kinds": {"synthetic_third_party": 3}, "sources": {"bmc_mumbai": {"kind": "synthetic_third_party", "n": 3, "license_verified": False}}}
    assert claims_for("synthetic", ours)["banner"].startswith("SYNTHETIC DATA ONLY")
    c = claims_for("synthetic", theirs)
    assert c["banner"].startswith("THIRD-PARTY SYNTHETIC DATA") and any("licence not verified" in r for r in c["reasons"]) and c["real_world_accuracy_claim_allowed"] is False


def test_unverified_origin_blocks_a_real_claim_even_with_verified_licence_and_enough_rows():
    src = {"kind": "real_public", "license_verified": True, "origin_verified": False, "n": 5000, "label_origins": {"mapped_from_source": 5000}, "text_origins": {}}
    prov = {"n": 5000, "kinds": {"real_public": 5000}, "sources": {"bmc_mumbai": src}}
    c = claims_for("real_holdout", prov)
    assert c["real_world_accuracy_claim_allowed"] is False and any("origin not verified" in r for r in c["reasons"])
    assert claims_for("hybrid", {**prov, "kinds": {"real_public": 5000, "synthetic": 10},
                                "sources": {**prov["sources"], "synthetic_civic": {"kind": "synthetic", "n": 10, "license_verified": True, "label_origins": {}, "text_origins": {}}}}
                      )["real_slice_claim"]["allowed"] is False
    ok = {**prov, "sources": {"bmc_mumbai": {**src, "origin_verified": True}}}
    assert claims_for("real_holdout", ok)["real_world_accuracy_claim_allowed"] is True


# ------------------------------------------------------------------ profile + CLI
def test_profile_bmc_reports_roles_runnable_tasks_and_determinism_without_values(card, policy):
    rep = profile_bmc(BMC_CSV, policy, None, MappingTable.load(card.mapping_id), DepartmentMapping.load("bmc_mumbai_departments"))
    assert rep["rows_profiled"] == 120 and rep["unclassified_columns_default_denied"] == ["UNCLASSIFIED_SENTINEL_COL"]
    assert set(rep["pii_columns_never_read"]) == {"complainant_name", "contractor_name"}
    assert set(rep["sensitive_columns_never_read"]) == {"complainant_age", "complainant_gender"}
    assert rep["tasks_runnable_given_columns"]["intake_text"]["runnable"] is False
    blob = json.dumps(rep)
    assert "INVENTED PERSON" not in blob and "INVENTED CONTRACTOR" not in blob


def test_cli_profile_and_prepare_and_leakage_audit_and_matrix(tmp_path, capsys):
    rp = tmp_path / "profile.json"
    assert cli.main(["profile", "bmc_mumbai", "--input", str(BMC_CSV), "--out", str(rp)]) == 0
    assert "UNCLASSIFIED_SENTINEL_COL" in capsys.readouterr().out
    args = ["prepare", "bmc_mumbai", "--input", str(BMC_CSV), "--out", str(tmp_path / "prep")]
    assert cli.main(args) == 2 and "--accept-terms bmc_mumbai" in capsys.readouterr().err        # terms gate
    assert cli.main([*args, "--accept-terms", "bmc_mumbai"]) == 0      # licence verified (CC BY 4.0 per the Rules): the terms acceptance is enough
    capsys.readouterr()
    assert cli.main([*args, *ACCEPT, "--holdout-after", "2024-03-01", "--confirm-citizen-text"]) == 2 and "synthetic" in capsys.readouterr().err
    assert cli.main([*args, *ACCEPT, "--holdout-after", "2024-03-01"]) == 0
    m = json.loads((tmp_path / "prep" / "PREPARE_MANIFEST.json").read_text(encoding="utf-8"))
    assert m["source_kind"] == "synthetic_third_party" and m["records"] == 120
    assert cli.main(["matrix"]) == 0 and "bmc_mumbai" in capsys.readouterr().out


def test_cli_leakage_audit_exits_nonzero_on_a_blocked_dataset(prepared, capsys):
    assert cli.main(["leakage-audit", "--records", str(prepared[0] / "records.jsonl"), "--source", "bmc_mumbai"]) == 3
    out = capsys.readouterr().out
    assert "routing_agreement: BLOCKED" in out and "resolution_time_prior: PASS" in out


def test_cli_rejects_unknown_role_map_roles(tmp_path, capsys):
    rm = tmp_path / "rm.json"
    rm.write_text(json.dumps({"ward": "not_a_role"}), encoding="utf-8")
    rc = cli.main(["profile", "bmc_mumbai", "--input", str(BMC_CSV), "--out", str(tmp_path / "p.json"), "--role-map", str(rm)])
    assert rc == 2 and "unknown roles" in capsys.readouterr().err


# ================================================================== real BMC column names (from the actual data dictionary)
REAL_HEADERS = ["complaint_id", "complaint_date", "year", "month", "is_monsoon_season", "complaint_time_of_day", "ward_code", "ward_area", "zone", "ward_type",
                "population_density", "ward_slum_percentage", "complaint_category", "department_assigned", "complaint_channel", "severity", "has_photo_evidence",
                "has_gps_location", "media_attention", "politically_sensitive", "complainant_type", "property_type", "repeat_complainant", "prior_complaints_count",
                "resolution_days", "num_reassignments", "complaint_status", "contractor_category", "work_quality_rating", "site_inspected", "defect_liability_claim",
                "estimated_cost_inr", "infrastructure_age_years", "months_since_last_maintained", "citizen_satisfied"]


def test_the_real_data_dictionary_headers_resolve_to_safe_roles(policy):
    res = policy.classify_headers(REAL_HEADERS)
    assert res.columns["department"] == "department_assigned" and policy.roles["department"].phase == "post_triage"
    assert res.columns["status"] == "complaint_status" and res.columns["resolution_duration"] == "resolution_days"
    assert res.columns["citizen_satisfied"] == "citizen_satisfied" and res.sensitive_ignored == ["complainant_type"] and res.pii_ignored == []
    for denied in ("repeat_complainant", "prior_complaints_count", "media_attention", "politically_sensitive", "estimated_cost_inr", "work_quality_rating", "ward_area"):
        assert denied in res.unclassified, denied                                                    # not claimed by any role: unavailable to every task
    for t, spec in policy.tasks.items():
        if spec.purpose != "demo":
            assert not {"status", "resolution_duration", "resolution_hours", "citizen_satisfied", "reassigned"} & set(spec.inputs), t
        if spec.purpose != "demo" and t != "resolution_time_prior":            # only the resolution-time prior may take the post-triage department as an input
            assert "department" not in spec.inputs, t
    assert "department" in policy.tasks["routing_agreement"].targets and "department" not in policy.tasks["routing_agreement"].inputs


def test_a_dataset_without_coordinates_reports_recurrence_as_not_computable_not_as_an_empty_success(tmp_path):
    import csv
    f = tmp_path / "x.csv"
    rows = list(csv.DictReader(BMC_CSV.open(encoding="utf-8")))
    with f.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[h for h in rows[0] if h not in ("latitude", "longitude")])
        w.writeheader()
        for r in rows:
            w.writerow({k: v for k, v in r.items() if k not in ("latitude", "longitude")})
    out = tmp_path / "prep"
    prep.prepare_bmc(load_card("bmc_mumbai"), f, out, retrieved_at="2026-10-02")
    res = eval_real.evaluate_recurrence_hotspot(read_jsonl(out / "records.jsonl"))
    assert res["computable"] is False and "no complaint has usable coordinates" in res["reason"] and res["ward_category_counts_top10"]
    assert "n_recurrent_cells" not in res and "NOT a recurrence/hotspot result" in res["interpretation"]
