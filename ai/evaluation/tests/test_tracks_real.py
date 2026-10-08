"""Evaluation tracks: provenance labelling, claim policy and real-data evaluations (format fixtures only)."""
import json

import pytest

from ai.evaluation import eval_real, run_eval
from ai.evaluation.provenance import MIN_REAL_N, TrackError, build_provenance, claims_for, row_provenance, validate_track
from ai.inference.intake.service import IntakeService
from ai.inference.providers.fake import FakeProvider
from ai.training.src.data_sources import cli as ds_cli
from ai.training.tests.conftest_real import NYC_CSV, make_chicago_rows, make_rdd_tree
from ai.training.tests.optional_deps import requires_scipy, requires_sklearn

DS = run_eval.HERE / "datasets"
ACK = ["--acknowledge-unverified-license"]


def real_row(**kw):
    base = {"record_id": "r", "provenance": {"kind": "real_public", "source_id": "nyc311", "source_dataset": "NYC", "license_id": "L", "license_verified": False,
                                              "label_origin": "mapped_from_source", "mapping_id": "m", "mapping_version": "0"},
            "text": None, "text_origin": "none", "split_hint": "holdout", "category": "roads", "subcategory": "pothole"}
    return {**base, **kw}


def synth_rows():
    return run_eval.read_jsonl(DS / "intake_eval.v1.jsonl")[:5]


# ------------------------------------------------------------------ provenance
def test_legacy_synthetic_rows_and_canonical_rows_both_get_provenance():
    assert row_provenance(synth_rows()[0])["kind"] == "synthetic"
    assert row_provenance(real_row())["source_id"] == "nyc311"
    with pytest.raises(TrackError, match="unlabeled"):
        row_provenance({"text": "x", "category": "roads"})


def test_provenance_summary():
    p = build_provenance(synth_rows() + [real_row(), real_row()])
    assert p["n"] == 7 and p["kinds"] == {"synthetic": 5, "real_public": 2}
    assert p["sources"]["nyc311"]["n"] == 2 and p["sources"]["nyc311"]["license_verified"] is False and p["sources"]["synthetic_civic"]["license_verified"]


def test_tracks_reject_the_wrong_kind_of_data():
    syn, real = build_provenance(synth_rows()), build_provenance([real_row()])
    validate_track("synthetic", syn)
    with pytest.raises(TrackError, match="synthetic track received"):
        validate_track("synthetic", real)
    with pytest.raises(TrackError, match="requires only real_public"):
        validate_track("real_holdout", syn)
    with pytest.raises(TrackError, match="needs both"):
        validate_track("hybrid", real)
    validate_track("hybrid", build_provenance(synth_rows() + [real_row()]))
    with pytest.raises(TrackError):
        validate_track("bogus", syn)


def test_real_holdout_never_scores_training_rows():
    rows = [real_row(split_hint="train")]
    with pytest.raises(TrackError, match="holdout"):
        validate_track("real_holdout", build_provenance(rows), rows=rows)
    ok = [real_row()]
    validate_track("real_holdout", build_provenance(ok), rows=ok)


def test_real_intake_track_refuses_rows_without_citizen_narrative():
    for origin, text in (("none", None), ("source_category_text", "Street Condition - Pothole")):
        rows = [real_row(text=text, text_origin=origin)]
        with pytest.raises(TrackError, match="citizen narrative"):
            validate_track("real_holdout", build_provenance(rows), task="intake", rows=rows)
    rows = [real_row(text="a pothole", text_origin="citizen_narrative")]
    validate_track("real_holdout", build_provenance(rows), task="intake", rows=rows)


