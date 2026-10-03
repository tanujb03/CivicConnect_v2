# Kaggle runbook: notebooks 06 (YOLO) and 07 (text models) on GPU T4 ×2

General notebook instructions (datasets, bootstrap, bundles) are in `ai/training/README.md` and `docs/RUNBOOK_ML.md`. This file covers the **two-GPU** setup only.

## How the two GPUs are used

| Notebook | Method | Why |
|---|---|---|
| 06 road-damage YOLO | Ultralytics **DDP**: `device=[0, 1]`. Ultralytics itself launches `torch.distributed.run` workers; the notebook process waits, then reloads `best.pt`. | The only multi-GPU mode Ultralytics offers. The notebook process never initialises CUDA before the launch (GPUs are counted with `nvidia-smi`). |
| 07 text models | `torch.nn.DataParallel`, loss computed **outside** the wrapper on the gathered logits. | M6's loss is per-sample cross-entropy, so DP gives the single-GPU gradient exactly, with the same seeded batches, one process for early stopping / checkpoint / ONNX export, and no process launch from a notebook. **M7 is not trained** (the pretrained encoder is exported as it is), so there is no contrastive loss and no in-batch negatives to gather. |

Single GPU, P100 and CPU still work. `CIVIC_NUM_GPUS=1` forces one GPU, `0` the CPU, unset/`auto` uses every visible GPU.

Batch sizes (all **totals**, split evenly): YOLO is fixed per model size so AutoBatch (`batch=-1`, not allowed with several GPUs) is never used: `n` 64, `s` 32 (default `yolov8s.pt`, 2 × 16), `m` 16, `l` 16, `x` 8, SMOKE 16. Each total also fits one 15 GB T4 (single-GPU fallback) and divides by 1, 2 and 4. These are conservative estimates, **not measured**; `CIVIC_YOLO_BATCH` overrides. Ultralytics 8.4.172 does `batch // n_gpus` without checking, so a batch that does not divide would silently shrink; `hardware.split_batch` rounds down to a multiple instead and says so. Text: effective batch 32 = 2 × 16; `CIVIC_GRAD_ACCUM=2` halves the memory per forward with the same gradient. YOLO `workers` is per GPU: 4 cores → 2 per GPU (1 GPU → 4).

## T4 ×2 checklist

**Before the run**
- [ ] The code on Kaggle is what `origin/tanuj` holds when the session starts (the bootstrap does a fresh `git clone --depth 1 --branch tanuj`). Push first. A stale clone fails in the settings/GPU cell with `No module named 'ai.training.src.hardware'`.
- [ ] Session options: **Accelerator = GPU T4 ×2**, **Internet = On**. Internet is needed for the clone, `ultralytics`, pretrained weights, the one-off AMP check model (`yolo26n.pt`) and Ultralytics' `cloudpickle` install on the first multi-GPU launch. (Internet off: weights must come from an attached dataset and the AMP check is skipped with a warning that keeps `amp=True`.)
- [ ] 06: attach the four datasets of notebook 05. 07: attach the corpus dataset (or `CIVIC_CORPUS_DIR`).
- [ ] Run `SMOKE = True` first (06: 1 epoch, 320 px, ~900 images; 07: 2 epochs). Both exercise both GPUs.
- [ ] For the stronger M6 encoder (07 only): uncomment the three `os.environ[...]` lines at the top of the settings cell (`intfloat/multilingual-e5-base`, prefix `query: `, a new version such as `2-base`). If it runs out of memory set `CIVIC_GRAD_ACCUM=2`.

**First lines of output when both GPUs are in use**
- 06 (cell *2 · Find the inputs…*): `GPUs: 2 used of 2 visible (2 x Tesla T4) | total batch 16 = 2 x 8 per GPU | workers 2/GPU | device=[0, 1]` (full run with `yolov8s.pt`: `total batch 32 = 2 x 16 per GPU`). The training cell then shows, forwarded from the workers, `DDP: debug command … torch.distributed.run --nproc_per_node 2 …`, `CUDA:0 (Tesla T4 …)` and `CUDA:1 (Tesla T4 …)`, `AMP: checks passed`, `Using 4 dataloader workers`.
- 07 (cell *2 · Find the corpus…*): `GPUs: 2 used of 2 visible (2 x Tesla T4) | total batch 32 = 2 x 16 per GPU`, then in the training cell `M6 training on 2 GPU(s) (DataParallel): effective batch 32, at most 16 samples per GPU per forward, device cuda` and one line per epoch ending in its seconds.
- `1 used of 2 visible` or `batch 32` without `2 x` means one GPU is in use: check `CIVIC_NUM_GPUS` and the accelerator setting.

