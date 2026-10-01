"""Discovery of attached Kaggle inputs: found by name AND structure, explicit overrides, and precise 'what is missing' messages."""
import os

import pytest

from ai.training.src.data_sources import kaggle_inputs as ki
from ai.training.src.data_sources.kaggle_inputs import (
    SPECS,
    describe_inputs,
    input_root,
    locate,
    mounted_dirs,
    pick_tabular_file,
    scan_tree,
)

pytest.importorskip("PIL", reason="the invented Kaggle tree uses real tiny JPEGs")

from .conftest_real import make_fake_kaggle_input, write_voc  # noqa: E402


def snapshot(root):
    return sorted((str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file())


def test_input_root_precedence(monkeypatch, tmp_path):
    monkeypatch.delenv(ki.ENV_ROOT, raising=False)
    assert input_root() == ki.DEFAULT_ROOT
    monkeypatch.setenv(ki.ENV_ROOT, str(tmp_path))
    assert input_root() == tmp_path
    assert input_root(tmp_path / "x") == tmp_path / "x"


def test_all_three_kaggle_mount_layouts_are_scanned(tmp_path):
    (tmp_path / "flat-slug").mkdir()
    (tmp_path / "datasets" / "owner" / "slug").mkdir(parents=True)
    (tmp_path / "competitions" / "comp-slug").mkdir(parents=True)
    (tmp_path / "stray.txt").write_text("x", encoding="utf-8")
    names = [str(p.relative_to(tmp_path)) for p in mounted_dirs(tmp_path)]
    assert names == ["competitions/comp-slug", "datasets/owner/slug", "flat-slug"]
    assert mounted_dirs(tmp_path / "missing") == []


def test_specs_cover_exactly_the_requested_datasets_without_invented_kaggle_slugs():
    assert set(SPECS) == {"bmc_mumbai", "mumbai_nashik_road_surface", "rdd2022", "rdd2020", "bharatpothole"}
    assert SPECS["bmc_mumbai"].kind == "tabular" and all(SPECS[i].kind == "images" for i in SPECS if i != "bmc_mumbai")
    assert SPECS["rdd2022"].default_format == SPECS["rdd2020"].default_format == "voc" and SPECS["bharatpothole"].default_format is None
    assert SPECS["mumbai_nashik_road_surface"].default_format is None
    assert "surbhisaswatimohanty/bharatpothole" in SPECS["bharatpothole"].attach            # the only slug that comes from primary evidence on a card
    assert "private" in SPECS["mumbai_nashik_road_surface"].attach.lower()                # not hosted on Kaggle by its authors: user uploads it


def test_bmc_is_found_in_a_competition_mount_by_name_and_structure(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in")
    loc = locate(SPECS["bmc_mumbai"], root)
    assert loc.found and loc.how == "name+structure" and loc.path.name.startswith("mumbai-nagar-seva-bmc")
    assert {f["relpath"] for f in loc.structure["tabular_files"]} == {"bmc_train.csv", "bmc_data_dictionary.csv"}


def test_rdd_names_do_not_cross_match_and_other_datasets_are_not_found(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in")                      # attaches RDD2022 India only
    assert locate(SPECS["rdd2022"], root).found
    miss = locate(SPECS["rdd2020"], root)
    assert not miss.found and "NOT FOUND" in miss.message and "rdd2022-india" in miss.message and "HOW TO ATTACH" in miss.message
    assert "competitions/mumbai-nagar-seva" in miss.message                     # lists what IS attached
    for sid in ("bharatpothole", "mumbai_nashik_road_surface"):
        assert not locate(SPECS[sid], root).found


def test_a_name_match_without_the_expected_structure_is_rejected_not_used(tmp_path):
    (tmp_path / "rdd2022-india").mkdir()
    (tmp_path / "rdd2022-india" / "readme.txt").write_text("no annotations here", encoding="utf-8")
    loc = locate(SPECS["rdd2022"], tmp_path)
    assert not loc.found and loc.candidates_rejected and "annotations" in loc.message and "NOT USABLE" in loc.message
    (tmp_path / "bmc-civic-empty").mkdir()
    assert "no CSV" in locate(SPECS["bmc_mumbai"], tmp_path).message
    (tmp_path / "bharatpothole").mkdir()
    assert "mount is empty" in locate(SPECS["bharatpothole"], tmp_path).message


def test_videos_only_mounts_are_reported_as_needing_frame_extraction(tmp_path):
    (tmp_path / "bharatpothole").mkdir()
    (tmp_path / "bharatpothole" / "clip.mp4").write_bytes(b"x")
    assert "no image files" in locate(SPECS["bharatpothole"], tmp_path).message


def test_explicit_override_wins_and_is_still_validated(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", bmc=False, rdd2022=False)
    odd = tmp_path / "somewhere" / "my-copy"
    write_voc(odd, "India", "train", "India_1", [("D40", 1, 1, 9, 9)])
    (odd / "India" / "train" / "images" / "India_1.jpg").write_bytes(b"x")
    loc = locate(SPECS["rdd2022"], root, override=odd)
    assert loc.found and loc.how == "override" and loc.path == odd
    assert not locate(SPECS["rdd2022"], root, override=tmp_path / "nope").found
    assert "does not exist" in locate(SPECS["rdd2022"], root, override=tmp_path / "nope").message
    bad = tmp_path / "empty-dir"
    bad.mkdir()
    assert "fails the structure check" in locate(SPECS["rdd2022"], root, override=bad).message


def test_missing_input_root_says_so_and_how_to_override(tmp_path):
    loc = locate(SPECS["bharatpothole"], tmp_path / "no_kaggle_here")
    assert not loc.found and "does not exist" in loc.message and ki.ENV_ROOT in loc.message


def test_discovery_only_reads_never_modifies_the_input_tree(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in", rdd2020=True, bharat=True, nashik=True)
    before = snapshot(root)
    for spec in SPECS.values():
        locate(spec, root)
    describe_inputs(root)
    scan_tree(root)
    assert snapshot(root) == before


def test_describe_inputs_lists_mounts_with_coarse_counts(tmp_path):
    root = make_fake_kaggle_input(tmp_path / "in")
    d = {x["mount"].rsplit("/", 1)[-1]: x for x in describe_inputs(root)}
    assert d["rdd2022-india"]["images"] == 40 and d["rdd2022-india"]["xml_annotation_files"] == 40


def test_scan_tree_cap_is_reported(tmp_path):
    for i in range(10):
        (tmp_path / f"f{i}.csv").write_text("a", encoding="utf-8")
    s = scan_tree(tmp_path, cap=5)
    assert s["capped"] is True and s["files"] == 6


@pytest.mark.parametrize("names,explicit,expect_found,why", [
    (["bmc_train.csv", "bmc_test.csv", "bmc_data_dictionary.csv"], None, True, "the only file"),
    (["a_train_part1.csv", "a_train_part2.csv"], None, False, "2 candidates"),
    (["data.csv", "dictionary.csv"], None, False, "2 candidates"),
])
def test_pick_tabular_file_never_chooses_when_ambiguous(tmp_path, names, explicit, expect_found, why):
    for n in names:
        (tmp_path / n).write_text("a,b\n1,2\n", encoding="utf-8")
    from ai.training.src.data_sources.kaggle_inputs import Location
    loc = Location("bmc_mumbai", True, tmp_path, structure=scan_tree(tmp_path))
    f, msg = pick_tabular_file(loc)
    assert (f is not None) == expect_found and why in msg
    if expect_found:
        assert f.name == "bmc_train.csv"
    else:
        assert "FILES['bmc_mumbai']" in msg and "withheld" in msg


def test_pick_tabular_file_explicit_and_unlocated(tmp_path):
    from ai.training.src.data_sources.kaggle_inputs import Location
    p = tmp_path / "x.csv"
    p.write_text("a\n1\n", encoding="utf-8")
    assert pick_tabular_file(Location("bmc_mumbai", False), p)[0] == p
    assert pick_tabular_file(Location("bmc_mumbai", False), tmp_path / "no.csv")[0] is None
    assert pick_tabular_file(Location("bmc_mumbai", False))[0] is None and os.path.exists(p)