def test_claim_policy():
    syn = claims_for("synthetic", build_provenance(synth_rows()))
    assert syn["real_world_accuracy_claim_allowed"] is False and "SYNTHETIC" in syn["banner"]
    few = claims_for("real_holdout", build_provenance([real_row() for _ in range(10)]))
    assert few["real_world_accuracy_claim_allowed"] is False and any(str(MIN_REAL_N) in r for r in few["reasons"]) and any("licence" in r for r in few["reasons"])
    verified = [real_row(provenance={**real_row()["provenance"], "license_verified": True}) for _ in range(MIN_REAL_N)]
    ok = claims_for("real_holdout", build_provenance(verified))
    assert ok["real_world_accuracy_claim_allowed"] is True and "not ground truth" in ok["scope"] and "mapped_from_source" in ok["scope"]
    unver = claims_for("real_holdout", build_provenance([real_row() for _ in range(MIN_REAL_N)]))
    assert unver["real_world_accuracy_claim_allowed"] is False and any("not verified" in r for r in unver["reasons"])
    hy = claims_for("hybrid", build_provenance(synth_rows() + verified))
    assert hy["real_world_accuracy_claim_allowed"] is False and hy["pooled_headline_allowed"] is False and hy["real_slice_claim"]["allowed"] is True
    d = claims_for("descriptive", build_provenance([real_row()]))
    assert d["real_world_accuracy_claim_allowed"] is False and "not model performance" in d["banner"]


# ------------------------------------------------------------------ real-data evaluations
@pytest.fixture
def chicago_prepared(tmp_path):
    src = make_chicago_rows(tmp_path / "chi.jsonl", n_dups=40)
    assert ds_cli.main(["prepare", "chicago311", "--input", str(src), "--out", str(tmp_path / "prep"), "--holdout-after", "2025-09-10",
                        "--accept-terms", "chicago311", *ACK]) == 0
    assert ds_cli.main(["pairs", "--records", str(tmp_path / "prep" / "records.jsonl"), "--out", str(tmp_path / "pairs")]) == 0
    return tmp_path


def test_taxonomy_coverage_reports_gaps_that_synthetic_data_must_fill(tmp_path):
    assert ds_cli.main(["prepare", "nyc311", "--input", str(NYC_CSV), "--out", str(tmp_path / "p"), "--accept-terms", "nyc311", *ACK]) == 0
    rows = run_eval.read_jsonl(tmp_path / "p" / "records.jsonl")
    r = eval_real.evaluate_taxonomy_coverage(rows)
    assert r["n"] == 12 and r["mapped_to_subcategory_share"] == 0.75 and r["mapped_any_share"] == round(10 / 12, 4)
    assert "pothole" in str(r["subcategory_distribution"]) and "sanitation/dead_animal" in r["taxonomy_subcategories_with_no_real_examples"]
    assert r["top_unmapped_source_labels"][0][0].startswith("Totally New") and "not a model-accuracy" in r["interpretation"]


def test_real_fusion_report_end_to_end_via_cli(chicago_prepared, tmp_path, capsys):
    pairs = chicago_prepared / "pairs" / "pairs.jsonl"
    out = tmp_path / "rep"
    assert run_eval.main(["--task", "fusion", "--track", "real_holdout", "--real-data", str(pairs), "--out", str(out), "--name", "real_fusion"]) == 0
    rep = json.loads((out / "real_fusion.json").read_text(encoding="utf-8"))
    assert rep["track"] == "real_holdout" and rep["provenance"]["kinds"] == {"real_public": rep["provenance"]["n"]}
    assert rep["claims"]["real_world_accuracy_claim_allowed"] is False                     # unverified licence + small n
    assert rep["results"]["real_data_notes"]["semantic_signal"].startswith("not evaluated") and rep["results"]["auc_roc"] > 0.8
    md = (out / "real_fusion.md").read_text(encoding="utf-8")
    assert "REAL PUBLIC DATA HOLDOUT" in md and "chicago311" in md and "NO" in md and "SYNTHETIC DATA ONLY" not in md


def test_hybrid_report_keeps_slices_separate_and_never_pools(chicago_prepared, tmp_path):
    out = tmp_path / "rep"
    pairs = chicago_prepared / "pairs" / "pairs.jsonl"
    assert run_eval.main(["--task", "fusion", "--track", "hybrid", "--real-data", str(pairs), "--out", str(out), "--name", "h"]) == 0
    rep = json.loads((out / "h.json").read_text(encoding="utf-8"))
    assert set(rep["results"]["by_provenance"]) == {"synthetic", "real_public"} and "pooled" not in rep["results"]
    assert rep["claims"]["pooled_headline_allowed"] is False and set(rep["provenance"]["kinds"]) == {"synthetic", "real_public"}
    assert rep["results"]["by_provenance"]["synthetic"]["semantic_source"] == "lexical"
    md = (out / "h.md").read_text(encoding="utf-8")
    assert "Slice: synthetic" in md and "Slice: real_public" in md and "no pooled headline" in md


