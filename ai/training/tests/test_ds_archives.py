"""Mounts that hold an archive instead of files (what the real Kaggle run showed): census, listing-only profiling, opt-in safe extraction."""
import json
import shutil
import tarfile
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("PIL", reason="Pillow builds the test images")

from ai.training.src.data_sources import archive_tools as at  # noqa: E402
from ai.training.src.data_sources import kaggle_run as kr  # noqa: E402
from ai.training.src.data_sources.image_profile import profile_archive, profile_image_dataset  # noqa: E402
from ai.training.src.data_sources.kaggle_inputs import SPECS, locate, scan_tree  # noqa: E402

from .conftest_real import make_rdd_copy  # noqa: E402

YOLO_CFG = {"rdd2022": {"format": "yolo", "class_names_file": "data.yaml"}}


def zip_tree(src: Path, dest: Path, root_name: str = "") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                z.write(p, (Path(root_name) / p.relative_to(src)).as_posix())
    return dest


def user_layout(tmp_path: Path, layout="yolo_split", **kw) -> tuple[Path, Path]:
    """The shape seen on Kaggle: /kaggle/input/datasets/<user>/rdd2022/<one extension-less file>."""
    src = make_rdd_copy(tmp_path / "src", layout, **kw)
    root = tmp_path / "in"
    mount = root / "datasets" / "tanujbhide" / "rdd2022"
    zip_tree(src, mount / "rdd-2022")                             # NO extension
    return root, src


def cfg_for(tmp_path, root, **kw):
    base = dict(work_dir=tmp_path / "work", input_root=root, accept_terms=["rdd2022"], ack_unverified_license=True)
    base.update(kw)
    return kr.RunConfig(**base)


def stage(res, name):
    return next(s for s in res["stages"] if s["stage"] == name)


# ------------------------------------------------------------------ sniffing / reading
def test_sniff_kind_by_content_not_extension(tmp_path):
    z = zip_tree(make_rdd_copy(tmp_path / "s", "images_only", n=2), tmp_path / "noext")
    t = tmp_path / "t.dat"
    with tarfile.open(t, "w:gz") as tf:
        tf.add(tmp_path / "s", arcname="s")
    raw = tmp_path / "x.bin"
    raw.write_bytes(b"\x00\x01\x02binary")
    txt = tmp_path / "readme"
    txt.write_text("hello\n", encoding="utf-8")
    (tmp_path / "r.rar").write_bytes(b"Rar!\x1a\x07\x00....")
    (tmp_path / "s7").write_bytes(b"7z\xbc\xaf\x27\x1c....")
    assert [at.sniff_kind(p) for p in (z, t, raw, txt, tmp_path / "r.rar", tmp_path / "s7", tmp_path / "missing")] == ["zip", "gzip", None, "text", "rar", "7z", None]
    plain_tar = tmp_path / "p.tar"
    with tarfile.open(plain_tar, "w") as tf:
        tf.add(tmp_path / "s", arcname="s")
    assert at.sniff_kind(plain_tar) == "tar"


def test_reader_lists_and_reads_zip_and_tar_without_extracting(tmp_path):
    src = make_rdd_copy(tmp_path / "s", "yolo_split", n=8)
    z = zip_tree(src, tmp_path / "a.zip")
    t = tmp_path / "a.tgz"
    with tarfile.open(t, "w:gz") as tf:
        tf.add(src, arcname=".")
    for p in (z, t):
        r = at.ArchiveReader(p)
        names = {n for n, _ in r.entries()}
        assert any(n.endswith("data.yaml") for n in names) and sum(n.endswith(".jpg") for n in names) == 8
        yaml_name = next(n for n in names if n.endswith("data.yaml"))
        assert b"D40" in r.read(yaml_name)
        r.close()
    assert not any(tmp_path.glob("extracted*"))


