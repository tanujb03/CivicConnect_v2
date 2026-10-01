"""The committed dataset→task→fields→labels→mapping→track manifests must match what the code/policy/cards generate."""
import json

from ai.training.src.data_sources import task_matrix as tm
from ai.training.src.data_sources.card_schema import list_cards
from ai.training.src.data_sources.column_roles import TaskPolicy

TRACKS = {"synthetic", "real_holdout", "hybrid", "descriptive", "none"}


def test_committed_manifests_are_in_sync_with_the_generators():
    assert (tm.HERE / "TASK_MATRIX.md").read_text(encoding="utf-8") == tm.render_markdown()
    assert (tm.HERE / "BMC_COLUMN_POLICY.md").read_text(encoding="utf-8") == tm.render_bmc_policy_markdown()
    assert json.loads((tm.HERE / "task_matrix.v1.json").read_text(encoding="utf-8")) == json.loads(json.dumps(tm.build_matrix()))


def test_every_card_has_at_least_one_row_and_every_row_uses_a_known_track():
    rows = tm.build_matrix()
    assert {c.id for c in list_cards()} <= {r["source_id"] for r in rows}
    assert all(r["track"] in TRACKS for r in rows)
    assert all(r["source_priority"] in ("primary", "secondary", "optional", "future") for r in rows)


def test_bmc_rows_are_derived_from_the_policy_and_never_list_sensitive_or_pii_as_fields():
    policy = TaskPolicy.load("bmc_mumbai")
    bmc = {r["task"]: r for r in tm.build_matrix() if r["source_id"] == "bmc_mumbai"}
    assert set(bmc) == set(policy.tasks)
    for task, r in bmc.items():
        assert r["inputs"] == policy.tasks[task].inputs and r["targets"] == policy.tasks[task].targets
        assert not {"pii", "complainant_profile"} & (set(r["inputs"]) | set(r["targets"]))
        assert "every unclassified column" in r["forbidden"]
    assert bmc["intake_text"]["operator_confirmations"] == ["description_is_citizen_text"]


def test_manifest_makes_no_real_text_or_before_after_claims():
    rows = tm.build_matrix()
    by = {(r["source_id"], r["task"]): r for r in rows}
    gap = by[("synthetic_civic", "before_after_resolution_evidence")]
    assert gap["status"] == "not_available" and "GAP" in gap["notes"]
    assert by[("nyc311", "intake_text")]["status"] == "unsupported"
    real_text = [r for r in rows if r["source_id"] != "synthetic_civic" and r["task"] == "intake_text" and r["status"] == "supported"]
    assert real_text == []                                       # no real source is declared as supporting text intake outright


def test_only_synthetic_sources_live_on_the_synthetic_track_and_no_real_row_is_pooled():
    for r in tm.build_matrix():
        if r["track"] == "synthetic":
            assert r["source_id"] in ("synthetic_civic", "bmc_mumbai")
        if r["source_id"] != "synthetic_civic":
            assert r["track"] != "hybrid"


def test_idd_has_no_task_rows_that_imply_support():
    assert [r["status"] for r in tm.build_matrix() if r["source_id"] == "idd"] == ["future"]


def test_cli_matrix_prints_the_generated_markdown(capsys):
    from ai.training.src.data_sources import cli
    assert cli.main(["matrix"]) == 0
    assert capsys.readouterr().out.strip() == tm.render_markdown().strip()


def test_bmc_rows_reflect_the_synthetic_origin_no_real_track_no_intake():
    rows = {r["task"]: r for r in tm.build_matrix() if r["source_id"] == "bmc_mumbai"}
    assert all(r["track"] in ("synthetic", "descriptive", "none") for r in rows.values())
    assert rows["intake_text"]["track"] == "none" and "synthetic" in rows["intake_text"]["notes"].lower()
    for t in ("routing_agreement", "triage_priority_prior", "resolution_time_prior", "recurrence_hotspot"):
        assert rows[t]["track"] == "synthetic"
    assert rows["taxonomy_coverage"]["track"] == "descriptive"
    text = (tm.HERE / "TASK_MATRIX.md").read_text(encoding="utf-8")
    assert "SYNTHETIC_PER_COMPETITION" in text
