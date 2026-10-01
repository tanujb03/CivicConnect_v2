import hashlib
import json
import subprocess

import httpx
import pytest

from ai.training.src.data_sources import cli
from ai.training.src.data_sources import prepare as prep
from ai.training.src.data_sources.canonical import CaseRecord, ImageRecord
from ai.training.src.data_sources.card_schema import load_card
from ai.training.src.data_sources.download.figshare import FigshareClient
from ai.training.src.data_sources.download.socrata import HARD_MAX_ROWS, SocrataDownloader
from ai.training.src.data_sources.errors import DataSourceError, UnsafeOutputPath
from ai.training.src.data_sources.paths import REPO_ROOT, ensure_safe_output
from ai.training.src.io_utils import read_jsonl

from .conftest_real import CHI_JSONL, NYC_CSV, make_chicago_rows, make_rdd_tree

ACCEPT = ["--acknowledge-unverified-license"]


# ------------------------------------------------------------------ Socrata downloader (mock transport; nothing leaves the machine)
def soda(rows, seen, status_seq=None):
    status_seq = list(status_seq or [])

    def handler(req: httpx.Request):
        seen.append((dict(req.url.params), dict(req.headers)))
        if status_seq:
            code = status_seq.pop(0)
            if code != 200:
                return httpx.Response(code)
        off, lim = int(req.url.params["$offset"]), int(req.url.params["$limit"])
        return httpx.Response(200, json=rows[off: off + lim])

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_socrata_paging_params_cap_and_retrieval_record(tmp_path):
    rows = [{"unique_key": str(i), "complaint_type": "x"} for i in range(7)]
    seen: list = []
    dl = SocrataDownloader(load_card("nyc311"), client=soda(rows, seen), app_token="SECRET-TOKEN", sleep=lambda s: None)
    raw = dl.download(tmp_path, since="2025-09-01", until="2025-09-30", max_rows=100, page_size=3, where="agency='DOT'")
    assert [int(p["$offset"]) for p, _ in seen] == [0, 3, 6] and all(p["$order"] == ":id" for p, _ in seen)
    assert seen[0][0]["$where"] == "created_date >= '2025-09-01T00:00:00' AND created_date <= '2025-09-30T23:59:59' AND (agency='DOT')"
    assert seen[0][1]["x-app-token"] == "SECRET-TOKEN"
    assert len(read_jsonl(raw)) == 7
    meta = json.loads((tmp_path / "RETRIEVAL.json").read_text(encoding="utf-8"))
    assert meta["rows"] == 7 and meta["sha256"] == hashlib.sha256(raw.read_bytes()).hexdigest() and meta["app_token_used"] is True
    assert "SECRET-TOKEN" not in json.dumps(meta) and meta["license_verified"] is False and meta["card_fingerprint"]


def test_socrata_respects_max_rows_and_input_validation(tmp_path):
    seen: list = []
    dl = SocrataDownloader(load_card("chicago311"), client=soda([{"a": i} for i in range(50)], seen), sleep=lambda s: None)
    assert len(read_jsonl(dl.download(tmp_path, max_rows=10, page_size=4))) == 10 and [p["$limit"] for p, _ in seen] == ["4", "4", "2"]
    with pytest.raises(DataSourceError):
        dl.where_clause("2025-9-1", None, None)
    with pytest.raises(DataSourceError):
        dl.download(tmp_path, max_rows=HARD_MAX_ROWS + 1)
    assert "x-app-token" not in seen[0][1]


def test_socrata_retries_transient_errors_and_fails_cleanly(tmp_path):
    seen: list = []
    dl = SocrataDownloader(load_card("nyc311"), client=soda([{"a": 1}], seen, status_seq=[503, 200]), sleep=lambda s: None)
    assert len(read_jsonl(dl.download(tmp_path / "a"))) == 1 and len(seen) >= 2
    bad = SocrataDownloader(load_card("nyc311"), client=soda([], [], status_seq=[404]), sleep=lambda s: None)
    with pytest.raises(DataSourceError, match="HTTP 404"):
        bad.download(tmp_path / "b")
    with pytest.raises(DataSourceError):
        SocrataDownloader(load_card("rdd2022"))                       # not a Socrata source


