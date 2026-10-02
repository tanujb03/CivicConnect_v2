import gzip
import json

import pytest

from ai.training.src.data_sources.adapters.chicago311 import Chicago311Adapter
from ai.training.src.data_sources.adapters.nyc311 import NYC311Adapter
from ai.training.src.data_sources.adapters.rdd2022 import RDD2022Adapter, infer_country, parse_voc
from ai.training.src.data_sources.adapters.synthetic import from_synthetic_row
from ai.training.src.data_sources.card_schema import load_card
from ai.training.src.data_sources.columns import (
    ColumnResolver,
    iter_rows,
    norm_header,
    parse_bool,
    parse_coord,
    parse_ts,
    reservoir,
    sniff_headers,
)
from ai.training.src.data_sources.errors import SchemaMismatch
from ai.training.src.data_sources.mapping import MappingTable
from ai.training.src.synthetic import generator as gen

from .conftest_real import CHI_JSONL, NYC_CSV, make_rdd_tree


def nyc(**kw):
    return NYC311Adapter(load_card("nyc311"), MappingTable.load("nyc311_to_civic"), **kw)


def chi(**kw):
    return Chicago311Adapter(load_card("chicago311"), MappingTable.load("chicago311_to_civic"), **kw)


# ------------------------------------------------------------------ columns / parsing
def test_header_resolution_handles_api_and_export_styles_and_fails_loudly():
    aliases, req = {"record_id": ["unique_key"], "ct": ["complaint_type"]}, {"record_id", "ct"}
    for headers in (["unique_key", "complaint_type"], ["Unique Key", "Complaint Type"], ["UNIQUE-KEY", "complaint  type"]):
        r = ColumnResolver(headers, aliases, req)
        assert r.get({h: "v" for h in headers}, "record_id") == "v"
    with pytest.raises(SchemaMismatch) as e:
        ColumnResolver(["id", "kind"], aliases, req)
    assert "record_id" in str(e.value) and "'id'" in str(e.value) and "Available headers" in str(e.value)
    assert norm_header(" Created  Date ") == "created_date"


def test_parsers():
    assert parse_ts("09/01/2025 08:15:00 AM") == "2025-09-01T08:15:00" and parse_ts("2025-09-01T08:15:00.000") == "2025-09-01T08:15:00"
    assert parse_ts("09/01/2025 11:30:00 PM") == "2025-09-01T23:30:00" and parse_ts("2025-09-01") == "2025-09-01T00:00:00"
    assert parse_ts("garbage") is None and parse_ts("") is None and parse_ts(None) is None
    assert parse_coord("41.5", -90, 90) == 41.5 and parse_coord("95", -90, 90) is None and parse_coord("x", -90, 90) is None and parse_coord("nan", -90, 90) is None
    assert [parse_bool(x) for x in ("true", "T", "1", "false", "", None, "maybe", True)] == [True, True, True, False, False, None, None, True]


