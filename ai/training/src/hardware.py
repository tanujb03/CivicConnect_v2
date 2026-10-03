"""GPU detection and batch-size / worker arithmetic for the Kaggle notebooks 06 (YOLO) and 07 (text models).

Detection never imports torch and never initialises CUDA (``nvidia-smi -L`` + ``CUDA_VISIBLE_DEVICES``): Ultralytics DDP launches fresh processes and a CUDA context in the
notebook process would only waste GPU 0 memory. ``CIVIC_NUM_GPUS`` overrides auto-detection (``1`` = single GPU, ``0`` = CPU, ``auto``/unset = every visible GPU; asking for
more than are visible is clamped).
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field

ENV_NUM_GPUS = "CIVIC_NUM_GPUS"
_SMI_LINE = re.compile(r"^GPU (\d+): (.*?)(?: \(UUID: ([^)]+)\))?\s*$")
_YOLO_SIZE = re.compile(r"yolo(?:v)?\d+([nsmlx])(?![a-z])", re.IGNORECASE)

# Fixed TOTAL batch per YOLO size at 640 px (AutoBatch, batch=-1/<1, is rejected by Ultralytics DDP). Chosen so the whole batch would still fit ONE 15 GB T4 with AMP
# (the single-GPU fallback must work) and so it splits evenly over 1, 2 and 4 GPUs. The total stays the same whatever the GPU count, so runs are comparable (Ultralytics'
# gradient accumulation to nbs=64 and weight decay scale with the TOTAL batch). These are conservative estimates, not measurements; override with CIVIC_YOLO_BATCH.
YOLO_TOTAL_BATCH = {"n": 64, "s": 32, "m": 16, "l": 16, "x": 8}
YOLO_BATCH_FALLBACK = 16


@dataclass(frozen=True)
class GpuPlan:
    detected: int                       # GPUs visible to this process (nvidia-smi + CUDA_VISIBLE_DEVICES)
    used: int                           # after CIVIC_NUM_GPUS
    names: tuple[str, ...] = ()
    note: str = ""

    @property
    def device_ids(self) -> list[int]:
        return list(range(self.used))

    @property
    def multi(self) -> bool:
        return self.used > 1


@dataclass(frozen=True)
class BatchPlan:
    requested: int
    effective: int                      # the TOTAL batch per optimizer micro-step across all GPUs
    per_gpu: int                        # largest per-GPU share
    n_gpus: int
    even: bool                          # effective splits evenly over n_gpus
    adjusted: bool                      # effective != requested

    def describe(self) -> str:
        if self.n_gpus <= 1:
            return f"batch {self.effective}"
        shape = f"{self.n_gpus} x {self.per_gpu}" if self.even else f"{self.n_gpus} GPUs, largest share {self.per_gpu}"
        return f"total batch {self.effective} = {shape} per GPU" + (f" (requested {self.requested}, rounded to fit the GPU count)" if self.adjusted else "")


def _smi_lines() -> list[str] | None:
    """Lines of ``nvidia-smi -L`` or None when the tool is missing or fails (no GPU driver)."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "-L"], capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.splitlines() if r.returncode == 0 else None


def visible_gpus(env: Mapping[str, str] | None = None, smi: Callable[[], list[str] | None] = _smi_lines) -> list[str]:
    """Names of the GPUs this process can use, in CUDA order. CUDA_VISIBLE_DEVICES selects and orders them and stops at the first invalid entry, as the driver does."""
    env = os.environ if env is None else env
    lines = smi()
    phys = [(int(m.group(1)), m.group(2).strip(), m.group(3) or "") for m in map(_SMI_LINE.match, lines or []) if m]
    cvd = env.get("CUDA_VISIBLE_DEVICES")
    if cvd is None:
        return [name for _, name, _ in phys]
    out: list[str] = []
    seen: set[str] = set()
    for tok in (t.strip() for t in cvd.split(",")):
        if not tok or tok in seen:
            break
        if tok.isdigit():
            hit = next((p for p in phys if p[0] == int(tok)), None)
            name = hit[1] if hit else ("GPU" if lines is None else None)       # without nvidia-smi the variable is all we have
        else:
            hit = next((p for p in phys if p[2] and p[2].startswith(tok)), None)
            name = hit[1] if hit else None
        if name is None:                                                        # "-1", unknown id, ...: CUDA stops enumerating here
            break
        seen.add(tok)
        out.append(name)
    return out


def plan_gpus(env: Mapping[str, str] | None = None, smi: Callable[[], list[str] | None] = _smi_lines) -> GpuPlan:
    env = os.environ if env is None else env
    names = visible_gpus(env, smi)
    raw = (env.get(ENV_NUM_GPUS) or "").strip().lower()
    if raw in ("", "auto"):
        return GpuPlan(len(names), len(names), tuple(names))
    try:
        want = int(raw)
    except ValueError:
        return GpuPlan(len(names), len(names), tuple(names), f"{ENV_NUM_GPUS}={raw!r} is not an integer or 'auto': ignored")
    if want < 0:
        want = 0
    used = min(want, len(names))
    note = f"{ENV_NUM_GPUS}={want} but only {len(names)} GPU(s) visible: using {used}" if want > len(names) else (f"{ENV_NUM_GPUS}={want}: forced" if want != len(names) else "")
    return GpuPlan(len(names), used, tuple(names[:used]), note)


