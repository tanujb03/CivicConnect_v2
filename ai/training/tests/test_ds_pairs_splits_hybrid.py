import pytest

from ai.evaluation import eval_fusion
from ai.training.src.data_sources.adapters.chicago311 import Chicago311Adapter
from ai.training.src.data_sources.adapters.nyc311 import NYC311Adapter
from ai.training.src.data_sources.adapters.synthetic import from_synthetic_row
from ai.training.src.data_sources.canonical import CaseRecord, Provenance
from ai.training.src.data_sources.card_schema import load_card
from ai.training.src.data_sources.hybrid import HybridDataError, build_hybrid_training_set, eligible_real_text
from ai.training.src.data_sources.mapping import MappingTable
from ai.training.src.data_sources.pairs import build_pairs_from_parent_links
from ai.training.src.data_sources.splits import (
    grid_cell,
    group_holdout,
    hash_fraction,
    spatial_cell_group,
    spatial_holdout,
    time_holdout,
)
from ai.training.src.synthetic import generator as gen

from .conftest_real import CHI_JSONL, NYC_CSV, make_chicago_rows


def chi_records(path=CHI_JSONL):
    return list(Chicago311Adapter(load_card("chicago311"), MappingTable.load("chicago311_to_civic")).iter_records(path))


# ------------------------------------------------------------------ pairs
def test_pairs_from_agency_links_have_expected_structure():
    recs = chi_records()
    pairs, stats = build_pairs_from_parent_links(recs, neg_per_pos=1, seed=1)
    assert stats["duplicate_flagged"] == 4 and stats["parent_missing"] == 1 and stats["positives"] == 3 and stats["negatives"] == 3
    pos = [p for p in pairs if p.label == 1]
    assert {p.pair_type for p in pos} == {"agency_linked_duplicate"} and all(p.provenance.kind == "real_public" for p in pairs)
    assert all(p.a.text is None and p.b.text is None for p in pairs)             # no narrative text exists: no leakage possible
    assert all(p.provenance.label_origin == "source_category" for p in pairs)
    for p in pairs:
        assert p.a.category == p.b.category                                       # same mapped category (gate-compatible)


def test_negatives_are_nearby_in_window_same_type_and_never_linked():
    from datetime import datetime

    from ai.inference.fusion.similarity import haversine_m
    recs = chi_records()
    links = {frozenset((r.record_id, r.parent_record_id)) for r in recs if r.parent_record_id}
    dup_ids = {r.record_id for r in recs if r.duplicate_flag}
    pairs, _ = build_pairs_from_parent_links(recs, neg_per_pos=2, seed=2)
    for p in (x for x in pairs if x.label == 0):
        assert frozenset((p.a.case_id, p.b.case_id)) not in links and p.b.case_id not in dup_ids
        assert haversine_m(p.a.latitude, p.a.longitude, p.b.latitude, p.b.longitude) <= 150
        assert abs((datetime.fromisoformat(p.a.created_at) - datetime.fromisoformat(p.b.created_at)).days) <= 30
    assert len(pairs) == len({p.pair_id for p in pairs})


def test_pair_building_is_deterministic_and_handles_files_without_duplicate_information():
    recs = chi_records()
    a, _ = build_pairs_from_parent_links(recs, seed=5)
    b, _ = build_pairs_from_parent_links(recs, seed=5)
    assert [p.model_dump() for p in a] == [p.model_dump() for p in b]
    nyc_recs = list(NYC311Adapter(load_card("nyc311"), MappingTable.load("nyc311_to_civic")).iter_records(NYC_CSV))
    pairs, stats = build_pairs_from_parent_links(nyc_recs)
    assert pairs == [] and stats["positives"] == 0


def test_real_pairs_flow_into_the_fusion_evaluation():
    pairs, _ = build_pairs_from_parent_links(chi_records(), seed=1)
    res = eval_fusion.evaluate([p.model_dump(mode="json") for p in pairs])
    assert res["n_pairs"] == 6 and res["n_gated_in"] == 6 and res["gate_recall_of_true_duplicates"] == 1.0 and res["auc_roc"] > 0.9