def test_readers_support_csv_jsonl_json_and_gzip(tmp_path):
    rows = [{"a": "1", "b": "x"}, {"a": "2", "b": "y"}]
    (tmp_path / "t.csv").write_text("a,b\n1,x\n2,y\n", encoding="utf-8")
    (tmp_path / "t.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    (tmp_path / "t.json").write_text(json.dumps(rows), encoding="utf-8")
    with gzip.open(tmp_path / "t.csv.gz", "wt", encoding="utf-8") as fh:
        fh.write("a,b\n1,x\n2,y\n")
    for name in ("t.csv", "t.jsonl", "t.json", "t.csv.gz"):
        assert list(iter_rows(tmp_path / name)) == rows and sniff_headers(tmp_path / name) == ["a", "b"]
    with pytest.raises(SchemaMismatch):
        list(iter_rows(tmp_path / "t.xlsx"))


def test_reservoir_sampling_is_deterministic_and_bounded():
    a, b = list(reservoir(range(1000), 10, seed=1)), list(reservoir(range(1000), 10, seed=1))
    assert a == b and len(a) == 10 and a != list(reservoir(range(1000), 10, seed=2)) and len(list(reservoir(range(5), 10))) == 5
    assert list(reservoir(range(5), None)) == list(range(5))


# ------------------------------------------------------------------ NYC adapter (format fixture)
def test_nyc_adapter_maps_fixture_rows_with_explicit_statuses():
    ad = nyc(retrieved_at="2026-10-01")
    recs = list(ad.iter_records(NYC_CSV))
    assert len(recs) == 12 and ad.stats["rows_read"] == 12
    by_id = {r.record_id: r for r in recs}
    assert by_id["nyc311:FMT-0001"].mapping_status == "exact" and by_id["nyc311:FMT-0001"].subcategory == "pothole"
    assert by_id["nyc311:FMT-0002"].mapping_status == "category_only" and by_id["nyc311:FMT-0002"].category == "roads"
    assert by_id["nyc311:FMT-0003"].subcategory == "pipe_leakage" and by_id["nyc311:FMT-0004"].subcategory == "blocked_drain"
    assert by_id["nyc311:FMT-0006"].mapping_status == "out_of_scope" and by_id["nyc311:FMT-0006"].category is None
    assert by_id["nyc311:FMT-0009"].mapping_status == "unmapped"
    assert by_id["nyc311:FMT-0001"].department == "road_maintenance"
    cov = ad.coverage.to_dict()
    assert cov["counts"] == {"exact": 9, "category_only": 1, "out_of_scope": 1, "unmapped": 1}
    # source labels are preserved verbatim next to the mapped ones
    assert by_id["nyc311:FMT-0001"].source_category == "Street Condition" and by_id["nyc311:FMT-0001"].source_subcategory == "Pothole"


def test_nyc_adapter_cleans_coordinates_and_dates_and_never_reads_addresses():
    ad = nyc()
    recs = {r.record_id: r for r in ad.iter_records(NYC_CSV)}
    assert recs["nyc311:FMT-0009"].latitude is None and recs["nyc311:FMT-0010"].latitude is None       # blank and 0/0 dropped
    assert ad.stats["no_coordinates"] == 2 and ad.stats["no_created_at"] == 1 and recs["nyc311:FMT-0011"].created_at is None
    assert recs["nyc311:FMT-0001"].created_at == "2025-09-01T08:15:00" and recs["nyc311:FMT-0001"].closed_at == "2025-09-03T10:00:00"
    assert recs["nyc311:FMT-0001"].place == "MANHATTAN"
    assert not any("address" in a for a in NYC311Adapter.aliases) and not any("address" in f for f in recs["nyc311:FMT-0001"].model_fields_set)


def test_nyc_adapter_has_no_narrative_text_unless_explicitly_requested_and_then_it_is_flagged():
    recs = list(nyc().iter_records(NYC_CSV))
    assert all(r.text is None and r.text_origin == "none" for r in recs)
    leak = list(nyc(include_category_text=True).iter_records(NYC_CSV))
    assert all(r.text_origin == "source_category_text" for r in leak if r.text) and leak[0].text == "Street Condition - Pothole"


def test_every_record_carries_full_provenance():
    for r in nyc(retrieved_at="2026-10-01").iter_records(NYC_CSV):
        p = r.provenance
        assert (p.kind, p.source_id, p.license_verified, p.label_origin) == ("real_public", "nyc311", False, "mapped_from_source")
        assert p.mapping_id == "nyc311_to_civic" and p.mapping_version == "0.1.0-draft" and p.source_record_id and p.retrieved_at == "2026-10-01"
        assert p.license_id and p.source_dataset


def test_nyc_adapter_filters_and_samples_deterministically():
    ad = nyc()
    since = list(ad.iter_records(NYC_CSV, since="2025-09-04", until="2025-09-05"))
    assert {r.record_id.split(":")[1] for r in since} == {"FMT-0007", "FMT-0008", "FMT-0009", "FMT-0010"}
    a = [r.record_id for r in nyc().iter_records(NYC_CSV, max_rows=5, sample_seed=3)]
    assert a == [r.record_id for r in nyc().iter_records(NYC_CSV, max_rows=5, sample_seed=3)] and len(a) == 5


def test_nyc_adapter_rejects_a_file_without_required_columns(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(SchemaMismatch, match="Available headers"):
        list(nyc().iter_records(p))


# ------------------------------------------------------------------ Chicago adapter
def test_chicago_adapter_maps_types_and_keeps_duplicate_links():
    ad = chi()
    recs = {r.record_id: r for r in ad.iter_records(CHI_JSONL)}
    assert recs["chicago311:FMT-C001"].subcategory == "pothole" and recs["chicago311:FMT-C006"].subcategory == "light_not_working"
    assert recs["chicago311:FMT-C009"].subcategory == "dead_animal" and recs["chicago311:FMT-C010"].mapping_status == "out_of_scope"
    assert recs["chicago311:FMT-C011"].mapping_status == "unmapped" and recs["chicago311:FMT-C012"].subcategory == "no_water_supply"
    assert recs["chicago311:FMT-C002"].duplicate_flag is True and recs["chicago311:FMT-C002"].parent_record_id == "chicago311:FMT-C001"
    assert recs["chicago311:FMT-C001"].duplicate_flag is False and recs["chicago311:FMT-C001"].parent_record_id is None
    assert recs["chicago311:FMT-C001"].place == "21"                                                  # int community area coerced to str
    assert all(r.text is None for r in recs.values())


def test_chicago_legacy_records_can_be_excluded():
    ad = chi(exclude_legacy=True)
    ids = {r.record_id for r in ad.iter_records(CHI_JSONL)}
    assert "chicago311:FMT-C009" not in ids and ad.stats["dropped_legacy"] == 1


def test_chicago_works_without_duplicate_columns(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text(json.dumps({"sr_number": "1", "sr_type": "Pothole in Street Complaint", "created_date": "2025-09-01T00:00:00"}) + "\n", encoding="utf-8")
    r = list(chi().iter_records(p))[0]
    assert r.duplicate_flag is None and r.parent_record_id is None


# ------------------------------------------------------------------ RDD2022 adapter
def test_country_inference():
    assert infer_country(("India", "train", "images")) == ("India", None)
    assert infer_country(("China_MotorBike", "train")) == ("China", "MotorBike") and infer_country(("China_Drone",))[1] == "Drone"
    assert infer_country(("Czech", "x"))[0] == "Czech Republic" and infer_country(("United_States",))[0] == "United States"
    assert infer_country(("mystery",)) == (None, None)


def test_rdd_adapter_produces_image_references_with_mapped_boxes(tmp_path):
    root = make_rdd_tree(tmp_path / "RDD")
    ad = RDD2022Adapter(load_card("rdd2022"), MappingTable.load("rdd2022_to_civic"))
    recs = {r.record_id: r for r in ad.iter_records(root)}
    assert set(recs) == {"rdd2022:India:-:IN_1", "rdd2022:India:-:IN_2", "rdd2022:Japan:-:JP_1", "rdd2022:China:MotorBike:CN_1", "rdd2022:Czech Republic:-:IN_1"}
    r = recs["rdd2022:India:-:IN_1"]
    assert r.has_annotation and (r.width, r.height) == (640, 480) and r.image_relpath == "India/train/images/IN_1.jpg" and r.split_hint == "train"
    assert [b.class_code for b in r.boxes] == ["D40", "D00", "D44"]                      # degenerate box skipped
    assert [(b.mapping_status, b.subcategory) for b in r.boxes] == [("exact", "pothole"), ("category_only", None), ("unmapped", None)]
    assert r.image_labels == ["roads", "roads/pothole"]
    assert recs["rdd2022:India:-:IN_2"].boxes == [] and recs["rdd2022:India:-:IN_2"].image_labels == []
    assert recs["rdd2022:Japan:-:JP_1"].image_labels == ["roads"]
    assert ad.stats["degenerate_boxes"] == 1 and ad.stats["unknown_classes"] == 1 and ad.stats["invalid_xml"] == 1
    assert ad.coverage.to_dict()["counts"] == {"category_only": 3, "exact": 2, "unmapped": 1}
    p = r.provenance
    assert (p.kind, p.label_origin, p.license_verified) == ("real_public", "human_annotated", True)


def test_rdd_ids_are_unique_across_countries_and_paths_are_relative(tmp_path):
    root = make_rdd_tree(tmp_path / "RDD")
    recs = list(RDD2022Adapter(load_card("rdd2022"), MappingTable.load("rdd2022_to_civic")).iter_records(root))
    ids = [r.record_id for r in recs]
    assert len(ids) == len(set(ids)) and all(not r.image_relpath.startswith("/") and str(tmp_path) not in r.image_relpath for r in recs)


def test_rdd_country_filter_unannotated_images_and_image_checks(tmp_path):
    root = make_rdd_tree(tmp_path / "RDD")
    mk = lambda: RDD2022Adapter(load_card("rdd2022"), MappingTable.load("rdd2022_to_civic"))  # noqa: E731
    assert {r.country for r in mk().iter_records(root, countries={"India"})} == {"India"}
    un = [r for r in mk().iter_records(root, include_unannotated=True) if not r.has_annotation]
    assert [(r.record_id, r.split_hint) for r in un] == [("rdd2022:India:-:IN_T1", None)] and un[0].boxes == []
    (root / "India" / "train" / "images" / "IN_2.jpg").unlink()
    ad = mk()
    assert "rdd2022:India:-:IN_2" not in {r.record_id for r in ad.iter_records(root, check_images=True)} and ad.stats["images_missing"] >= 1


def test_voc_parser_refuses_dtd_and_entities(tmp_path):
    bad = tmp_path / "a.xml"
    bad.write_text('<!DOCTYPE foo [<!ENTITY x "y">]><annotation/>', encoding="utf-8")
    with pytest.raises(SchemaMismatch):
        parse_voc(bad)
    broken = tmp_path / "b.xml"
    broken.write_text("<annotation><oops></annotation>", encoding="utf-8")
    with pytest.raises(SchemaMismatch):
        parse_voc(broken)


def test_rdd_missing_root():
    with pytest.raises(SchemaMismatch):
        list(RDD2022Adapter(load_card("rdd2022"), MappingTable.load("rdd2022_to_civic")).iter_records("/nonexistent/root"))


# ------------------------------------------------------------------ synthetic wrapper keeps provenance
def test_synthetic_rows_become_canonical_records_with_synthetic_provenance():
    row = gen.generate_intake_split("test", 1, 3)[0]
    r = from_synthetic_row(row)
    assert r.provenance.kind == "synthetic" and r.provenance.license_verified and r.provenance.label_origin == "synthetic_template"
    assert r.text_origin == "citizen_narrative" and r.mapping_status == "not_applicable" and r.split_hint == "test"
    assert (r.category, r.subcategory) == (row["category"], row["subcategory"])
