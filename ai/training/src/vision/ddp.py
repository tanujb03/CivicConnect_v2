"""Make Ultralytics' multi-GPU (DDP) training usable from a notebook.

With ``device=[0, 1]`` Ultralytics does not train in the notebook process: ``trainer.train()`` writes a temp script and runs ``torch.distributed.run`` through ``subprocess.run``.
A Jupyter kernel does not forward a child process's output into the cell, so the per-epoch log of the workers would only show up in the server console. ``session`` swaps the
``subprocess`` name inside ``ultralytics.engine.trainer`` for a proxy whose ``run`` streams the child's output (progress bars included) to ``sys.stdout`` while it runs, and starts
the GPU watcher (``hardware.start_gpu_watch``). Nothing else about the launch changes; if Ultralytics no longer has that attribute the proxy is simply skipped.
"""
from __future__ import annotations

import codecs
import contextlib
import os
import subprocess
import sys
import time
import types

from ai.training.src import hardware as hw


class StreamingSubprocess:
    """Stands in for the ``subprocess`` module: ``run`` forwards the child's merged stdout/stderr to ``sys.stdout`` as it arrives (unbuffered, UTF-8, ``\\r`` kept)."""

    def __init__(self, real=subprocess):
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    def run(self, cmd, check=False, **kw):
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8", **(kw.pop("env", None) or {})}
        p = self._real.Popen(cmd, stdout=self._real.PIPE, stderr=self._real.STDOUT, env=env, **kw)
        dec = codecs.getincrementaldecoder("utf-8")(errors="replace")
        try:
            while chunk := p.stdout.read1(4096):
                sys.stdout.write(dec.decode(chunk))
                sys.stdout.flush()
            sys.stdout.write(dec.decode(b"", final=True))
            rc = p.wait()
        except BaseException:                      # kernel interrupted: do not leave the workers running
            p.kill()
            p.wait()
            raise
        if check and rc:
            raise self._real.CalledProcessError(rc, cmd)
        return self._real.CompletedProcess(cmd, rc)


@contextlib.contextmanager
def stream_child_output():
    try:
        import ultralytics.engine.trainer as trainer
    except ImportError:
        yield
        return
    real = getattr(trainer, "subprocess", None)
    if real is None:
        yield
        return
    trainer.subprocess = StreamingSubprocess(real)
    try:
        yield
    finally:
        trainer.subprocess = real


@contextlib.contextmanager
def session(n_gpu: int, watch_file=None):
    """Around ``model.train(...)``: the GPU watcher for any GPU run, the child-output proxy when Ultralytics will launch DDP workers (several GPUs)."""
    run = types.SimpleNamespace(seconds=0.0)               # run.seconds = wall-clock of the block, set on exit
    t0 = time.time()
    timers = hw.start_gpu_watch(n_gpu, out_file=watch_file) if n_gpu else []
    try:
        with stream_child_output() if n_gpu > 1 else contextlib.nullcontext():
            yield run
    finally:
        run.seconds = round(time.time() - t0, 1)
        for t in timers:
            t.cancel()
