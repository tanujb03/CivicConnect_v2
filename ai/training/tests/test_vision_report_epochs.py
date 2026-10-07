"""Per-epoch wall-clock times from Ultralytics' results.csv (cumulative ``time`` column, padded header names)."""
from ai.training.src.vision import report as rp


def test_epoch_seconds_are_the_differences_of_the_cumulative_time_column(tmp_path):
    f = tmp_path / "results.csv"
    f.write_text("                  epoch,                    time,         train/box_loss\n" "                      1,                   41.5,                 1.2\n"
                 "                      2,                   80.25,                1.1\n" "                      3,                  121.0,                 1.0\n", encoding="utf-8")
    assert rp.epoch_seconds(f) == [41.5, 38.75, 40.75]


def test_epoch_seconds_is_empty_when_the_file_or_column_is_missing(tmp_path):
    assert rp.epoch_seconds(tmp_path / "nope.csv") == []
    f = tmp_path / "r.csv"
    f.write_text("epoch,loss\n1,0.5\n", encoding="utf-8")
    assert rp.epoch_seconds(f) == []
