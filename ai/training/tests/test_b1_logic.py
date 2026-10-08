import os

import numpy as np
import pytest

from ai.inference.providers.fake import FakeProvider
from ai.training.src import train_encoder_head as B1
from ai.training.src.io_utils import read_jsonl
from ai.training.tests.optional_deps import requires_sklearn


def fake_embed(texts):
    """Hashed char-trigram vectors: a stand-in encoder so the B1 *pipeline* is testable without torch."""
    fp = FakeProvider(dim=256)
    return np.array([fp._vec(t) for t in texts], dtype=np.float32)


@requires_sklearn
def test_b1_pipeline_logic_with_an_injected_encoder(small_dataset):
    tr, va, te = (read_jsonl(small_dataset / f"{s}.jsonl") for s in ("train", "val", "test"))
    res = B1.evaluate_embedding_classifier(fake_embed, tr, va, te, c_grid=(1.0, 10.0))
    assert res["embedding_dim"] == 256 and res["selected_C"] in (1.0, 10.0)
    assert res["test_subcategory_accuracy"] > 4 / 27 and 0 <= res["test_macro_f1"] <= 1
    assert set(res["test_subcategory_accuracy_by_language"]) == {"en", "hi", "mr", "hi-Latn"}


@requires_sklearn
def test_b1_run_writes_a_report_that_states_it_is_synthetic(small_dataset, tmp_path):
    out = B1.run(small_dataset, tmp_path, "fake/encoder", embed_fn=fake_embed)
    rep = __import__("json").loads((out / "b1_report.json").read_text(encoding="utf-8"))
    assert rep["synthetic_data"] is True and rep["encoder"] == "fake/encoder" and (tmp_path / "fake__encoder").exists()


@pytest.mark.requires_kaggle
def test_b1_with_a_real_sentence_encoder(small_dataset):
    pytest.importorskip("sentence_transformers", reason="requires sentence-transformers (Kaggle)")
    if not os.environ.get("RUN_B1_TESTS"):
        pytest.skip("set RUN_B1_TESTS=1 on Kaggle (needs internet to download the encoder)")
    embed = B1.load_sentence_encoder("intfloat/multilingual-e5-small", "query: ")
    tr, va, te = (read_jsonl(small_dataset / f"{s}.jsonl") for s in ("train", "val", "test"))
    assert B1.evaluate_embedding_classifier(embed, tr, va, te)["test_subcategory_accuracy"] > 0.1