def test_unsupported_and_corrupt_archives_raise_clear_errors(tmp_path):
    (tmp_path / "x.7z").write_bytes(b"7z\xbc\xaf\x27\x1c....")
    with pytest.raises(at.ArchiveError, match="7z is not a supported archive type"):
        at.ArchiveReader(tmp_path / "x.7z")
    (tmp_path / "bad.zip").write_bytes(b"PK\x03\x04junk")
    with pytest.raises(at.ArchiveError, match="cannot be read"):
        at.ArchiveReader(tmp_path / "bad.zip")
    (tmp_path / "single.gz").write_bytes(__import__("gzip").compress(b"just one file"))
    with pytest.raises(at.ArchiveError, match="not a tar archive"):
        at.ArchiveReader(tmp_path / "single.gz")


def test_archive_profile_matches_the_directory_profile_of_the_same_content(tmp_path):
    src = make_rdd_copy(tmp_path / "s", "yolo_split", n=12, countries=("India", "Japan"))
    z = zip_tree(src, tmp_path / "a.zip")
    d, a = profile_image_dataset(src), profile_archive(z)
    for k in ("n_images", "extensions", "format_candidates", "annotation_artifacts", "class_name_files", "class_name_previews", "split_directories_images",
              "country_markers_images", "images_with_same_stem_annotation", "suggested_config_NOT_APPLIED", "n_videos"):
        assert d[k] == a[k], k
    assert "listing only" in a["source"] and d["source"] == "directory"


# ------------------------------------------------------------------ the real-run shape: one extension-less file in the mount
def test_an_extensionless_zip_is_recognised_by_content_and_located(tmp_path):
    root, _ = user_layout(tmp_path)
    st = scan_tree(root / "datasets" / "tanujbhide" / "rdd2022")
    assert st["images"] == 0 and st["extensions"] == {"(none)": 1} and st["content_types_of_unknown_files"] == {"zip": 1}
    assert st["archive_files"][0]["relpath"] == "rdd-2022" and st["archive_files"][0]["kind"] == "zip"
    loc = locate(SPECS["rdd2022"], root)
    assert loc.found and loc.path.name == "rdd2022" and loc.structure["top_level_entries"][0] == {"name": "rdd-2022", "type": "file", "bytes": loc.structure["top_level_entries"][0]["bytes"]}


def test_first_run_lists_the_archive_extracts_nothing_and_says_exactly_what_to_set(tmp_path):
    root, _ = user_layout(tmp_path)
    cfg = cfg_for(tmp_path, root)
    res = kr.run_dataset(cfg, "rdd2022")
    assert res["status"] == "NEEDS_CONFIG"
    lst = stage(res, "archive_listing")["detail"]
    assert lst["archive"] == "rdd-2022" and lst["kind"] == "zip" and lst["n_images_inside"] == 40 and lst["format_candidates_NOT_DECISIONS"][0] == "yolo"
    assert lst["class_name_previews"][0]["names_first_30"] == ["D00", "D10", "D20", "D40"]
    assert "EXTRACT['rdd2022'] = True" in res["next_steps"][0] and "never bundled" in res["next_steps"][0]
    assert not (tmp_path / "work" / "extracted").exists() and not list(cfg.out.rglob("records.jsonl"))          # nothing copied, nothing prepared


