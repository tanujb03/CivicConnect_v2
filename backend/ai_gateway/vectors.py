"""Vector helpers for AI-2 candidate search: pgvector availability, the text literal pgvector parses, and the portable cosine used on SQLite / without the extension.

Migration 0003 gives ``case_embeddings`` an untyped ``embedding_vec vector`` column plus a PARTIAL HNSW cosine index per dimension in ``INDEXED_DIMS``:
``USING hnsw ((embedding_vec::vector(D)) vector_cosine_ops) WHERE (embedding_dim = D)``. A query only uses such an index when it repeats the cast and the predicate, so
``vector_order_sql`` builds exactly that expression (D is always an int taken from the stored row, never user text).
"""
from __future__ import annotations

import json
import math
from typing import Sequence

from sqlalchemy import text

INDEXED_DIMS = (384, 768)                      # multilingual-e5-small / -base (see alembic 0003)
MAX_VECTOR_DIM = 16000                         # pgvector's limit for the ``vector`` type


def vector_search_available(db) -> bool:
    """PostgreSQL with the pgvector extension AND the ``embedding_vec`` column of migration 0003 (SQLite, or a server without the extension: False)."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    try:
        return bool(db.execute(text(
            "SELECT 1 FROM pg_extension e, information_schema.columns c WHERE e.extname = 'vector' AND c.table_schema = current_schema() "
            "AND c.table_name = 'case_embeddings' AND c.column_name = 'embedding_vec'")).scalar())
    except Exception:                          # noqa: BLE001  (a probe must never break a request)
        db.rollback()
        return False


def to_literal(vec: Sequence[float]) -> str:
    """``[0.1,0.2,...]``: the text form pgvector casts with ``CAST(:v AS vector)``."""
    return json.dumps([float(x) for x in vec], separators=(",", ":"))


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity in [-1, 1]; 0.0 for empty / zero / mismatched vectors."""
    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def vector_order_sql(dim: int, column: str = "e.embedding_vec", param: str = ":q") -> str:
    """``ORDER BY`` expression with the SAME cast as the partial index of that dimension, so the index is usable."""
    d = int(dim)
    if not 0 < d <= MAX_VECTOR_DIM:
        raise ValueError(f"unsupported embedding dimension {dim}")
    return f"{column}::vector({d}) <=> CAST({param} AS vector({d}))"
