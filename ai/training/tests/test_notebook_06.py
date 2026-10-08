"""Notebook 06 end to end on INVENTED data (tiny gray images, from-scratch yolov8n on CPU): proves data assembly, id decoding, training, evaluation, the domain check,
ONNX export, the backend-decoder parity check and the bundle all work. Metrics are meaningless here; only the plumbing is tested."""
import json
import random
import zipfile
from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat", reason="optional notebook tooling (nbformat) is not installed")
pytest.importorskip("ultralytics")
pytest.importorskip("onnxruntime")
PIL = pytest.importorskip("PIL.Image")
torch = pytest.importorskip("torch")

HAS_CUDA = torch.cuda.is_available()
# "cpu": the plumbing everywhere. "0": one real GPU. The multi-GPU (Ultralytics DDP) launch cannot run here: the Windows torch wheel has no libuv and torch.distributed.run's static
# rendezvous then fails before any worker starts, and there is only one GPU anyway. It can only be verified on Kaggle T4 x2 (docs/KAGGLE_RUNBOOK.md checklist); the batch / device arithmetic is covered in test_hardware.py.
DEVICES = ["cpu", pytest.param("0", marks=pytest.mark.skipif(not HAS_CUDA, reason="needs a CUDA GPU"))]

NB = Path(__file__).resolve().parents[1] / "notebooks" / "06_road_damage_detector_kaggle.ipynb"
W, H = 640, 480
TRUTH = {0: "D40", 1: "D00", 2: "D10", 3: "D20"}             # the invented id order of the invented YOLO copy


def img(p: Path, size=(96, 72)):
    p.parent.mkdir(parents=True, exist_ok=True)
    PIL.new("RGB", size, (110, 110, 110)).save(p)


def voc(p: Path, stem: str, objs):
    body = "".join(f"<object><name>{n}</name><bndbox><xmin>{b[0]:.1f}</xmin><ymin>{b[1]:.1f}</ymin><xmax>{b[2]:.1f}</xmax><ymax>{b[3]:.1f}</ymax></bndbox></object>" for n, b in objs)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"<annotation><filename>{stem}.jpg</filename><size><width>{W}</width><height>{H}</height></size>{body}</annotation>", encoding="utf-8")


