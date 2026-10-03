"""GPU detection (mocked nvidia-smi, no CUDA) and the batch / worker arithmetic shared by notebooks 06 and 07."""
import pytest

from ai.training.src import hardware as hw


def smi(n: int, name: str = "Tesla T4"):
    lines = [f"GPU {i}: {name} (UUID: GPU-0000000{i}-aaaa-bbbb)" for i in range(n)]
    return lambda: lines if n else None


@pytest.mark.parametrize("n", [0, 1, 2, 4])
def test_detects_the_visible_gpu_count_without_torch(n):
    p = hw.plan_gpus({}, smi(n))
    assert (p.detected, p.used) == (n, n) and p.device_ids == list(range(n)) and p.multi == (n > 1)


def test_nvidia_smi_failure_means_no_gpu():
    assert hw.plan_gpus({}, lambda: None).used == 0
    assert hw.visible_gpus({}, lambda: []) == []


@pytest.mark.parametrize("cvd,expected", [("0", 1), ("0,1", 2), ("1", 1), ("", 0), ("-1", 0), ("0,5", 1), ("1,0", 2), ("0,0", 1), ("3,0", 0)])
def test_cuda_visible_devices_selects_and_stops_at_the_first_invalid_entry(cvd, expected):
    assert hw.plan_gpus({"CUDA_VISIBLE_DEVICES": cvd}, smi(2)).used == expected


def test_cuda_visible_devices_accepts_uuids_and_works_without_nvidia_smi():
    assert hw.plan_gpus({"CUDA_VISIBLE_DEVICES": "GPU-00000001"}, smi(2)).used == 1
    assert hw.plan_gpus({"CUDA_VISIBLE_DEVICES": "0,1"}, lambda: None).used == 2        # container without nvidia-smi: the variable is all we have
    assert hw.plan_gpus({"CUDA_VISIBLE_DEVICES": "GPU-nope"}, lambda: None).used == 0


@pytest.mark.parametrize("raw,detected,used,noted", [("1", 2, 1, True), ("1", 4, 1, True), ("2", 4, 2, True), ("auto", 2, 2, False), ("", 2, 2, False), ("2", 2, 2, False),
                                                     ("0", 2, 0, True), ("8", 2, 2, True), ("-3", 2, 0, True), ("two", 2, 2, True)])
def test_civic_num_gpus_forces_clamps_or_falls_back_to_auto(raw, detected, used, noted):
    p = hw.plan_gpus({"CIVIC_NUM_GPUS": raw}, smi(detected))
    assert (p.detected, p.used, bool(p.note)) == (detected, used, noted)


def test_forced_single_gpu_keeps_a_single_device():
    p = hw.plan_gpus({"CIVIC_NUM_GPUS": "1"}, smi(2))
    assert p.device_ids == [0] and not p.multi and hw.ultralytics_device(p) == 0 and len(p.names) == 1


def test_ultralytics_device_follows_the_gpu_count():
    assert hw.ultralytics_device(hw.plan_gpus({}, smi(2))) == [0, 1]
    assert hw.ultralytics_device(hw.plan_gpus({}, smi(4))) == [0, 1, 2, 3]
    assert hw.ultralytics_device(hw.plan_gpus({}, smi(1))) == 0
    assert hw.ultralytics_device(hw.plan_gpus({}, smi(0))) == "cpu"


@pytest.mark.parametrize("req,n,eff,per,adj", [(32, 1, 32, 32, False), (32, 2, 32, 16, False), (32, 4, 32, 8, False), (33, 2, 32, 16, True), (31, 2, 30, 15, True),
                                                (30, 4, 28, 7, True), (3, 4, 4, 1, True), (1, 2, 2, 1, True), (16, 0, 16, 16, False)])
def test_yolo_batch_must_divide_evenly_and_is_rounded_down(req, n, eff, per, adj):
    b = hw.split_batch(req, n, must_divide=True)
    assert (b.effective, b.per_gpu, b.adjusted) == (eff, per, adj) and b.even and b.effective % max(n, 1) == 0


@pytest.mark.parametrize("req,n,per,even", [(32, 2, 16, True), (33, 2, 17, False), (32, 4, 8, True), (30, 4, 8, False), (5, 2, 3, False), (32, 1, 32, True)])
def test_text_batch_keeps_the_effective_batch_and_reports_the_largest_share(req, n, per, even):
    b = hw.split_batch(req, n, must_divide=False)
    assert (b.effective, b.per_gpu, b.even, b.adjusted) == (req, per, even, False)


@pytest.mark.parametrize("bad", [0, -1])
def test_autobatch_values_are_rejected(bad):
    with pytest.raises(ValueError, match="positive integer"):
        hw.split_batch(bad, 2, must_divide=True)


def test_every_default_yolo_batch_splits_over_1_2_and_4_gpus_without_change():
    assert all(hw.split_batch(v, n, must_divide=True).effective == v for v in hw.YOLO_TOTAL_BATCH.values() for n in (1, 2, 4))


@pytest.mark.parametrize("name,size", [("yolov8s.pt", "s"), ("yolov8n.yaml", "n"), ("yolo11m.pt", "m"), ("yolo26x.pt", "x"), ("/w/yolov8l.pt", "l"), ("custom.pt", None), ("yolov8seg.pt", None)])
def test_yolo_size_is_read_from_the_model_name(name, size):
    assert hw.yolo_model_size(name) == size


def test_yolo_total_batch_table_fallback_and_override():
    assert hw.yolo_total_batch("yolov8s.pt", {}) == 32 and hw.yolo_total_batch("yolov8n.pt", {}) == 64 and hw.yolo_total_batch("mystery.pt", {}) == 16
    assert hw.yolo_total_batch("yolov8s.pt", {"CIVIC_YOLO_BATCH": "48"}) == 48


@pytest.mark.parametrize("n,cpu,expected", [(0, 4, 0), (1, 4, 4), (2, 4, 2), (4, 4, 1), (8, 4, 1), (1, 16, 4), (2, 16, 4)])
def test_yolo_workers_are_per_gpu_and_capped_at_the_core_share(n, cpu, expected):
    assert hw.yolo_workers(n, cpu) == expected


def test_banner_shows_gpu_count_and_per_gpu_batch():
    p = hw.plan_gpus({}, smi(2))
    text = hw.banner(p, hw.split_batch(32, 2, must_divide=True), 2)
    assert "2 used of 2 visible (2 x Tesla T4)" in text and "total batch 32 = 2 x 16 per GPU" in text and "workers 2/GPU" in text
    assert "CPU" in hw.banner(hw.plan_gpus({}, smi(0)), hw.split_batch(8, 0, must_divide=True))


def test_training_record_is_plain_json():
    import json
    rec = hw.TrainingHardware(gpu_count=2, gpu_names=["T4", "T4"], parallel="DDP", batch_effective=32, batch_per_gpu=16).as_dict()
    assert json.loads(json.dumps(rec))["batch_per_gpu"] == 16 and rec["epoch_seconds"] == []
