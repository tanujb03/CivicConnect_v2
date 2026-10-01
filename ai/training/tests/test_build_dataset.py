import json

from ai.training.src import build_dataset as bd
from ai.training.src.io_utils import read_jsonl

from .conftest import SMALL


def test_manifest_labels_dataset_as_synthetic_and_records_the_split_design(small_dataset):
    m = json.loads((small_dataset / "DATASET_MANIFEST.json").read_text(encoding="utf-8"))
    assert m["synthetic"] is True and "SYNTHETIC" in m["disclaimer"] and "native-speaker" in m["disclaimer"]
    assert m["split_design"]["unit"].startswith("template family")
    fam = m["split_design"]["family_indices"]
    assert not set(fam["train"]) & set(fam["test"]) and set(m["languages"]) == {"en", "hi", "mr", "hi-Latn"}
    assert set(m["files"]) == {f"{p}{s}.jsonl" for p in ("", "pairs_") for s in ("train", "val", "test")}


def test_dataset_is_reproducible_bit_for_bit(small_dataset, tmp_path):
    again = bd.build(tmp_path / "again", **SMALL)
    ref = json.loads((small_dataset / "DATASET_MANIFEST.json").read_text(encoding="utf-8"))
    assert {k: v["sha256"] for k, v in again["files"].items()} == {k: v["sha256"] for k, v in ref["files"].items()}
    assert bd.check_against(again, small_dataset / "DATASET_MANIFEST.json") == []


def test_manifest_check_detects_drift(small_dataset, tmp_path):
    other = bd.build(tmp_path / "other", **{**SMALL, "seed": 12})
    problems = bd.check_against(other, small_dataset / "DATASET_MANIFEST.json")
    assert problems and all("sha256 differs" in p for p in problems)


def test_cli_publishes_eval_set(tmp_path):
    rc = bd.main(["--out", str(tmp_path / "d"), "--eval-out", str(tmp_path / "e"), "--n-train", "2", "--n-val", "1", "--n-test", "1",
                  "--pairs-train", "40", "--pairs-val", "20", "--pairs-test", "20"])
    assert rc == 0 and len(read_jsonl(tmp_path / "e" / "intake_eval.v1.jsonl")) == 108
    assert (tmp_path / "e" / "manifest.v1.json").exists()
