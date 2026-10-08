"""Child-process output of Ultralytics' DDP launch must reach the notebook cell (a Jupyter kernel does not forward it by itself)."""
import subprocess
import sys

import pytest

from ai.training.src.vision import ddp

nbformat = pytest.importorskip("nbformat", reason="optional notebook tooling (nbformat) is not installed")
pytest.importorskip("ultralytics")


def test_proxy_streams_stdout_and_stderr_and_keeps_carriage_returns(capsys):
    r = ddp.StreamingSubprocess().run([sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.stdout.write('50%\\r100%\\n'); print('ok ✅')"], check=True)
    text = capsys.readouterr().out
    assert r.returncode == 0 and "out" in text and "err" in text and "50%\r100%" in text and "ok ✅" in text


def test_proxy_raises_like_subprocess_run_on_failure_and_still_shows_the_output(capsys):
    with pytest.raises(subprocess.CalledProcessError) as e:
        ddp.StreamingSubprocess().run([sys.executable, "-c", "print('worker crashed'); raise SystemExit(3)"], check=True)
    assert e.value.returncode == 3 and "worker crashed" in capsys.readouterr().out
    assert ddp.StreamingSubprocess().run([sys.executable, "-c", "raise SystemExit(2)"]).returncode == 2        # check=False returns the code


def test_session_patches_ultralytics_only_for_several_gpus_and_restores_it():
    import ultralytics.engine.trainer as trainer
    real = trainer.subprocess
    with ddp.session(1):
        assert trainer.subprocess is real
    with ddp.session(0):
        assert trainer.subprocess is real
    with ddp.session(2):
        assert isinstance(trainer.subprocess, ddp.StreamingSubprocess) and trainer.subprocess.CalledProcessError is subprocess.CalledProcessError
    assert trainer.subprocess is real


@pytest.mark.slow
def test_child_output_reaches_the_notebook_cell_through_the_proxy():
    """A Jupyter kernel does not forward a plain child's output into the cell; the proxy (what trainer.train() calls once it is installed) does."""
    import pathlib

    from nbclient import NotebookClient
    code = "\n".join(["import sys", "import ultralytics.engine.trainer as T", "from ai.training.src.vision import ddp",
                      "with ddp.session(2) as run:", "    T.subprocess.run([sys.executable, '-c', 'print(\"CHILD-LINE\")'], check=True)", "print('seconds', run.seconds)"])
    nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(code)])
    NotebookClient(nb, timeout=120, kernel_name="python3", resources={"metadata": {"path": str(pathlib.Path(__file__).resolve().parents[3])}}).execute()
    out = "".join(o.get("text", "") for o in nb.cells[0].outputs)
    assert "CHILD-LINE" in out and "seconds " in out