def test_with_explicit_extraction_only_useful_members_are_unpacked_and_the_rest_of_the_pipeline_runs(tmp_path):
    src = make_rdd_copy(tmp_path / "src", "yolo_split")
    (src / "clip.mp4").write_bytes(b"x" * 100)
    (src / "notes.docx").write_bytes(b"docx")
    root = tmp_path / "in"
    zip_tree(src, root / "datasets" / "tanujbhide" / "rdd2022" / "rdd-2022")
    cfg = cfg_for(tmp_path, root, extract={"rdd2022": True}, image=YOLO_CFG)
    res = kr.run_dataset(cfg, "rdd2022")
    ex = stage(res, "extraction")["detail"]
    assert ex["files_extracted"] == 81 and ex["skipped_other_types"] == 2 and ex["videos_included"] is False        # 40 images + 40 labels + data.yaml
    got = sorted(p.name for p in (tmp_path / "work" / "extracted" / "rdd2022").rglob("*") if p.is_file())
    assert "clip.mp4" not in got and "notes.docx" not in got and "data.yaml" in got
    assert res["status"] == "OK" and stage(res, "annotation_audit")["detail"]["source_class_counts"] == {"D00": 10, "D10": 10, "D20": 10, "D40": 10}
    assert stage(res, "image_file_and_duplicate_audit")["detail"]["formats_by_magic_bytes"] == {"jpeg": 40}
    s = kr.run_all(cfg, ("rdd2022",))
    names = zipfile.ZipFile(kr.bundle(cfg)).namelist()
    assert s["datasets"]["rdd2022"]["status"] == "OK" and not any("extracted" in n or n.endswith((".jpg", ".txt", ".yaml")) for n in names)
    again = kr.run_dataset(cfg, "rdd2022")
    assert stage(again, "extraction")["detail"]["reused"].endswith("extracted/rdd2022")                              # marker match: not re-copied
    cfg_v = cfg_for(tmp_path / "v", root, extract={"rdd2022": True}, extract_include_videos=True, image=YOLO_CFG)
    assert stage(kr.run_dataset(cfg_v, "rdd2022"), "extraction")["detail"]["files_extracted"] == ex["files_extracted"] + 1


def test_extracted_results_equal_the_results_from_a_plain_directory_copy(tmp_path):
    root_zip, src = user_layout(tmp_path / "z")
    plain_root = tmp_path / "p" / "in"
    shutil.copytree(src, plain_root / "rdd-2022")
    a = kr.run_dataset(cfg_for(tmp_path / "z", root_zip, extract={"rdd2022": True}, image=YOLO_CFG), "rdd2022")
    b = kr.run_dataset(cfg_for(tmp_path / "p", plain_root, image=YOLO_CFG), "rdd2022")
    for st in ("annotation_audit", "mapping_validation"):
        assert stage(a, st)["detail"] == stage(b, st)["detail"], st
    assert stage(a, "prepare")["detail"]["adapter_stats"]["annotated"] == stage(b, "prepare")["detail"]["adapter_stats"]["annotated"] == 40


def test_the_input_tree_is_never_modified_by_listing_or_extraction(tmp_path):
    root, _ = user_layout(tmp_path)
    before = sorted((str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file())
    kr.run_dataset(cfg_for(tmp_path, root), "rdd2022")
    kr.run_dataset(cfg_for(tmp_path, root, extract={"rdd2022": True}, image=YOLO_CFG), "rdd2022")
    assert sorted((str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()) == before


def test_a_mismatching_existing_destination_is_never_deleted(tmp_path):
    root, _ = user_layout(tmp_path)
    dest = tmp_path / "work" / "extracted" / "rdd2022"
    dest.mkdir(parents=True)
    (dest / "precious.txt").write_text("keep me", encoding="utf-8")
    res = kr.run_dataset(cfg_for(tmp_path, root, extract={"rdd2022": True}, image=YOLO_CFG), "rdd2022")
    assert res["status"] == "BLOCKED" and "never deletes" in stage(res, "extraction")["detail"] and (dest / "precious.txt").read_text(encoding="utf-8") == "keep me"


# ------------------------------------------------------------------ safety of extraction
def test_unsafe_member_paths_are_skipped_and_nothing_is_written_outside(tmp_path):
    z = tmp_path / "evil.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("../escape.jpg", b"x")
        zf.writestr("/abs.jpg", b"x")
        zf.writestr("ok/fine.jpg", b"x")
        zf.writestr("ok/..\\win.jpg", b"x")
    dest = tmp_path / "out" / "ds"
    info = at.extract_useful(z, dest)
    assert info["files_extracted"] == 1 and info["skipped_unsafe_paths"] == 3
    assert (dest / "ok" / "fine.jpg").is_file() and not (tmp_path / "out" / "escape.jpg").exists() and not (tmp_path / "abs.jpg").exists()


def test_extraction_refuses_when_it_would_not_fit_and_writes_nothing(tmp_path, monkeypatch):
    src = make_rdd_copy(tmp_path / "s", "images_only", n=5)
    z = zip_tree(src, tmp_path / "a.zip")
    with pytest.raises(at.ArchiveError, match="max_bytes"):
        at.extract_useful(z, tmp_path / "o1", max_bytes=10)
    import collections
    usage = collections.namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda p: usage(100, 99, 1))
    with pytest.raises(at.ArchiveError, match="only 0.0 GB is free"):
        at.extract_useful(z, tmp_path / "o2")
    assert not [p for d in ("o1", "o2") if (tmp_path / d).exists() for p in (tmp_path / d).rglob("*") if p.is_file()]


def test_disk_guard_is_reported_as_blocked_by_the_orchestrator(tmp_path, monkeypatch):
    root, _ = user_layout(tmp_path)
    import collections
    usage = collections.namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda p: usage(100, 99, 1))
    res = kr.run_dataset(cfg_for(tmp_path, root, extract={"rdd2022": True}, image=YOLO_CFG), "rdd2022")
    assert res["status"] == "BLOCKED" and "free on" in stage(res, "extraction")["detail"] and "nothing was extracted" in stage(res, "extraction")["detail"]


