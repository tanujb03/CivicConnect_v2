import hashlib
import json
from pathlib import Path

from ai.inference.config import load_taxonomy

D = Path(__file__).resolve().parents[1] / "datasets"
T = load_taxonomy()


def rows(name):
    return [json.loads(l) for l in (D / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def manifest():
    return json.loads((D / "manifest.v1.json").read_text(encoding="utf-8"))


def test_committed_eval_files_match_the_manifest_hashes():
    m = manifest()
    for name, local in (("test.jsonl", "intake_eval.v1.jsonl"), ("pairs_test.jsonl", "fusion_eval_pairs.v1.jsonl")):
        assert hashlib.sha256((D / local).read_bytes()).hexdigest() == m["files"][name]["sha256"], local
        assert len(rows(local)) == m["files"][name]["rows"]


def test_eval_set_size_and_labelling():
    r = rows("intake_eval.v1.jsonl")
    assert 100 <= len(r) <= 300                                 # Section 57: 100-300 labelled reports
    assert manifest()["synthetic"] is True and "SYNTHETIC" in manifest()["disclaimer"]
    assert all(x["synthetic"] is True and x["split"] == "test" for x in r)
    assert {f"{x['category']}/{x['subcategory']}" for x in r} == set(T.label_ids)          # every class represented
    assert {x["language"] for x in r} == {"en", "hi", "mr", "hi-Latn"}
    assert any(x["code_mixed"] for x in r) and any(x["noisy"] for x in r)


def test_eval_families_and_places_are_held_out_from_training():
    m, r = manifest(), rows("intake_eval.v1.jsonl")
    design = m["split_design"]
    test_fams, train_fams = set(design["family_indices"]["test"]), set(design["family_indices"]["train"]) | set(design["family_indices"]["val"])
    assert not test_fams & train_fams
    assert {int(x["family_id"].split(":")[2]) for x in r} <= test_fams
    assert {x["place_id"] for x in r if x["place_id"] is not None} <= set(design["place_indices"]["test"])


def test_fusion_eval_pairs_are_labelled_and_held_out():
    p = rows("fusion_eval_pairs.v1.jsonl")
    assert len(p) == 300 and all(x["synthetic"] for x in p) and {x["label"] for x in p} == {0, 1}
    test_fams = set(manifest()["split_design"]["family_indices"]["test"])
    assert {int(x[s]["family_id"].split(":")[2]) for x in p for s in ("a", "b")} <= test_fams
    assert any(x["cross_language"] for x in p) and any(not x["cross_language"] for x in p)