@pytest.fixture()
def inputs(tmp_path):
    rng = random.Random(7)
    r20, r22, bph, mn = (tmp_path / "in" / n for n in ("rdd2020", "rdd2022", "bph", "mn"))
    for i in range(0, 1500, 6):                                                      # 250 India frames, 4 boxes each (one per class) -> 1000 matched boxes
        s = f"India_{i:06d}"
        objs, ylines = [], []
        for cid, name in TRUTH.items():
            x0, y0 = 20 + cid * 140, rng.uniform(20, 300)
            w, h = rng.uniform(40, 100), rng.uniform(40, 100)
            objs.append((name, (x0, y0, x0 + w, y0 + h)))
            ylines.append(f"{cid} {(x0 + w / 2) / W:.6f} {(y0 + h / 2) / H:.6f} {w / W:.6f} {h / H:.6f}")
        img(r20 / "train/train/India/images" / f"{s}.jpg")
        voc(r20 / "train/train/India/annotations/xmls" / f"{s}.xml", s, objs)
        img(r22 / "RDD_SPLIT/train/images" / f"{s}.jpg")
        (r22 / "RDD_SPLIT/train/labels").mkdir(parents=True, exist_ok=True)
        (r22 / "RDD_SPLIT/train/labels" / f"{s}.txt").write_text("\n".join(ylines) + "\n", encoding="utf-8")
    for i in range(60):                                                              # Japan frames only in the YOLO copy
        s = f"Japan_{i * 3:06d}"
        img(r22 / "RDD_SPLIT/val/images" / f"{s}.jpg")
        (r22 / "RDD_SPLIT/val/labels").mkdir(parents=True, exist_ok=True)
        (r22 / "RDD_SPLIT/val/labels" / f"{s}.txt").write_text("3 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    for i in range(80):
        s = f"2025050109_{i // 10:04d}_frame_{i:05d}_jpg.rf.h{i}"
        img(bph / "BharatPotHole/BharatPotHole/train/images" / f"{s}.jpg")
        (bph / "BharatPotHole/BharatPotHole/train/labels").mkdir(parents=True, exist_ok=True)
        (bph / "BharatPotHole/BharatPotHole/train/labels" / f"{s}.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    (bph / "BharatPotHole/BharatPotHole/data.yaml").write_text("nc: 1\nnames: ['pothole']\n", encoding="utf-8")
    for scene in ("Pothole in Rainy Season", "Plain Road"):
        for i in range(8):
            img(mn / "tj2m7zz4rg-2/Road Surface Image/Paved Road" / scene / "Final" / f"Image ({i}).jpg")
    return {"rdd2020": r20, "rdd2022": r22, "bharatpothole": bph, "mumbai_nashik_road_surface": mn}


@pytest.mark.slow
@pytest.mark.parametrize("device", DEVICES)
def test_notebook_06_runs_end_to_end_in_smoke_mode_and_writes_a_complete_bundle(inputs, tmp_path, monkeypatch, device):
    from nbclient import NotebookClient
    work = tmp_path / "work"
    for k, v in {"CIVIC_WORKDIR": str(work), "CIVIC_PATHS_JSON": json.dumps({k: str(v) for k, v in inputs.items()}), "CIVIC_YOLO_MODEL": "yolov8n.yaml",
                 "CIVIC_YOLO_DEVICE": device}.items():
        monkeypatch.setenv(k, v)
    nb = nbformat.read(NB, as_version=4)
    NotebookClient(nb, timeout=1500, kernel_name="python3", resources={"metadata": {"path": str(NB.parent)}}).execute()
    out = "\n".join(o.get("text", "") for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", []))
    assert "Traceback" not in out and "DECODED:" in out and "backend decoder vs Ultralytics" in out and "GPUs: " in out
    zips = list(work.glob("civic_road_damage_smoke-*.zip"))
    assert len(zips) == 1
    names = zipfile.ZipFile(zips[0]).namelist()
    assert {"road_damage/best.onnx", "road_damage/model_card.json", "road_damage/best.pt"} <= set(names)
    card = json.loads(zipfile.ZipFile(zips[0]).read("road_damage/model_card.json"))
    assert card["smoke_run"] is True and card["classes"] == ["D00", "D10", "D20", "D40"] and card["civic_mapping"]["D40"] == ["roads", "pothole"]
    assert card["data"]["rdd2022_id_decoding"]["mapping"] == {str(k): v for k, v in TRUTH.items()} or card["data"]["rdd2022_id_decoding"]["mapping"] == TRUTH
    assert card["data"]["manifest"]["groups_straddling_splits"] == 0 and {"rdd2020", "rdd2022", "bharatpothole"} <= set(card["data"]["manifest"]["by_source"])
    assert card["provenance_and_licences"]["rdd2020"]["licence_status"] == "VERIFIED_PRIMARY" and card["provenance_and_licences"]["bharatpothole"]["licence_status"] == "UNVERIFIED"
    assert set(card["maharashtra_domain_check"]) == {"Pothole in Rainy Season", "Plain Road"} and card["backend_decoder_parity"]["images_with_detections"] >= 0
    assert "limits" in card and any("non-commercial" in x for x in card["limits"])
    hw = card["training"]["hardware"]                               # new keys only; "batch" keeps its meaning (the total batch)
    n = {"cpu": 0, "0": 1}[device]
    assert card["training"]["batch"] == 16 and hw["gpu_count"] == n and hw["batch_effective"] == 16 and hw["batch_per_gpu"] == 16 // max(n, 1) and hw["world_size"] == max(n, 1)
    assert hw["parallel"] == "none" and hw["wall_seconds"] > 0 and len(hw["epoch_seconds"]) == 1 and hw["epoch_seconds"][0] > 0