# ------------------------------------------------------------------ selection / unsupported / opaque files
def test_several_archives_need_an_explicit_choice(tmp_path):
    root = tmp_path / "in"
    mount = root / "datasets" / "tanujbhide" / "rdd2022"
    zip_tree(make_rdd_copy(tmp_path / "s1", "yolo_split", n=8), mount / "part1")
    zip_tree(make_rdd_copy(tmp_path / "s2", "yolo_split", n=8, countries=("Japan",)), mount / "part2.zip")
    res = kr.run_dataset(cfg_for(tmp_path, root), "rdd2022")
    assert res["status"] == "NEEDS_CONFIG" and "ARCHIVE['rdd2022']" in res["next_steps"][0]
    ok = kr.run_dataset(cfg_for(tmp_path, root, archive={"rdd2022": "part2.zip"}), "rdd2022")
    assert stage(ok, "archive_listing")["detail"]["archive"] == "part2.zip" and stage(ok, "archive_listing")["detail"]["n_images_inside"] == 8


def test_a_tar_gz_without_extension_works_too(tmp_path):
    src = make_rdd_copy(tmp_path / "s", "yolo_split", n=8)
    root = tmp_path / "in"
    mount = root / "datasets" / "tanujbhide" / "rdd2022"
    mount.mkdir(parents=True)
    with tarfile.open(mount / "rdd-2022", "w:gz") as tf:
        tf.add(src, arcname="rdd")
    res = kr.run_dataset(cfg_for(tmp_path, root, extract={"rdd2022": True}, image={"rdd2022": {"format": "yolo", "class_names_file": "rdd/data.yaml"}}), "rdd2022")
    assert stage(res, "archive_listing")["detail"]["kind"] == "gzip" and res["status"] == "OK"


def test_a_7z_or_rar_archive_is_blocked_with_a_reupload_hint(tmp_path):
    root = tmp_path / "in"
    mount = root / "datasets" / "tanujbhide" / "bharatpothole"
    mount.mkdir(parents=True)
    (mount / "data").write_bytes(b"7z\xbc\xaf\x27\x1c" + b"\x00" * 64)
    res = kr.run_dataset(cfg_for(tmp_path, root), "bharatpothole")
    assert res["status"] == "BLOCKED" and "7z/rar" in res["next_steps"][0] and "re-upload it as zip or tar" in res["next_steps"][0]
    assert stage(res, "locate")["detail"]["census"]["archive_files"][0]["kind"] == "7z"


def test_an_opaque_file_gets_a_full_census_in_the_report_instead_of_a_bare_no_images(tmp_path):
    root = tmp_path / "in"
    mount = root / "datasets" / "tanujbhide" / "civicconnect-mumbai-nashik-road-surface-v2"
    mount.mkdir(parents=True)
    (mount / "2").write_text("this is not an archive\n" * 5, encoding="utf-8")
    res = kr.run_dataset(cfg_for(tmp_path, root), "mumbai_nashik_road_surface")
    assert res["status"] == "BLOCKED"
    census = stage(res, "locate")["detail"]["census"]
    assert census["top_level_entries"][0]["name"] == "2" and census["top_level_entries"][0]["type"] == "file"
    assert census["content_types_of_unknown_files"] == {"text": 1} and census["sample_files"][0]["content_type"] == "text"
    msg = res["next_steps"][0]
    assert "no image files found" in msg and "top-level entries: 2 (file" in msg and "content types of unrecognised files {'text': 1}" in msg
    assert json.dumps(res)                                                                                      # report stays serialisable


