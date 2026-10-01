import math

import pytest

from ai.evaluation import metrics as M


def test_accuracy_and_wilson():
    assert M.accuracy(["a", "b"], ["a", "c"]) == 0.5 and math.isnan(M.accuracy([], []))
    lo, hi = M.wilson_interval(50, 100)
    assert lo < 0.5 < hi and 0.39 < lo < 0.41 and 0.59 < hi < 0.61
    assert M.wilson_interval(0, 0)[0] != M.wilson_interval(0, 0)[0]  # NaN
    lo, hi = M.wilson_interval(10, 10)
    assert hi == pytest.approx(1.0) and lo > 0.6


def test_per_class_prf_and_macro_f1():
    yt, yp = ["a", "a", "b", "b", "c"], ["a", "b", "b", "b", "a"]
    prf = M.per_class_prf(yt, yp, ["a", "b", "c"])
    assert prf["a"]["precision"] == 0.5 and prf["a"]["recall"] == 0.5 and prf["b"]["precision"] == pytest.approx(2 / 3)
    assert prf["c"]["f1"] == 0.0 and prf["c"]["support"] == 1
    assert M.macro_f1(yt, yp, ["a", "b", "c", "unused"]) == pytest.approx((0.5 + 0.8 + 0.0) / 3)  # unseen classes excluded


def test_ece_known_cases():
    assert M.expected_calibration_error([1.0] * 10, [True] * 10) == 0.0
    assert M.expected_calibration_error([0.9] * 10, [True] * 5 + [False] * 5) == pytest.approx(0.4)
    assert M.expected_calibration_error([0.5] * 10, [True] * 5 + [False] * 5) == pytest.approx(0.0)
    assert math.isnan(M.expected_calibration_error([], []))


def test_auc_and_threshold_metrics():
    assert M.auc_roc([0.1, 0.4, 0.35, 0.8], [0, 0, 1, 1]) == 0.75
    assert M.auc_roc([0.2, 0.2], [0, 1]) == 0.5 and math.isnan(M.auc_roc([0.1, 0.2], [1, 1]))
    m = M.precision_recall_at([0.9, 0.7, 0.4, 0.2], [1, 0, 1, 0], 0.5)
    assert (m["tp"], m["fp"], m["fn"]) == (1, 1, 1) and m["f1"] == 0.5


def test_top_confusions_orders_by_count():
    c = M.top_confusions(["a", "a", "a", "b"], ["b", "b", "c", "a"], k=2)
    assert c[0] == {"true": "a", "pred": "b", "count": 2} and len(c) == 2
