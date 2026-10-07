"""Gold-set provenance: read from the CSV, never defaulted to human, and always visible in the report block that uses it."""
import numpy as np
import pytest

from ai.evaluation import gold as g
from ai.training.src.text_model import train as tr


@pytest.mark.parametrize("column, notes, expected", [
    ("human", "", ("human", "column")),
    (" Human ", "style=sms", ("human", "column")),
    ("llm_authored_claude", "", ("llm_authored_claude", "column")),
    ("llm_authored_claude", "llm_authored_claude; style=plain", ("llm_authored_claude", "column")),    # column and notes agree
    ("", "llm_authored_claude; style=angry", ("llm_authored_claude", "notes")),                         # no column value: the notes marker
    (None, "Style=SMS; LLM_Authored_Claude", ("llm_authored_claude", "notes")),
    ("", "", ("unspecified", "none")),
    (None, None, ("unspecified", "none")),
    ("", "written by the team, human", ("unspecified", "none")),                                          # "human" in notes is NOT a marker
    ("teacher", "", ("unspecified", "column_unrecognized")),
    ("teacher", "llm_authored_claude", ("unspecified", "column_unrecognized")),                          # an explicit but unknown value never falls through to the notes
    ("human", "llm_authored_claude; style=plain", ("unspecified", "conflict")),                          # contradictory: not human
    ("llm_authored_claude", "llm_authored_gpt", ("unspecified", "conflict")),
])
def test_provenance_is_read_from_the_column_then_the_notes_marker_and_never_defaults_to_human(column, notes, expected):
    assert g.read_provenance(column, notes) == expected


def test_only_explicit_human_is_team_authored_and_not_synthetic():
    assert (g.label_origin("human"), g.is_synthetic("human")) == ("team_authored", False)
    assert (g.label_origin("llm_authored_claude"), g.is_synthetic("llm_authored_claude")) == ("llm_authored_claude", True)
    assert (g.label_origin("unspecified"), g.is_synthetic("unspecified")) == ("unspecified", True)


def test_a_gold_jsonl_row_without_provenance_is_unspecified_even_if_the_old_builder_called_it_team_authored():
    assert g.row_provenance({"label_origin": "team_authored", "synthetic": False}) == "unspecified"
    assert g.row_provenance({"provenance": "human"}) == "human" and g.row_provenance({"provenance": "bogus"}) == "unspecified"


def _rows(**counts):
    return [{"text": f"{p} {i}", "language": "en", "label_id": "roads/pothole", "provenance": p} for p, n in counts.items() for i in range(n)]


def test_report_blocks_are_split_by_provenance_labelled_with_their_size_and_never_pooled():
    sets = g.split_by_provenance(_rows(llm_authored_claude=5, human=2, unspecified=1))
    assert list(sets) == ["gold[human, n=2]", "gold[llm_authored_claude, n=5]", "gold[unspecified, n=1]"]
    assert [len(v) for v in sets.values()] == [2, 5, 1] and "gold" not in sets
    assert list(g.split_by_provenance(_rows(llm_authored_claude=336))) == ["gold[llm_authored_claude, n=336]"]       # only LLM gold: no block is called human
    assert g.split_by_provenance([]) == {}


def test_block_meta_says_what_the_set_is_and_refuses_a_mixed_block():
    llm = g.block_meta(_rows(llm_authored_claude=3))
    assert llm["provenance"] == "llm_authored_claude" and llm["human_written"] is False and "not human text" in llm["claim"] and "never a real-world accuracy claim" in llm["claim"]
    assert g.block_meta(_rows(human=1))["human_written"] is True
    unspec = g.block_meta(_rows(unspecified=1))
    assert unspec["human_written"] is False and "NOT specified" in unspec["claim"]
    with pytest.raises(ValueError):
        g.block_meta(_rows(human=1, llm_authored_claude=1))


def test_training_report_blocks_carry_provenance_and_the_llm_set_is_never_presented_as_human_gold():
    data = {"val": [{"label_id": "roads/pothole", "language": "en"}], "test": [{"label_id": "roads/pothole", "language": "en"}]}
    sets, gold_names = tr.evaluation_sets(data, _rows(llm_authored_claude=4, human=2))
    assert set(sets) == {"val", "test_llm_groups", "gold[human, n=2]", "gold[llm_authored_claude, n=4]"} and gold_names == {"gold[human, n=2]", "gold[llm_authored_claude, n=4]"}
    labels = ["roads/pothole", "roads/damaged_footpath"]
    res = {n: tr.block_result(np.array([[1.0, 0.0]] * len(rows)), rows, labels, gold=n in gold_names) for n, rows in sets.items()}
    llm, human = res["gold[llm_authored_claude, n=4]"], res["gold[human, n=2]"]
    assert llm["n"] == 4 and llm["provenance"] == "llm_authored_claude" and llm["human_written"] is False and "not human text" in llm["claim"]
    assert human["n"] == 2 and human["provenance"] == "human" and human["human_written"] is True
    assert "provenance" not in res["val"] and "provenance" not in res["test_llm_groups"]                         # non-gold blocks are untouched
    sets_none, names_none = tr.evaluation_sets(data, [])
    assert set(sets_none) == {"val", "test_llm_groups"} and names_none == set()


def test_manifest_count_block():
    rows = [{"provenance": "llm_authored_claude", "language": "en"}] * 3 + [{"provenance": "llm_authored_claude", "language": "hi"}, {"provenance": "human", "language": "mr"}, {"provenance": "unspecified", "language": "en"}]
    c = g.count_by_provenance(rows)
    assert c["by_provenance"] == {"human": 1, "llm_authored_claude": 4, "unspecified": 1} and c["human_rows"] == 1
    assert c["by_provenance_language"] == {"human": {"mr": 1}, "llm_authored_claude": {"en": 3, "hi": 1}, "unspecified": {"en": 1}}
    assert g.count_by_provenance([])["human_rows"] == 0
