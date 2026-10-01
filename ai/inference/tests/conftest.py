from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from ai.inference.config import AIPolicy, load_taxonomy
from ai.inference.local.text_classifier import LocalTextClassifier

AI_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ARTIFACT = AI_ROOT / "artifacts" / "fixtures" / "b0_tiny"
POTHOLE_TEXT = "there is a big pothole in the road near the school"


@pytest.fixture(scope="session")
def taxonomy():
    return load_taxonomy()


@pytest.fixture(scope="session")
def policy():
    return AIPolicy.load()


@pytest.fixture(scope="session")
def tiny_artifact_dir() -> Path:
    assert FIXTURE_ARTIFACT.is_dir(), "run: python -m ai.training.src.make_fixture_artifact"
    return FIXTURE_ARTIFACT


@pytest.fixture(scope="session")
def tiny_classifier(tiny_artifact_dir):
    return LocalTextClassifier.load(tiny_artifact_dir)


NOW = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)

INTAKE_OK = {
    "title": "Large pothole near school entrance",
    "description": "A large pothole on the road near the school entrance.",
    "category": "roads", "subcategory": "pothole", "severity": "HIGH", "language": "en",
    "transcript": None, "confidence": 0.94, "reasons": ["Text mentions 'pothole'"], "image_observations": [],
}