def test_a_mount_with_images_never_triggers_archive_logic(tmp_path):
    root = tmp_path / "in"
    make_rdd_copy(root / "rdd-2022", "yolo_split", n=8)
    zip_tree(make_rdd_copy(tmp_path / "other", "images_only", n=3), root / "rdd-2022" / "backup.zip")
    res = kr.run_dataset(cfg_for(tmp_path, root, image=YOLO_CFG), "rdd2022")
    assert res["status"] == "OK" and not any(s["stage"] in ("archive_listing", "extraction") for s in res["stages"])


# ================================================================== what the real Kaggle run showed: mounts holding only a saved web page
LANDING = ("<!DOCTYPE html><html><head><title>Road surface images with seasons - Mendeley Data</title></head>"
           "<body>" + "<p>dataset description</p>" * 40 + "</body></html>")


@pytest.mark.parametrize("ds,mount,filename", [
    ("mumbai_nashik_road_surface", "civicconnect-mumbai-nashik-road-surface-v2", "2"),            # URL .../datasets/tj2m7zz4rg/2
    ("rdd2020", "rdd2020-mendeleydata", "1"),                                                      # URL .../datasets/5ty2wb6gvg/1
    ("rdd2022", "rdd2022", "rdd-2022"),                                                            # URL .../datasets/aliabdelmenam/rdd-2022
    ("bharatpothole", "bharatpothole", "bharatpothole"),                                           # URL .../datasets/surbhisaswatimohanty/bharatpothole
])
def test_a_dataset_made_from_a_page_url_is_diagnosed_as_a_saved_web_page_with_the_fix(tmp_path, ds, mount, filename):
    root = tmp_path / "in"
    d = root / "datasets" / "tanujbhide" / mount
    d.mkdir(parents=True)
    (d / filename).write_text(LANDING, encoding="utf-8")
    res = kr.run_dataset(cfg_for(tmp_path, root, accept_terms=[ds]), ds)
    assert res["status"] == "BLOCKED"
    msg = res["next_steps"][0]
    assert "saved WEB PAGE" in msg and "Road surface images with seasons - Mendeley Data" in msg and "landing page, not its data" in msg
    assert "remote file" in msg and "Re-attach the original Kaggle dataset" in msg
    census = stage(res, "locate")["detail"]["census"]
    assert census["content_types_of_unknown_files"] == {"html": 1} and census["sample_files"][0]["html_title"].startswith("Road surface")
    assert not list((tmp_path / "work").rglob("records.jsonl"))


def test_sniffing_distinguishes_html_json_xml_and_plain_text(tmp_path):
    files = {"a": "<!doctype html><html></html>", "b": "<html lang='en'>", "c": '{"x": 1}', "d": "<?xml version='1.0'?><a/>", "e": "just words\n"}
    got = {}
    for name, body in files.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
        got[name] = at.sniff_kind(tmp_path / name)
    assert got == {"a": "html", "b": "html", "c": "json", "d": "xml", "e": "text"}
    prev = at.text_preview(tmp_path / "a")
    assert prev["preview"].startswith("<!doctype html>")


def test_the_attach_instructions_warn_against_page_urls_and_name_the_real_sources():
    from ai.training.src.data_sources.kaggle_inputs import SPECS
    for sid in ("rdd2022", "bharatpothole"):
        assert "Do NOT create your own dataset from the page URL" in SPECS[sid].attach
    for sid in ("mumbai_nashik_road_surface", "rdd2020"):
        a = SPECS[sid].attach
        assert "HTML page" in a and "public-api/zip" in a and "unverified from here" in a