def test_real_holdout_refuses_unprepared_or_training_rows(chicago_prepared, tmp_path, capsys):
    recs = chicago_prepared / "prep" / "records.jsonl"
    # records have split hints -> but a raw file with NO holdout rows must be refused
    nohold = tmp_path / "nohold.jsonl"
    nohold.write_text("\n".join(json.dumps({**json.loads(l), "split_hint": "train"}) for l in recs.read_text(encoding="utf-8").splitlines()[:5]), encoding="utf-8")
    rc = run_eval.main(["--task", "fusion", "--track", "real_holdout", "--real-data", str(nohold), "--out", str(tmp_path / "o")])
    assert rc == 2 and "holdout" in capsys.readouterr().err and not (tmp_path / "o").exists()


def test_real_intake_cli_is_refused_for_311_data(chicago_prepared, tmp_path, capsys):
    recs = chicago_prepared / "prep" / "records.jsonl"
    rc = run_eval.main(["--task", "intake", "--track", "real_holdout", "--real-data", str(recs), "--system", "provider", "--out", str(tmp_path / "o")])
    assert rc == 2 and "citizen narrative" in capsys.readouterr().err


def test_synthetic_track_rejects_real_data_and_requires_real_data_flag(chicago_prepared, tmp_path, capsys):
    assert run_eval.main(["--task", "fusion", "--track", "real_holdout", "--out", str(tmp_path / "o")]) == 2
    assert "--real-data is required" in capsys.readouterr().err


def test_taxonomy_coverage_cli_labels_itself_descriptive(chicago_prepared, tmp_path):
    out = tmp_path / "rep"
    assert run_eval.main(["--task", "taxonomy_coverage", "--real-data", str(chicago_prepared / "prep" / "records.jsonl"), "--out", str(out), "--name", "cov"]) == 0
    rep = json.loads((out / "cov.json").read_text(encoding="utf-8"))
    assert rep["track"] == "descriptive" and rep["claims"]["real_world_accuracy_claim_allowed"] is False and "not model performance" in rep["claims"]["banner"]


def test_existing_synthetic_reports_now_carry_provenance_and_claims():
    reports = run_eval.HERE / "reports"
    for name in ("intake_b0_local", "fusion_calibrated_lexical", "fusion_prior_lexical"):
        rep = json.loads((reports / f"{name}.json").read_text(encoding="utf-8"))
        assert rep["track"] == "synthetic" and rep["provenance"]["kinds"] and rep["claims"]["real_world_accuracy_claim_allowed"] is False
        assert "SYNTHETIC" in rep["claims"]["banner"] and rep["provenance"]["sources"]["synthetic_civic"]["license_verified"] is True
        assert "SYNTHETIC DATA ONLY" in (reports / f"{name}.md").read_text(encoding="utf-8")


# ------------------------------------------------------------------ vision (RDD2022) with a scripted provider
def rdd_records(tmp_path):
    root = make_rdd_tree(tmp_path / "RDD")
    assert ds_cli.main(["prepare", "rdd2022", "--input", str(root), "--out", str(tmp_path / "rp"), "--holdout-countries", "India", "Japan", "Czech Republic",
                        "--accept-terms", "rdd2022", *ACK]) == 0
    return root, run_eval.read_jsonl(tmp_path / "rp" / "records.jsonl")


INTAKE_POTHOLE = {"title": "t", "description": "d", "category": "roads", "subcategory": "pothole", "severity": "LOW", "language": "en", "transcript": None,
                  "confidence": 0.9, "reasons": [], "image_observations": ["hole in the road"]}