**Confirm both GPUs are busy after 2 minutes.** A Jupyter kernel runs one cell at a time, so a second cell with `nvidia-smi` cannot run while training is busy. Instead the training cell prints, 2 and 15 minutes in (and appends to `/kaggle/working/gpu_watch.txt`): `GPU watch @120s: GPU0 Tesla T4 util 9x% mem 5.1/15.0 GB | GPU1 Tesla T4 util …`. A line ending `WARNING: only 1 of 2 GPUs busy` means the second GPU is idle. If the editor offers a console/terminal panel, `watch -n 5 nvidia-smi` there shows the same live. Text M6 is small, so its utilisation can be well below 100 % and the speed-up over one GPU modest: compare `seconds per epoch` in the cell *4 · Compare…* with a run using `CIVIC_NUM_GPUS=1`.

**If the multi-GPU launch fails** (06: `CalledProcessError` from `torch.distributed.run`, NCCL errors, no output for several minutes; 07: an error inside `DataParallel`)
1. Add a first cell `import os; os.environ["CIVIC_NUM_GPUS"] = "1"` and *Restart & Run All*. Everything then runs on GPU 0 exactly as before (same total batch).
2. After a failed DDP launch kill leftover workers (restart the session, or `pkill -f torch.distributed.run`) before retrying, otherwise they still hold GPU memory.
3. Out of memory: 06 `CIVIC_YOLO_BATCH=16` (any multiple of the GPU count); 07 `CIVIC_GRAD_ACCUM=2`.
4. Send the first ~40 lines of the training cell output.

**After training**
- 06: validation of the val split (every epoch and the final one) runs on rank 0 inside the workers; `best.pt` is written by rank 0. The notebook process then evaluates the held-out test groups on GPU 0 and exports ONNX **once, on the CPU** (the graph is device-independent; a GPU export makes Ultralytics pip-install `onnxruntime-gpu`).
- 06 `model_card.json` → `training.hardware` (new): `gpu_count`, `world_size`, `gpu_names`, `parallel` (`DDP`/`none`), `batch_effective`, `batch_per_gpu`, `workers_per_gpu`, `wall_seconds`, `epoch_seconds`. `training.batch` keeps its meaning (the total batch).
- 07 `manifest.json` of M6 → `training_hardware` (new): the same fields plus `grad_accum`, `parallel` (`DataParallel`/`none`); `history[*].seconds` per epoch; M7's manifest only gains `"fine_tuned": false`. The artifact schema (`civic-onnx-text/1`) and tokenizer files are unchanged.

## What is verified where

| Claim | Local (RTX 4050, CPU, Windows) | Needs Kaggle T4 ×2 |
|---|---|---|
| GPU detection without CUDA, batch/worker arithmetic, `CIVIC_NUM_GPUS` | unit tests with mocked 0/1/2/4 GPUs, uneven and forced-single cases | real `nvidia-smi` output of the T4 ×2 machine |
| 07 loss equivalence (loss outside DataParallel, grad accumulation, unwrapped export) | gradient equality of 2 DP replicas (`device_ids=[0, 0]`) vs one device on the real GPU; accumulation vs full batch; CPU and 1-GPU runs of the whole notebook | transfer between two physical GPUs, real speed-up |
| 06 notebook plumbing on CPU and 1 GPU (assembly, train, evaluate, CPU ONNX export, model card) | executed end to end on invented data | real data, real T4 timing |
| 06 Ultralytics DDP launch, NCCL, rank-0 validation, `best.pt` handoff | **not verifiable**: this Windows torch wheel has no libuv and `torch.distributed.run` fails before any worker starts; behaviour taken from the Ultralytics 8.4.172 source and docs | **everything** about the DDP run |
| Worker log forwarding into the cell, GPU watcher | proxy tests and a kernel-level test; watcher printed from a timer thread into a cell | the same on Kaggle's kernel |

Synthetic or invented data gives no accuracy claim; only the plumbing is tested.
