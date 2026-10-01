"""Production AI inference layer for CivicConnect v2.

Entry point for the backend::

    from ai.inference.service import AIService
    ai = AIService.from_env()
    response = ai.analyze_intake(request)

Nothing in this package imports training code, notebooks, scikit-learn, torch
or pandas. Runtime dependencies: pydantic, numpy, httpx.
"""

__version__ = "0.1.0"
