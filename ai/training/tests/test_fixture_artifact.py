import json

from ai.inference.local.text_classifier import LocalTextClassifier
from ai.training.src.make_fixture_artifact import GOLDEN_TEXTS, build_fixture
from ai.training.tests.optional_deps import requires_scipy, requires_sklearn


@requires_scipy
@requires_sklearn
def test_fixture_build_is_reproducible_and_matches_the_committed_golden_file(tmp_path):
    out = build_fixture(tmp_path / "fx")
    from ai.inference.tests.conftest import FIXTURE_ARTIFACT
    new = json.loads((out / "golden.json").read_text(encoding="utf-8"))
    committed = json.loads((FIXTURE_ARTIFACT / "golden.json").read_text(encoding="utf-8"))
    assert [g["text"] for g in new] == GOLDEN_TEXTS
    assert [(g["label_id"], g["abstained"]) for g in new] == [(g["label_id"], g["abstained"]) for g in committed]
    for a, b in zip(new, committed):
        assert abs(a["subcategory_probability"] - b["subcategory_probability"]) < 2e-3
    assert LocalTextClassifier.load(out).label_ids == LocalTextClassifier.load(FIXTURE_ARTIFACT).label_ids
