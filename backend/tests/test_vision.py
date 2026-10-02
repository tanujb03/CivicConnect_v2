"""Local road-damage model in the intake gateway: numpy pre/post-processing, a REAL onnxruntime session on a tiny hand-built ONNX graph, and the merge policy.

The ONNX graph is a constant-output stand-in (it ignores the pixels), so these tests prove the plumbing and the decoding, not detection quality."""
import io
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from ai.inference.providers.fake import FakeProvider  # noqa: E402
from ai.inference.schemas import EvidenceInput  # noqa: E402
from ai.inference.tests.conftest import INTAKE_OK  # noqa: E402
from backend.ai_gateway import configure_gateway  # noqa: E402
from backend.ai_gateway import vision as V  # noqa: E402
from backend.core.security import create_access_token  # noqa: E402
from backend.main import app  # noqa: E402
from backend.tests.test_ai_gateway import Env  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


def auth(role="citizen", sub="u-test"):
    return {"Authorization": f"Bearer {create_access_token(sub, role)}"}


@pytest.fixture(autouse=True)
def _reset():
    yield
    configure_gateway(None)


def jpeg_bytes(w=1280, h=640):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (90, 90, 90)).save(buf, "JPEG")
    return buf.getvalue()


# ------------------------------------------------------------------------------------------------ pure numpy
def test_letterbox_keeps_aspect_and_decode_undoes_it():
    img = np.zeros((640, 1280, 3), np.uint8)
    boxed, scale, pad = V.letterbox(img, 640)
    assert boxed.shape == (640, 640, 3) and scale == 0.5 and pad == (0.0, 160.0)
    raw = np.zeros((1, 8, 3), np.float32)                                  # (1, 4+nc, N)
    raw[0, :, 0] = [320, 320, 100, 80, 0, 0, 0, 0.9]                       # pothole (class 3)
    raw[0, :, 1] = [322, 322, 100, 80, 0, 0, 0, 0.8]                       # same pothole, lower score: removed by NMS
    raw[0, :, 2] = [100, 200, 50, 50, 0.6, 0, 0, 0]                        # crack (class 0)
    out = V.decode_yolov8(raw, 4, conf=0.25, iou=0.45, scale=scale, pad=pad, orig_wh=(1280, 640))
    assert [(c, round(s, 2)) for c, s, _ in out] == [(3, 0.9), (0, 0.6)]
    assert [round(v) for v in out[0][2]] == [540, 240, 740, 400]
    assert V.decode_yolov8(raw * 0.1, 4, conf=0.25, iou=0.45, scale=scale, pad=pad, orig_wh=(1280, 640)) == []
    with pytest.raises(ValueError):
        V.decode_yolov8(np.zeros((1, 9, 5)), 4, conf=0.1, iou=0.5, scale=1, pad=(0, 0), orig_wh=(10, 10))


# ------------------------------------------------------------------------------------------------ a real onnxruntime session
@pytest.fixture()
def tiny_model(tmp_path):
    onnx = pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")
    from onnx import TensorProto, helper, numpy_helper
    const = np.zeros((1, 8, 3), np.float32)
    const[0, :, 0] = [320, 320, 100, 80, 0, 0, 0, 0.9]
    const[0, :, 1] = [100, 200, 50, 50, 0.6, 0, 0, 0]
    const[0, :, 2] = [10, 10, 5, 5, 0.05, 0, 0, 0]
    nodes = [helper.make_node("ReduceSum", ["images"], ["s"], keepdims=0), helper.make_node("Mul", ["s", "zero"], ["z"]), helper.make_node("Add", ["z", "const"], ["output0"])]
    g = helper.make_graph(nodes, "tiny", [helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, 640, 640])],
                          [helper.make_tensor_value_info("output0", TensorProto.FLOAT, [1, 8, 3])],
                          [numpy_helper.from_array(np.array(0, np.float32), "zero"), numpy_helper.from_array(const, "const")])
    m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)])
    m.ir_version = 8
    onnx.save(m, str(tmp_path / "best.onnx"))
    (tmp_path / "model_card.json").write_text('{"model_name": "tiny-test", "version": "0", "classes": ["D00","D10","D20","D40"]}', encoding="utf-8")
    return tmp_path


