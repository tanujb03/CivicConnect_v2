"""Free / alternative AI providers behind the frozen ``AIProvider`` protocol (``ai.inference.provider``). Nothing in ``ai/inference`` is modified:
``AIService(provider=...)`` accepts any object implementing the protocol, so these live in the backend gateway layer."""
from .composite import CompositeProvider
from .factory import build_provider_from_env
from .openai_compat import ChatCompletionsProvider

__all__ = ["ChatCompletionsProvider", "CompositeProvider", "build_provider_from_env"]
