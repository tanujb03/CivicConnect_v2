"""Helpers for the real-data architecture tests (no real data is ever used or downloaded)."""
from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "real_data_formats"
NYC_CSV = FIXTURES / "nyc311_format_sample.csv"
CHI_JSONL = FIXTURES / "chicago311_format_sample.jsonl"

XML = """<annotation><folder>x</folder><filename>{name}.jpg</filename><size><width>640</width><height>480</height><depth>3</depth></size>{objs}</annotation>"""
OBJ = """<object><name>{cls}</name><bndbox><xmin>{x0}</xmin><ymin>{y0}</ymin><xmax>{x1}</xmax><ymax>{y1}</ymax></bndbox></object>"""


def write_voc(root: Path, country_dir: str, split: str, stem: str, objs: list[tuple], *, with_image: bool = True, raw: str | None = None) -> None:
    base = root / country_dir / split
    (base / "annotations" / "xmls").mkdir(parents=True, exist_ok=True)
    (base / "images").mkdir(parents=True, exist_ok=True)
    body = raw if raw is not None else XML.format(name=stem, objs="".join(OBJ.format(cls=c, x0=a, y0=b, x1=d, y1=e) for c, a, b, d, e in objs))
    (base / "annotations" / "xmls" / f"{stem}.xml").write_text(body, encoding="utf-8")
    if with_image:
        (base / "images" / f"{stem}.jpg").write_bytes(b"\xff\xd8\xff\xe0FAKEJPEG")


def make_rdd_tree(root: Path) -> Path:
    write_voc(root, "India", "train", "IN_1", [("D40", 10, 10, 100, 100), ("D00", 50, 50, 300, 90), ("D00", 20, 20, 20, 50), ("D44", 5, 5, 40, 40)])
    write_voc(root, "India", "train", "IN_2", [])
    (root / "India" / "test" / "images").mkdir(parents=True, exist_ok=True)
    (root / "India" / "test" / "images" / "IN_T1.jpg").write_bytes(b"\xff\xd8\xff\xe0FAKEJPEG")
    write_voc(root, "Japan", "train", "JP_1", [("D20", 1, 1, 50, 50)])
    write_voc(root, "China_MotorBike", "train", "CN_1", [("D10", 1, 1, 50, 50)])
    write_voc(root, "Czech", "train", "IN_1", [("D40", 1, 1, 60, 60)])           # same stem as an India image
    write_voc(root, "Norway", "train", "BAD", [], raw="<!DOCTYPE x [<!ENTITY a 'b'>]><annotation/>", with_image=False)
    return root


def make_chicago_rows(path: Path, n_dups: int = 60, seed: int = 3) -> Path:
    """Larger INVENTED Chicago-shaped file with duplicate/parent links, for calibration/eval plumbing tests."""
    import random
    rng = random.Random(seed)
    rows = []
    for i in range(n_dups):
        typ = rng.choice(["Pothole in Street Complaint", "Street Light Out Complaint", "No Water Complaint"])
        lat, lon = 41.80 + rng.random() * 0.2, -87.75 + rng.random() * 0.2
        day = rng.randint(1, 20)
        pid = f"FMT-P{i:04d}"
        rows.append({"sr_number": pid, "sr_type": typ, "owner_department": "X", "status": "Open", "created_date": f"2025-09-{day:02d}T08:00:00.000",
                     "latitude": str(lat), "longitude": str(lon), "community_area": 1, "duplicate": "false", "parent_sr_number": "", "legacy_record": "false"})
        rows.append({"sr_number": f"FMT-D{i:04d}", "sr_type": typ, "owner_department": "X", "status": "Open",
                     "created_date": f"2025-09-{min(day + rng.randint(0, 5), 28):02d}T09:00:00.000", "latitude": str(lat + rng.gauss(0, 0.0001)),
                     "longitude": str(lon + rng.gauss(0, 0.0001)), "community_area": 1, "duplicate": "true", "parent_sr_number": pid, "legacy_record": "false"})
        for j in range(2):   # unlinked nearby same-type background requests
            rows.append({"sr_number": f"FMT-N{i:04d}{j}", "sr_type": typ, "owner_department": "X", "status": "Open",
                         "created_date": f"2025-09-{day:02d}T12:00:00.000", "latitude": str(lat + rng.uniform(0.0003, 0.0011)),
                         "longitude": str(lon + rng.uniform(0.0003, 0.0011)), "community_area": 1, "duplicate": "false", "parent_sr_number": "", "legacy_record": "false"})
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


# ------------------------------------------------------------------ fake /kaggle/input tree (invented; for the Kaggle-in-place workflow tests)
def make_real_jpeg(path: Path, seed: int, size=(64, 48)) -> None:
    """A real, decodable JPEG (needs Pillow) whose content depends on ``seed`` (different seeds => visibly different pictures)."""
    from PIL import Image, ImageDraw
    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", size, (seed * 37 % 255, seed * 91 % 255, seed * 53 % 255))
    d = ImageDraw.Draw(im)
    for k in range(4):
        d.rectangle([(seed * (k + 3)) % 40, (seed * (k + 5)) % 30, (seed * (k + 3)) % 40 + 12, (seed * (k + 5)) % 30 + 9], fill=((seed * 17 + k * 80) % 255, (seed * 29 + k * 60) % 255, (k * 70) % 255))
    im.save(path, "JPEG")


def make_fake_kaggle_input(root: Path, *, bmc=True, rdd2022=True, rdd2020=False, bharat=False, nashik=False) -> Path:
    """Creates a tiny INVENTED /kaggle/input-shaped tree. Nothing here is real data."""
    import shutil
    root.mkdir(parents=True, exist_ok=True)
    if bmc:
        comp = root / "competitions" / "mumbai-nagar-seva-bmc-civic-complaint-resolution-2018-2024"
        comp.mkdir(parents=True)
        shutil.copy(FIXTURES / "bmc_mumbai_format_sample.csv", comp / "bmc_train.csv")
        (comp / "bmc_data_dictionary.csv").write_text("column,description\nINVENTED,INVENTED\n", encoding="utf-8")
    for flag, name in ((rdd2022, "rdd2022-india"), (rdd2020, "rdd2020-india")):
        if flag:
            r = root / name
            for i in range(40):
                write_voc(r, "India", "train", f"India_{i:06d}", [("D40", 5, 5, 40, 30)] if i % 2 == 0 else [("D00", 5, 5, 40, 30)], with_image=False)
                make_real_jpeg(r / "India" / "train" / "images" / f"India_{i:06d}.jpg", i)
    if bharat:
        r = root / "bharatpothole"
        for v in range(6):
            for f in range(5):
                make_real_jpeg(r / "images" / f"vid{v}_f{f}.jpg", v * 7 + f)
                (r / "labels").mkdir(exist_ok=True)
                (r / "labels" / f"vid{v}_f{f}.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
        (r / "classes.txt").write_text("pothole\n", encoding="utf-8")
    if nashik:
        r = root / "road-surface-nashik-mumbai"
        for k, cls in enumerate(("Paved Road", "Unpaved Road", "pothole", "speed breaker")):
            for i in range(4):
                make_real_jpeg(r / cls / f"{cls.replace(' ', '_')}_{i}.jpg", 100 + k * 10 + i)
    return root
