"""CivicConnect v2 AI package root.

Only ``ai.inference`` is production code (importable by the FastAPI backend).
``ai.training`` and ``ai.evaluation`` are experiment/QA tooling and are never
imported by ``ai.inference``.
"""
