from pathlib import Path

from ai.training.src import doctor
from ai.training.tests.optional_deps import requires_scipy, requires_sklearn


def test_doctor_reports_names_only_and_flags_what_is_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                                 # the doctor also looks for .env in the cwd: never the developer's real one
    secret = "sk-very-secret-value"
    rows, ok = doctor.run({"GEMINI_API_KEY": secret, "AI_TEXT_ONNX_PATH": str(tmp_path / "nope")}, repo=tmp_path)
    flat = " ".join(f"{s} {i} {d}" for s, i, d in rows)
    assert secret not in flat and not ok
    by = {i: s for s, i, _ in rows}
    assert by["GEMINI_API_KEY"] == "OK" and by["GROQ_API_KEY"] == "MISSING" and by["AI_INTAKE_MODEL"] == "MISSING" and by["AI_TEXT_ONNX_PATH"] == "MISSING"
    assert by["AI_VISION_ONNX_PATH"] == "INFO" and by[".env"] == "MISSING"


@requires_scipy
@requires_sklearn
def test_doctor_is_satisfied_by_a_complete_cloud_configuration(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("X=1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "m6").mkdir()
    env = {"GROQ_API_KEY": "k", "AI_INTAKE_MODEL": "a", "AI_ANALYTICS_MODEL": "b", "AI_TRANSCRIPTION_MODEL": "c", "AI_TEXT_ONNX_PATH": "m6"}
    rows, ok = doctor.run(env, repo=Path(tmp_path))
    assert ok and {i: s for s, i, _ in rows}["AI_TEXT_ONNX_PATH"] == "OK"