def test_detector_runs_a_real_session_and_maps_to_civic_categories(tiny_model):
    det = V.OnnxRoadDamageDetector(tiny_model)
    a = det.detect(jpeg_bytes(), "ev-1")
    assert a.model == "tiny-test@0" and (a.width, a.height) == (1280, 640)
    assert [(d.class_code, d.category, d.subcategory) for d in a.detections] == [("D40", "roads", "pothole"), ("D00", "roads", None)]
    assert [round(v) for v in a.detections[0].box] == [540, 240, 740, 400]
    best = V.summarize([a])
    assert best["subcategory"] == "pothole" and best["evidence_id"] == "ev-1"
    assert V.build_from_env({"AI_VISION_ONNX_PATH": str(tiny_model)}) is not None
    assert V.build_from_env({"AI_VISION_ONNX_PATH": str(tiny_model / "missing")}) is None and V.build_from_env({}) is None     # optional: never fatal


# ------------------------------------------------------------------------------------------------ gateway merge policy
class StubVision:
    def __init__(self, code="D40", conf=0.9, boom=False):
        self.code, self.conf, self.boom = code, conf, boom

    def analyze(self, evidence):
        if self.boom:
            raise RuntimeError("model exploded")
        cat = ("roads", "pothole" if self.code == "D40" else None)
        return V.ImageAnalysis(evidence.evidence_id, [V.Detection(self.code, "pothole" if self.code == "D40" else "crack", self.conf, [1, 2, 3, 4], *cat)], 10, 10, "stub@1")


def setup(provider=None, vision=None):
    env = Env(provider)
    env.gateway.vision = vision
    env.evidence.register(EvidenceInput(evidence_id="img-1", media_type="IMAGE", mime_type="image/jpeg", data=b"x"), owner_id="u-test")
    configure_gateway(env.gateway)
    return env


def intake(**body):
    return client.post("/api/v1/cases/intake/analyze", headers=auth(), json={"evidence_ids": ["img-1"], **body})


def test_photo_only_report_without_any_other_ai_gets_a_local_proposal_the_citizen_must_confirm():
    setup(None, StubVision("D40", 0.91))
    b = intake().json()
    assert b["proposal"]["category"] == "roads" and b["proposal"]["subcategory"] == "pothole" and b["proposal"]["suggested_department"] == "ROADS"
    assert b["requires_confirmation"] is True and 0 < b["confidence"] <= 0.8 and b["proposal"]["severity"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert any(w.startswith("LOCAL_VISION_USED") for w in b["warnings"]) and any("Local road-damage model" in r for r in b["proposal"]["reasons"])
    assert b["image_analysis"][0]["detections"][0]["class_code"] == "D40" and b["ai_metadata"]["local_vision"]["used_for_proposal"] is True


def test_cracks_give_the_category_only():
    setup(None, StubVision("D00", 0.7))
    b = intake().json()
    assert b["proposal"]["category"] == "roads" and b["proposal"]["subcategory"] is None


def test_a_confident_provider_answer_is_kept_and_a_disagreement_is_flagged():
    setup(FakeProvider(structured={"intake": {**INTAKE_OK, "category": "sanitation", "subcategory": "garbage_overflow", "confidence": 0.93}}), StubVision("D40", 0.9))
    b = intake(text="garbage everywhere").json()
    assert b["proposal"]["category"] == "sanitation" and not any(w.startswith("LOCAL_VISION_USED") for w in b["warnings"])
    assert any(w.startswith("VISION_DISAGREES") for w in b["warnings"]) and b["image_analysis"]


def test_a_failing_image_model_never_fails_the_intake():
    setup(None, StubVision(boom=True))
    r = intake()
    assert r.status_code == 200 and any(w.startswith("IMAGE_MODEL_FAILED") for w in r.json()["warnings"]) and r.json()["image_analysis"] == []


def test_without_a_local_model_nothing_changes():
    setup(None, None)
    b = intake().json()
    assert b["image_analysis"] == [] and b["proposal"]["category"] == "other" and "local_vision" not in (b["ai_metadata"] or {})


def test_end_to_end_with_a_real_onnx_session(tiny_model):
    setup(None, V.LocalVisionAnalyzer(V.OnnxRoadDamageDetector(tiny_model)))
    env_ev = EvidenceInput(evidence_id="img-1", media_type="IMAGE", mime_type="image/jpeg", data=jpeg_bytes())
    from backend.ai_gateway.deps import get_gateway
    get_gateway().evidence.register(env_ev, owner_id="u-test")
    b = intake().json()
    assert b["proposal"]["subcategory"] == "pothole" and b["image_analysis"][0]["model"] == "tiny-test@0" and len(b["image_analysis"][0]["detections"]) == 2
