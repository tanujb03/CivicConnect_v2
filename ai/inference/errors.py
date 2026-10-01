"""Exception hierarchy for the inference layer.

Services convert provider failures into graceful, *visible* fallbacks (warnings +
metadata). These exceptions are raised by lower layers and caught by services.
"""
from __future__ import annotations


class AIError(Exception):
    """Base class for all inference-layer errors."""


class ProviderNotConfigured(AIError):
    """No provider / model configured (missing API key, model ID, etc.)."""


class ProviderUnavailable(AIError):
    """Provider call failed (network, timeout, HTTP 429/5xx, auth)."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ProviderResponseInvalid(AIError):
    """Provider answered but the output was refused, empty or schema-invalid."""


class ArtifactError(AIError):
    """A model artifact is missing, corrupt, or incompatible."""


class TaxonomyError(AIError):
    """Taxonomy file is malformed or internally inconsistent."""


class ToolValidationError(AIError):
    """A copilot tool call failed validation (unknown tool, bad arguments)."""


class InputLimitExceeded(AIError, ValueError):
    """Input exceeds a configured limit (size/count). Backend should map to HTTP 413/422."""


class ToolPermissionDenied(AIError):
    """Raised by a backend ToolExecutor when the actor may not run the requested tool/scope."""