def test_agency_links_that_cross_categories_are_kept_so_the_gate_miss_is_measured(tmp_path):
    p = tmp_path / "c.jsonl"
    rows = [{"sr_number": "P", "sr_type": "Pothole in Street Complaint", "created_date": "2025-09-01T00:00:00", "latitude": "41.9", "longitude": "-87.6"},
            {"sr_number": "C", "sr_type": "Street Light Out Complaint", "created_date": "2025-09-02T00:00:00", "latitude": "41.9", "longitude": "-87.6",
             "duplicate": "true", "parent_sr_number": "P"}]
    import json
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    pairs, stats = build_pairs_from_parent_links(chi_records(p))
    assert stats["positives"] == 1 and stats["positives_category_differs"] == 1
    res = eval_fusion.evaluate([x.model_dump(mode="json") for x in pairs])
    assert res["gate_recall_of_true_duplicates"] == 0.0           # our same-category gate would miss it: a real finding


# ------------------------------------------------------------------ splits
def test_time_holdout_and_group_holdout():
    recs = chi_records()
    out = time_holdout(recs, "2025-09-05")
    assert {r.split_hint for r in out if r.created_at[:10] >= "2025-09-05"} == {"holdout"} and {r.split_hint for r in out if r.created_at[:10] < "2025-09-05"} == {"train"}
    grp = group_holdout(recs, lambda r: r.place, {"21"})
    assert {r.split_hint for r in grp} == {"holdout"}
    assert group_holdout(recs, lambda r: None, {"x"})[0].split_hint is None


def test_spatial_holdout_keeps_whole_cells_together_and_is_deterministic():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        recs = chi_records(make_chicago_rows(Path(d) / "c.jsonl", n_dups=40))
    out = spatial_holdout(recs, 0.3, seed=1)
    by_cell: dict = {}
    for r in out:
        by_cell.setdefault(spatial_cell_group(r), set()).add(r.split_hint)
    assert all(len(v) == 1 for v in by_cell.values()) and {"train", "holdout"} <= {s for v in by_cell.values() for s in v}
    assert [r.split_hint for r in out] == [r.split_hint for r in spatial_holdout(recs, 0.3, seed=1)]
    assert 0 <= hash_fraction("x", 1) < 1 and grid_cell(41.88, -87.63) == grid_cell(41.8804, -87.6304) != grid_cell(41.99, -87.63)


# ------------------------------------------------------------------ hybrid assembly
def real_text_record(i, **kw):
    base = dict(record_id=f"real:{i}", provenance=Provenance(kind="real_public", source_id="partner", source_dataset="Partner", license_id="L", license_verified=True,
                                                               label_origin="human_annotated"),
                text="pothole near school", text_origin="citizen_narrative", category="roads", subcategory="pothole", mapping_status="exact", split_hint="train")
    return CaseRecord(**{**base, **kw})


def synth(n=30):
    return [from_synthetic_row(r) for r in gen.generate_intake_split("train", 1, 3)[:n]]


def test_hybrid_requires_genuine_real_narrative_text():
    cat_text = list(NYC311Adapter(load_card("nyc311"), MappingTable.load("nyc311_to_civic"), include_category_text=True).iter_records(NYC_CSV))
    assert all(eligible_real_text(r) for r in cat_text)                       # category text / no text => never eligible
    with pytest.raises(HybridDataError, match="no citizen narrative"):
        build_hybrid_training_set(cat_text, synth())


def test_hybrid_excludes_holdouts_caps_synthetic_and_keeps_provenance():
    real = [real_text_record(i) for i in range(10)] + [real_text_record(99, split_hint="holdout"), real_text_record(98, mapping_status="category_only", subcategory=None)]
    mixed, rep = build_hybrid_training_set(real, synth(30), max_synthetic_per_real=2.0, seed=1)
    assert rep["n_real"] == 10 and rep["n_synthetic"] == 20 and rep["real_excluded"] == {"holdout": 1, "no_exact_mapped_label": 1}
    assert {r.provenance.kind for r in mixed} == {"real_public", "synthetic"} and "real:99" not in {r.record_id for r in mixed}
    assert rep["real_share"] == pytest.approx(10 / 30, abs=1e-3)


def test_hybrid_rejects_mislabeled_synthetic_and_never_pads_with_synthetic_only():
    with pytest.raises(HybridDataError, match="non-synthetic"):
        build_hybrid_training_set([real_text_record(1)], [real_text_record(2)])
    with pytest.raises(HybridDataError):
        build_hybrid_training_set([], synth())