def split_batch(requested: int, n_gpus: int, *, must_divide: bool) -> BatchPlan:
    """Total batch -> (effective total, per-GPU share).

    ``must_divide=True`` (Ultralytics DDP, which does ``batch // world_size`` and would silently shrink the batch): round DOWN to a multiple of the GPU count (at least one
    sample per GPU). ``False`` (DataParallel splits unevenly happily): keep the requested total and report the largest share.
    """
    n = max(int(n_gpus), 1)
    if int(requested) < 1:
        raise ValueError(f"batch must be a positive integer, got {requested} (AutoBatch / fractional batch is not supported with multiple GPUs)")
    requested = int(requested)
    if n == 1:
        return BatchPlan(requested, requested, requested, 1, True, False)
    if must_divide:
        eff = max(n, requested // n * n)
        return BatchPlan(requested, eff, eff // n, n, True, eff != requested)
    return BatchPlan(requested, requested, math.ceil(requested / n), n, requested % n == 0, False)


def yolo_model_size(model_name: str) -> str | None:
    m = _YOLO_SIZE.search(os.path.basename(str(model_name)))
    return m.group(1).lower() if m else None


def yolo_total_batch(model_name: str, env: Mapping[str, str] | None = None) -> int:
    """The fixed total batch for this model size (``CIVIC_YOLO_BATCH`` overrides)."""
    env = os.environ if env is None else env
    if (env.get("CIVIC_YOLO_BATCH") or "").strip():
        return int(env["CIVIC_YOLO_BATCH"])
    return YOLO_TOTAL_BATCH.get(yolo_model_size(model_name) or "", YOLO_BATCH_FALLBACK)


def yolo_workers(n_gpus: int, cpu_count: int | None = None, cap: int = 4) -> int:
    """Ultralytics ``workers`` is PER RANK and it caps it at cpu_count // n_gpus itself; do the same here so the log shows the real number. 4 cores: 1 GPU -> 4, 2 GPUs -> 2."""
    cpu = cpu_count if cpu_count is not None else (os.cpu_count() or 1)
    return 0 if n_gpus < 1 else max(1, min(cap, cpu // n_gpus))


def ultralytics_device(plan: GpuPlan) -> list[int] | int | str:
    """``device=`` for Ultralytics: [0, 1, ...] for several GPUs, 0 for one, "cpu" otherwise."""
    return plan.device_ids if plan.used >= 2 else (0 if plan.used == 1 else "cpu")


def device_gpu_count(device) -> int:
    """GPUs behind an Ultralytics ``device=`` value: [0, 1] / "0,1" -> 2, 0 / "0" / "cuda:0" -> 1, "cpu" / "" -> 0."""
    if isinstance(device, (list, tuple)):
        return len(device)
    d = str(device).strip().lower()
    return 0 if d in ("", "cpu", "none") else len([t for t in d.split(",") if t.strip()])


def single_device(device) -> int | str:
    """ONE device for evaluation and ONNX export from the notebook process after (multi-GPU) training: "cpu" stays "cpu", anything else becomes the first GPU."""
    if device_gpu_count(device) == 0:
        return "cpu"
    first = device[0] if isinstance(device, (list, tuple)) else str(device).split(",")[0].strip()
    first = str(first).replace("cuda:", "")
    return int(first) if first.isdigit() else first


@dataclass
class TrainingHardware:
    """What a run actually used; written into model_card.json / manifest.json (new keys only, so older readers keep working)."""
    gpu_count: int
    world_size: int = 1                 # processes / replicas taking part (1 on CPU and on one GPU)
    gpu_names: list[str] = field(default_factory=list)
    parallel: str = "none"              # "none" | "DataParallel" | "DDP"
    batch_effective: int = 0
    batch_per_gpu: int = 0
    workers_per_gpu: int | None = None
    grad_accum: int = 1
    wall_seconds: float | None = None
    epoch_seconds: list[float] = field(default_factory=list)
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def banner(plan: GpuPlan, batch: BatchPlan, workers: int | None = None) -> str:
    gpus = f"{plan.used} x {plan.names[0]}" if plan.used and len(set(plan.names)) == 1 else (", ".join(plan.names) or "CPU")
    extra = f" | workers {workers}/GPU" if workers else ""
    return f"GPUs: {plan.used} used of {plan.detected} visible ({gpus}) | {batch.describe()}{extra}" + (f"\n  note: {plan.note}" if plan.note else "")
