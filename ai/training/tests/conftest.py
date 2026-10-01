from __future__ import annotations

from pathlib import Path

import pytest

from ai.training.src.build_dataset import build

SMALL = dict(seed=11, test_fold=4, n_train=4, n_val=2, n_test=1, pairs_train=300, pairs_val=100, pairs_test=60)


@pytest.fixture(scope="session")
def small_dataset(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("synthetic_small")
    build(out, **SMALL)
    return out