def test_vision_evaluation_scores_provider_answers_against_mapped_annotations(tmp_path):
    root, recs = rdd_records(tmp_path)
    svc = IntakeService(FakeProvider(structured={"intake": INTAKE_POTHOLE}))
    r = eval_real.evaluate_vision(svc, recs, root, max_per_country=10)
    assert r["n"] == 5 and r["validity"] == "ok" and r["degraded_rate"] == 0.0
    # provider always says "pothole": recall 1.0 on the 2 pothole images (India IN_1, Czech IN_1), precision 2/5
    assert r["overall"]["pothole_recall"] == 1.0 and r["overall"]["pothole_precision"] == 0.4 and r["by_country"]["Japan"]["pothole_precision"] == 0.0
    assert r["by_country"]["India"]["n"] == 2 and "cracks have no taxonomy subcategory" in r["caveat"]


def test_vision_flags_invalid_runs_when_the_provider_degrades(tmp_path):
    from ai.inference.errors import ProviderUnavailable
    root, recs = rdd_records(tmp_path)
    svc = IntakeService(FakeProvider(structured={"intake": ProviderUnavailable("down")}))
    assert eval_real.evaluate_vision(svc, recs, root)["validity"].startswith("INVALID")


def test_vision_needs_a_provider_and_images(tmp_path, capsys):
    root, recs = rdd_records(tmp_path)
    with pytest.raises(TrackError, match="provider"):
        eval_real.evaluate_vision(IntakeService(None), recs, root)
    for env in ("OPENAI_API_KEY", "AI_INTAKE_MODEL"):
        import os
        os.environ.pop(env, None)
    rc = run_eval.main(["--task", "vision", "--track", "real_holdout", "--real-data", str(tmp_path / "rp" / "records.jsonl"), "--image-root", str(root),
                        "--system", "provider", "--out", str(tmp_path / "o")])
    assert rc == 2 and "SKIPPED" in capsys.readouterr().err and not (tmp_path / "o").exists()


def test_intake_real_guard():
    with pytest.raises(TrackError):
        eval_real.evaluate_intake_real(IntakeService(None), [real_row()])


@requires_scipy
@requires_sklearn
def test_real_fusion_calibration_labels_weights_as_real_with_provenance(chicago_prepared, tmp_path):
    from ai.inference.fusion.scoring import FusionWeights
    from ai.training.src import train_fusion_calibrator as C
    pairs = run_eval.read_jsonl(chicago_prepared / "pairs" / "pairs.jsonl")
    tr, va = tmp_path / "tr.jsonl", tmp_path / "va.jsonl"
    tr.write_text("\n".join(json.dumps(p) for i, p in enumerate(pairs) if i % 3), encoding="utf-8")
    va.write_text("\n".join(json.dumps(p) for i, p in enumerate(pairs) if not i % 3), encoding="utf-8")
    out = C.run(None, tmp_path / "fw", train_pairs=tr, val_pairs=va, data_kind="real")
    w = FusionWeights.load(out)
    doc = json.loads((out / "fusion_weights.json").read_text(encoding="utf-8"))
    assert w.status == "calibrated_real" and doc["synthetic_data"] is False and doc["trained_on"]["sources"]["chicago311"]["license_verified"] is False
    assert min(w.semantic, w.geospatial, w.temporal, w.category) >= 0 and any("REAL agency-linked" in x for x in doc["limitations"])
    with pytest.raises(SystemExit):
        C.run(None, tmp_path / "x", data_kind="real")                       # needs real pairs
    synthetic_pairs = tmp_path / "s.jsonl"
    synthetic_pairs.write_text(json.dumps({"provenance": {"kind": "synthetic"}}) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="real_public"):
        C.run(None, tmp_path / "y", train_pairs=synthetic_pairs, val_pairs=synthetic_pairs, data_kind="real")


def test_service_treats_real_calibration_as_calibrated():
    from datetime import datetime, timezone

    from ai.inference.fusion.scoring import FusionWeights
    from ai.inference.fusion.service import FusionService
    from ai.inference.schemas import FusionCase, FusionRequest
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    mk = lambda i, lat: FusionCase(case_id=i, category="roads", latitude=lat, longitude=72.0, created_at=now)  # noqa: E731
    w = FusionWeights(-3, 0, 4, 1, 2, status="calibrated_real", version="v")
    r = FusionService(weights=w).analyze(FusionRequest(subject=mk("s", 19.0), candidates=[mk("c", 19.0001)]))
    assert not any(x.startswith("FUSION_UNCALIBRATED_PRIOR") for x in r.warnings)