# ------------------------------------------------------------------ figshare client
def figshare(files, content=b"x" * 10):
    def handler(req: httpx.Request):
        if req.url.path.startswith("/v2/articles"):
            return httpx.Response(200, json={"title": "T", "doi": "10.x/y", "version": 1, "license": {"name": "CC BY 4.0", "url": "https://u"},
                                             "published_date": "2022", "files": files})
        return httpx.Response(200, content=content)
    return FigshareClient(21431547, client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_figshare_reports_licence_from_the_primary_api_and_lists_files():
    c = figshare([{"id": 1, "name": "a.zip", "size": 10, "computed_md5": "m", "download_url": "https://dl/a"}])
    assert c.show_license()["license"] == {"name": "CC BY 4.0", "url": "https://u"}
    assert c.list_files()[0]["md5"] == "m"


def test_figshare_download_verifies_md5_and_respects_size_allowance(tmp_path):
    good = hashlib.md5(b"x" * 10).hexdigest()
    c = figshare([{"id": 1, "name": "a.zip", "size": 10, "computed_md5": good, "download_url": "https://dl/a"}])
    f = c.list_files()[0]
    assert c.download(f, tmp_path).read_bytes() == b"x" * 10
    with pytest.raises(DataSourceError, match="md5 mismatch"):
        c.download({**f, "md5": "0" * 32}, tmp_path / "b")
    with pytest.raises(DataSourceError, match="allowance"):
        c.download({**f, "size": 20 * 1024 ** 3}, tmp_path / "c")


# ------------------------------------------------------------------ output-path guard
def test_safe_output_paths(tmp_path):
    assert ensure_safe_output(tmp_path / "x") == (tmp_path / "x").resolve()                       # outside the repo: ok
    assert ensure_safe_output(REPO_ROOT / "ai" / "artifacts" / "real_data" / "nyc311").name == "nyc311"
    for bad in (REPO_ROOT / "ai", REPO_ROOT / "ai" / "evaluation" / "datasets", REPO_ROOT / "docs", REPO_ROOT / "ai" / "artifacts" / "civic_text_b0",
                REPO_ROOT / "ai" / "artifacts" / "real_data" / ".." / "datasets"):
        with pytest.raises(UnsafeOutputPath):
            ensure_safe_output(bad)


def test_real_data_directory_is_gitignored():
    r = subprocess.run(["git", "check-ignore", "-q", "ai/artifacts/real_data/nyc311/anything.json"], cwd=REPO_ROOT)
    if r.returncode == 128:
        pytest.skip("not a git checkout")
    assert r.returncode == 0


def test_no_real_or_large_data_is_tracked_in_git():
    r = subprocess.run(["git", "ls-files", "ai"], cwd=REPO_ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("not a git checkout")
    files = [f for f in r.stdout.splitlines() if (REPO_ROOT / f).exists()]
    assert not [f for f in files if f.startswith("ai/artifacts/real_data/")]
    big = [(f, (REPO_ROOT / f).stat().st_size) for f in files if (REPO_ROOT / f).stat().st_size > 1_000_000]
    assert not big, f"large tracked files: {big}"
    assert not [f for f in files if f.endswith((".zip", ".tar", ".gz", ".parquet", ".h5", ".pt", ".onnx"))]


# ------------------------------------------------------------------ prepare (library)
def test_prepare_tabular_writes_valid_canonical_records_and_an_honest_manifest(tmp_path):
    m = prep.prepare_tabular(load_card("nyc311"), NYC_CSV, tmp_path / "out", holdout_after="2025-09-04", retrieved_at="2026-10-01")
    recs = [CaseRecord.model_validate(r) for r in read_jsonl(tmp_path / "out" / "records.jsonl")]
    assert m["records"] == len(recs) == 12 and m["license_verified"] is False and m["license_status"] == "UNVERIFIED"
    assert m["citizen_narrative_text_available"] is False and m["text_origin_counts"] == {"none": 12}
    assert m["coverage"]["counts"]["exact"] == 9 and m["mapping"]["status"].startswith("DRAFT") and m["input_sha256"]
    assert m["split_counts"]["holdout"] > 0 and m["split_counts"]["train"] > 0 and "NOT permitted" in m["redistribution"]
    assert m["taxonomy_version"] == "1.0.0-draft" and m["card_fingerprint"]


def test_prepare_rdd_writes_references_not_images(tmp_path):
    root = make_rdd_tree(tmp_path / "RDD")
    m = prep.prepare_rdd(load_card("rdd2022"), root, tmp_path / "out", holdout_countries={"Japan"}, include_unannotated=True)
    recs = [ImageRecord.model_validate(r) for r in read_jsonl(tmp_path / "out" / "records.jsonl")]
    assert m["images_per_country"]["India"] == 3 and m["boxes_per_class"] == {"D40": 2, "D00": 1, "D44": 1, "D20": 1, "D10": 1}
    assert {r.split_hint for r in recs if r.country == "Japan"} == {"holdout"} and {r.split_hint for r in recs if r.country == "India"} == {"train"}
    assert m["license_verified"] is False and m["license_conflicts"] and "BY-SA" in m["redistribution"]
    assert not list((tmp_path / "out").glob("*.jpg")) and m["images_with_no_boxes"] == 1
    assert m["image_label_counts"]["roads/pothole"] == 2


# ------------------------------------------------------------------ CLI
def test_cli_cards_and_card(capsys):
    assert cli.main(["cards"]) == 0 and "nyc311" in capsys.readouterr().out
    assert cli.main(["card", "rdd2022"]) == 0 and "CONFLICT" in capsys.readouterr().out


def test_cli_prepare_requires_terms_then_works(tmp_path, capsys):
    args = ["prepare", "nyc311", "--input", str(NYC_CSV), "--out", str(tmp_path / "o")]
    assert cli.main(args) == 2 and "--accept-terms nyc311" in capsys.readouterr().err
    assert cli.main([*args, "--accept-terms", "nyc311"]) == 2 and "UNVERIFIED" in capsys.readouterr().err
    assert cli.main([*args, "--accept-terms", "nyc311", *ACCEPT]) == 0
    assert (tmp_path / "o" / "PREPARE_MANIFEST.json").exists()


def test_cli_refuses_unsafe_output_locations(tmp_path, capsys):
    rc = cli.main(["prepare", "nyc311", "--input", str(NYC_CSV), "--out", str(REPO_ROOT / "ai" / "evaluation" / "oops"), "--accept-terms", "nyc311", *ACCEPT])
    assert rc == 2 and "refusing to write external data" in capsys.readouterr().err
    assert not (REPO_ROOT / "ai" / "evaluation" / "oops").exists()


def test_cli_profile_flags_missing_columns_and_free_text(tmp_path, capsys):
    out = tmp_path / "p.json"
    assert cli.main(["profile", "chicago311", "--input", str(CHI_JSONL), "--out", str(out)]) == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["resolved_columns"]["record_id"] == "sr_number" and rep["draft_mapping_coverage"]["total"] == 12
    assert rep["candidate_free_text_columns"] == [] and rep["date_range"][0].startswith("2025-09-01") and rep["coordinate_coverage"] == 1.0
    long_text = tmp_path / "t.jsonl"
    long_text.write_text("\n".join(json.dumps({"sr_number": str(i), "sr_type": "Pothole", "created_date": "2025-09-01T00:00:00", "notes": "x" * 200}) for i in range(30)), encoding="utf-8")
    cli.main(["profile", "chicago311", "--input", str(long_text), "--out", str(tmp_path / "q.json")])
    assert json.loads((tmp_path / "q.json").read_text(encoding="utf-8"))["candidate_free_text_columns"][0]["column"] == "notes"


def test_cli_end_to_end_chicago_prepare_then_pairs(tmp_path, capsys):
    big = make_chicago_rows(tmp_path / "chi.jsonl", n_dups=25)
    assert cli.main(["prepare", "chicago311", "--input", str(big), "--out", str(tmp_path / "prep"), "--accept-terms", "chicago311", *ACCEPT]) == 0
    assert cli.main(["pairs", "--records", str(tmp_path / "prep" / "records.jsonl"), "--out", str(tmp_path / "pairs")]) == 0
    man = json.loads((tmp_path / "pairs" / "PAIRS_MANIFEST.json").read_text(encoding="utf-8"))
    assert man["stats"]["positives"] == 25 and man["n_pairs"] >= 25


def test_cli_schema_mismatch_exits_cleanly(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    assert cli.main(["prepare", "nyc311", "--input", str(bad), "--out", str(tmp_path / "o"), "--accept-terms", "nyc311", *ACCEPT]) == 2
    assert "Available headers" in capsys.readouterr().err
