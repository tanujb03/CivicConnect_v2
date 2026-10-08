"""Embedding backfill (backend/scripts/backfill_embeddings.py) and the gateway's batch method ``embed_cases``: SQLite and fakes only, no network.

Checks: only cases WITHOUT an embedding are selected (oldest first) and an existing vector is never replaced, batching and token splitting, the pacing override and one attempt
per request (AI_MAX_RETRIES=0) through the production provider factory, HTTP 429 / spent budget / other failures stop the run with the right exit code, poison rows are bisected
and skipped, wrong dimensions store nothing, a rerun embeds only the rest, empty text never uses up --limit, a run of more than 100 inputs needs --counting (and a daily limit),
per-input counting is paced, the dry run sends and writes nothing, and ``seed_demo --with-embeddings`` only prints the plan.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from ai.inference.errors import ProviderResponseInvalid, ProviderUnavailable
from ai.inference.provider import EmbeddingResult
from ai.inference.providers.fake import FakeProvider
from backend.ai_gateway.providers import build_provider_from_env
from backend.ai_gateway.providers.budget import BudgetSpent, ModelBudgets, parse_limits
from backend.ai_gateway.providers.composite import CompositeProvider
from backend.ai_gateway.providers.openai_compat import ChatCompletionsProvider, _estimate_tokens
from backend.ai_gateway.service import SYSTEM_ACTOR, Actor
from backend.ai_gateway.sql import SqlCaseRepository
from backend.core.exceptions import CivicConnectException
from backend.models import AIAnalysis, CaseEmbedding, CivicCase
from backend.models.types import new_id
from backend.scripts import backfill_embeddings as bf
from backend.scripts import seed_demo
from backend.tests.ai_helpers import install

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
KNOWN = [1.0] + [0.0] * 7                                       # a recognisable pre-existing vector (8 dimensions)
FAKE_LIMITS = {"AI_MODEL_LIMITS": "fake-embedding=100/1000/30000"}   # the fake provider's embedding model id with a daily limit


class Scripted(FakeProvider):
    """Fake embedding provider: ``plan`` holds one step per call (an Exception to raise, a callable ``texts -> EmbeddingResult``, or None for a normal answer)."""

    def __init__(self, plan=(), dim: int = 8, **kw):
        super().__init__(dim=dim, **kw)
        self.plan = list(plan)

    def default(self, texts):
        return EmbeddingResult(vectors=[self._vec(t) for t in texts], model="fake-embedding", latency_ms=1)

    def embed(self, texts):
        self.calls.append(("embed", list(texts)))
        step = self.plan.pop(0) if self.plan else None
        if isinstance(step, Exception):
            raise step
        return step(texts) if callable(step) else self.default(texts)

    @property
    def sent(self) -> list[list[str]]:
        return [c[1] for c in self.calls if c[0] == "embed"]


class Poison(Scripted):
    """HTTP 400 for any batch that contains a text with POISON in it."""

    def embed(self, texts):
        if any("POISON" in t for t in texts):
            self.calls.append(("embed", list(texts)))
            raise ProviderUnavailable("gemini: HTTP 400 (invalid input)", status_code=400)
        return super().embed(texts)


class Tripwire(FakeProvider):
    def embed(self, texts):
        raise AssertionError("a dry run must not call the provider")


class BrokenEmbedder:
    tag = "broken@1"

    def embed(self, texts):
        raise RuntimeError("onnx session died")


class GoodEmbedder:
    tag = "local@1"

    def embed(self, texts):
        return [[1.0] + [0.0] * 7 for _ in texts]


class Clock:
    """A fake clock whose sleep advances it, so pacing waits cost no time."""

    def __init__(self) -> None:
        self.t, self.sleeps = 0.0, []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


def add_cases(e, specs: list[tuple[str | None, float]]) -> list[str]:
    """(text, age in days) -> case ids; the larger the age, the older the case. ``None`` text = a case without any text."""
    ids = []
    with e.session_factory() as db:
        for text, age in specs:
            c = CivicCase(id=new_id(), case_number=f"T-{new_id()[:8]}", title=None, description=text, category="roads", subcategory="pothole", latitude=19.07, longitude=72.88,
                          created_at=NOW - timedelta(days=age), updated_at=NOW, status="NEEDS_REVIEW", priority="NORMAL")
            db.add(c)
            ids.append(c.id)
        db.commit()
    return ids


def many(e, n: int, prefix: str = "report") -> list[str]:
    return add_cases(e, [(f"{prefix} {i}", n + 5 - i) for i in range(n)])


def store(e, case_id: str, vec=KNOWN, model="old@1") -> None:
    with e.session_factory() as db:
        db.add(CaseEmbedding(case_id=case_id, model=model, vector=vec, embedding_dim=len(vec), embedding_model=model))
        db.commit()


def rows(e, model, **where):
    with e.session_factory() as db:
        return db.query(model).filter_by(**where).all()


def run(gw, *, env=None, clock=None, **opts):
    lines: list[str] = []
    kw = {"clock": clock.now, "sleep": clock.sleep} if clock else {}
    code, rep = bf.execute(bf.Options(**opts), gateway_factory=lambda: gw, environ={} if env is None else env, used_today=lambda *_: (0, "test", "gemini"), out=lines.append, **kw)
    return code, rep, "\n".join(lines)


def no_gateway():
    raise AssertionError("the gateway must not be built when there is nothing to do")


# ---- selection: only missing, oldest first, never re-embed ---------------------------------------------------------------------------------------------------------
def test_only_cases_without_an_embedding_are_sent_oldest_first_and_existing_vectors_stay(env):
    ids = add_cases(env, [("newest pothole", 1), ("oldest pothole", 9), ("has a vector", 5), ("middle pothole", 4), ("also has one", 7)])
    store(env, ids[2])
    store(env, ids[4], [0.0, 1.0] + [0.0] * 6)
    p = Scripted()
    gw = install(p)
    code, rep, _ = run(gw, batch_size=10)
    assert code == 0 and p.sent == [["oldest pothole", "middle pothole", "newest pothole"]]
    assert rep["selected"] == 3 and rep["embedded"] == 3 and rep["embed_calls"] == 1 and rep["http_requests"] == 1 and rep["embedded_provider"] == 3 and rep["embedded_local"] == 0
    kept = {r.case_id: r for r in rows(env, CaseEmbedding)}
    assert kept[ids[2]].vector == KNOWN and kept[ids[2]].model == "old@1" and kept[ids[4]].vector[1] == 1.0     # untouched
    assert {i for i in kept} == set(ids)
    [row] = rows(env, CaseEmbedding, case_id=ids[0])
    assert row.embedding_model == "provider:fake-embedding" and row.embedding_dim == 8 and len(row.vector) == 8
    analyses = rows(env, AIAnalysis, task_type="embedding")
    assert sorted(a.case_id for a in analyses) == sorted([ids[0], ids[1], ids[3]]) and all(a.source == "provider" and a.degraded is False for a in analyses)


def test_a_vector_that_appears_during_the_call_is_kept_not_replaced(env):
    ids = add_cases(env, [("a", 3), ("b", 2), ("c", 1)])

    def race(texts):                                              # another process embeds case b while the provider call is in flight
        store(env, ids[1], [0.0, 0.0, 1.0] + [0.0] * 5, "other@1")
        return p.default(texts)

    p = Scripted(plan=[race])
    code, rep, text = run(install(p), batch_size=10)
    assert code == 0 and rep["embedded"] == 2 and rep["skipped_existing"] == 1
    [kept] = rows(env, CaseEmbedding, case_id=ids[1])
    assert kept.model == "other@1" and kept.vector[2] == 1.0
    assert "already embedded/kept: 1" in text


def test_a_primary_key_collision_at_commit_counts_as_already_embedded_not_as_a_failure(env, monkeypatch):
    ids = add_cases(env, [("a", 3), ("b", 2), ("c", 1)])
    real = SqlCaseRepository.save_embedding

    def flaky(self, case_id, vector, model, *, if_missing=False):
        if case_id == ids[1]:
            raise IntegrityError("INSERT INTO case_embeddings", {}, Exception("duplicate key"))        # PostgreSQL reports the lost race at commit
        return real(self, case_id, vector, model, if_missing=if_missing)

    monkeypatch.setattr(SqlCaseRepository, "save_embedding", flaky)
    out = install(Scripted()).embed_cases(ids, SYSTEM_ACTOR, only_missing=True)
    assert out["embedded"] == 2 and out["skipped_existing"] == [ids[1]] and out["failed"] == []
    assert {r.case_id for r in rows(env, CaseEmbedding)} == {ids[0], ids[2]}


def test_batches_follow_the_batch_size_and_each_is_one_provider_call(env):
    many(env, 7)
    p = Scripted()
    code, rep, _ = run(install(p), batch_size=3)
    assert code == 0 and [len(s) for s in p.sent] == [3, 3, 1] and rep["batches_done"] == rep["batches_planned"] == 3 and rep["embed_calls"] == 3
    assert rep["embedded"] == 7 and len(rows(env, CaseEmbedding)) == 7


def test_the_plan_splits_a_batch_that_would_exceed_the_token_ceiling(env):
    ids = add_cases(env, [("x" * 400, 6), ("y" * 400, 5), ("z" * 400, 4), ("w" * 4000, 3), ("short", 2)])
    one = _estimate_tokens({"input": ["x" * 400]})
    plan = bf.build_plan(SqlCaseRepository(), ids, batch_size=100, token_cap=2 * one + 1)
    assert [len(b) for b in plan.batches] == [2, 2] and plan.too_long == [ids[3]]
    assert plan.batches == [ids[:2], [ids[2], ids[4]]] and plan.batch_tokens[0] == 2 * one and plan.rows == 4
    assert all(t <= 2 * one + 1 for t in plan.batch_tokens)
    assert bf.build_plan(SqlCaseRepository(), ids, batch_size=1).batches == [[i] for i in ids]            # at the default ceiling nothing is too long


def test_the_configured_tokens_per_minute_splits_batches_instead_of_failing(env):
    ids = add_cases(env, [("x" * 400, 6), ("y" * 400, 5), ("z" * 400, 4)])
    one = _estimate_tokens({"input": ["x" * 400]})
    p = Scripted()
    spec = f"fake-embedding=80/1000/{one + 5}"                     # a tpm that fits ONE of these texts
    code, rep, _ = run(install(p), env={"AI_EMBEDDING_MODEL": "fake-embedding", "AI_MODEL_LIMITS": spec}, batch_size=10)
    assert code == 0 and [len(s) for s in p.sent] == [1, 1, 1] and rep["embedded"] == 3 and len(ids) == 3
    plan = bf.build_plan(SqlCaseRepository(), ids, 10, token_cap=one - 1)
    assert plan.too_long == ids and plan.batches == []             # a text above the ceiling on its own is set aside and reported, not sent


def test_texts_are_cut_at_8000_characters_and_reported(env):
    ids = add_cases(env, [("a" * 9000, 3), ("short one", 2)])
    p = Scripted()
    code, rep, text = run(install(p), batch_size=10)
    assert code == 0 and [len(t) for t in p.sent[0]] == [8000, 9] and rep["truncated"] == [ids[0]] and rep["embedded"] == 2
    assert "texts cut at 8000 characters: 1" in text and ids[0] in text


def test_cases_without_text_are_never_sent_and_do_not_stop_the_run(env):
    ids = add_cases(env, [(None, 5), ("a real report", 4), ("   ", 3)])
    p = Scripted()
    code, rep, text = run(install(p), batch_size=10)
    assert code == 0 and p.sent == [["a real report"]] and rep["embedded"] == 1 and rep["skipped_empty"] == 2 and rep["selected"] == 1
    assert {r.case_id for r in rows(env, CaseEmbedding)} == {ids[1]} and "rows skipped (empty text): 2" in text
    code, rep, _ = run(install(Scripted()), batch_size=10)                              # a rerun: the empty ones are skipped again, nothing is sent
    assert code == 0 and rep["embed_calls"] == 0 and rep["skipped_empty"] == 2


def test_limit_takes_the_oldest_missing_cases_only(env):
    ids = add_cases(env, [("c1", 5), ("c2", 4), ("c3", 3), ("c4", 2)])
    p = Scripted()
    code, rep, _ = run(install(p), limit=2, batch_size=10)
    assert code == 0 and p.sent == [["c1", "c2"]] and rep["embedded"] == 2
    assert {r.case_id for r in rows(env, CaseEmbedding)} == set(ids[:2])


def test_empty_and_over_long_cases_do_not_use_up_the_limit(env):
    one = _estimate_tokens({"input": ["x" * 400]})
    add_cases(env, [(None, 9), ("  ", 8), ("a", 7), ("x" * 400, 6), ("b", 5), ("c", 4)])
    p = Scripted()
    code, rep, _ = run(install(p), env={"AI_EMBEDDING_MODEL": "fake-embedding", "AI_MODEL_LIMITS": f"fake-embedding=80/1000/{one - 1}"}, limit=2, batch_size=10)      # the 400-character text exceeds the tpm: set aside
    assert code == 0 and p.sent == [["a", "b"]] and rep["embedded"] == 2 and rep["skipped_empty"] == 2 and rep["too_long"] == 1


# ---- stops: 429, spent budget, other failures, bisecting -----------------------------------------------------------------------------------------------------------
def test_http_429_stops_cleanly_with_exit_2_and_the_rerun_embeds_only_the_rest(env):
    ids = add_cases(env, [(f"report {i}", 10 - i) for i in range(5)])
    p = Scripted(plan=[None, ProviderUnavailable("gemini: HTTP 429", status_code=429)])
    code, rep, text = run(install(p), batch_size=2)
    assert code == 2 and rep["embedded"] == 2 and rep["batches_done"] == 1 and rep["embed_calls"] == 2 and len(p.sent) == 2           # never loops: no third call
    assert "STOP: quota" in text and {r.case_id for r in rows(env, CaseEmbedding)} == set(ids[:2]) and rep["bisect_calls"] == 0
    p2 = Scripted()
    code, rep, _ = run(install(p2), batch_size=2)
    assert code == 0 and p2.sent == [["report 2", "report 3"], ["report 4"]] and rep["embedded"] == 3                                      # only what was missing
    assert len(rows(env, CaseEmbedding)) == 5
    lines: list[str] = []
    code, rep = bf.execute(bf.Options(), gateway_factory=no_gateway, environ={}, out=lines.append)                                     # nothing missing: no gateway, no request
    assert code == 0 and rep["embed_calls"] == 0 and "0 requests made" in "\n".join(lines)


def test_a_spent_budget_stops_with_exit_2(env):
    add_cases(env, [("a", 3), ("b", 2)])
    p = Scripted(plan=[BudgetSpent("gemini: daily budget of emb is spent (1000/1000 requests today); request not sent", status_code=429)])
    code, rep, text = run(install(p), batch_size=1)
    assert code == 2 and rep["embedded"] == 0 and len(p.sent) == 1 and "BudgetSpent" in text and rows(env, CaseEmbedding) == []


@pytest.mark.parametrize("error", [ProviderUnavailable("gemini: HTTP 503", status_code=503), ProviderUnavailable("gemini: transport error ConnectError"), RuntimeError("boom")])
def test_an_outage_or_other_failure_stops_at_the_first_failing_batch_with_exit_3_and_neither_retries_nor_bisects(env, error):
    add_cases(env, [(f"r{i}", 9 - i) for i in range(4)])
    p = Scripted(plan=[None, error])
    code, rep, text = run(install(p), batch_size=2)
    assert code == 3 and rep["embedded"] == 2 and len(p.sent) == 2 and "STOP:" in text and len(rows(env, CaseEmbedding)) == 2 and rep["bisect_calls"] == 0


def test_a_rejected_row_is_isolated_by_bisecting_skipped_and_listed_and_the_rest_is_embedded(env):
    ids = add_cases(env, [("fine one", 9), ("fine two", 8), ("POISON row", 7), ("fine three", 6), ("fine four", 5)])
    p = Poison()
    code, rep, text = run(install(p), batch_size=5)
    assert code == 0 and rep["embedded"] == 4 and list(rep["bad_rows"]) == [ids[2]] and rep["bisect_calls"] == 4 and len(p.sent) == 5
    assert {r.case_id for r in rows(env, CaseEmbedding)} == set(ids) - {ids[2]} and "SKIPPED for this run: 1" in text and ids[2] in text and "HTTP 400" in text
    code, rep, _ = run(install(Poison()), batch_size=5)                                  # a rerun tries the rejected row again (the skip list is per run) and skips it again
    assert code == 3 and rep["embedded"] == 0 and list(rep["bad_rows"]) == [ids[2]]           # every row of this run failed


def test_bisecting_stops_after_20_extra_requests_with_exit_3(env):
    add_cases(env, [(f"POISON {i}", 40 - i) for i in range(30)])
    p = Poison()
    code, rep, text = run(install(p), batch_size=30)
    assert code == 3 and len(p.sent) == 1 + 20 and rep["bisect_calls"] == 20 and "extra requests" in text and rep["embedded"] == 0 and rows(env, CaseEmbedding) == []


def test_a_quota_error_during_bisecting_stops_at_once_with_exit_2(env):
    add_cases(env, [(f"r{i}", 9 - i) for i in range(4)])
    p = Scripted(plan=[ProviderUnavailable("gemini: HTTP 400", status_code=400), ProviderUnavailable("gemini: HTTP 429", status_code=429)])
    code, rep, _ = run(install(p), batch_size=4)
    assert code == 2 and len(p.sent) == 2 and rep["embedded"] == 0


def test_a_batch_that_would_overrun_max_requests_stops_before_it(env):
    many(env, 4)
    p = Scripted()
    code, rep, text = run(install(p), batch_size=1, max_requests=2)
    assert code == 2 and len(p.sent) == 2 and rep["http_requests"] == 2 and rep["embedded"] == 2 and "--max-requests 2" in text


def test_no_embedding_provider_means_exit_3_and_nothing_is_sent(env):
    add_cases(env, [("a", 2)])
    code, rep, text = run(install(None), batch_size=5)
    assert code == 3 and rep["embed_calls"] == 0 and "no embedding provider" in text and rows(env, CaseEmbedding) == []
    code, _ = bf.execute(bf.Options(), gateway_factory=lambda: (_ for _ in ()).throw(RuntimeError("x")), environ={}, out=lambda s: None)
    assert code == 3


# ---- dimensions ----------------------------------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("vectors, expected", [(lambda texts: [[1.0, 0.0, 0.0]] * len(texts), 8),                       # not the dimension that was asked for
                                               (lambda texts: [[1.0, 0.0]] + [[1.0, 0.0, 0.0]] * (len(texts) - 1), None),    # uneven dimensions
                                               (lambda texts: [[1.0] * 8], None),                                          # one vector for several texts
                                               (lambda texts: [[float("nan")] * 8] * len(texts), None)])
def test_a_batch_with_invalid_vectors_raises_before_anything_is_stored(env, vectors, expected):
    ids = add_cases(env, [("a", 3), ("b", 2)])
    p = Scripted(plan=[lambda texts: EmbeddingResult(vectors=vectors(texts), model="fake-embedding")])
    with pytest.raises(ProviderResponseInvalid):
        install(p).embed_cases(ids, SYSTEM_ACTOR, only_missing=True, expected_dim=expected)
    assert rows(env, CaseEmbedding) == [] and rows(env, AIAnalysis, task_type="embedding") == []


def test_the_dimension_of_the_stored_embeddings_is_the_expectation_when_none_is_given(env):
    ids = add_cases(env, [("a", 3), ("b", 2)])
    store(env, ids[0])                                              # 8 dimensions stored already
    p = Scripted(plan=[lambda texts: EmbeddingResult(vectors=[[1.0, 0.0, 0.0, 0.0]] * len(texts), model="fake-embedding")])
    with pytest.raises(ProviderResponseInvalid, match="dimension 4 differs from the expected 8"):
        install(p).embed_cases([ids[1]], SYSTEM_ACTOR, only_missing=True)
    assert [r.case_id for r in rows(env, CaseEmbedding)] == [ids[0]]
    assert install(Scripted()).embed_cases([ids[1]], SYSTEM_ACTOR, only_missing=True)["embedded"] == 1        # the same dimension is accepted


def test_the_first_valid_batch_of_a_run_fixes_the_dimension_when_nothing_is_stored_yet(env, monkeypatch):
    monkeypatch.setattr(SqlCaseRepository, "stored_embedding_dim", staticmethod(lambda: None))
    ids = add_cases(env, [("first", 3), ("second", 2)])
    p = Scripted(plan=[None, lambda texts: EmbeddingResult(vectors=[[1.0, 0.0, 0.0, 0.0]] * len(texts), model="fake-embedding")])
    code, rep, _ = run(install(p), batch_size=1)
    assert code == 0 and rep["embedded"] == 1 and list(rep["bad_rows"]) == [ids[1]] and [r.case_id for r in rows(env, CaseEmbedding)] == [ids[0]]


def test_a_provider_that_always_answers_the_wrong_dimension_fails_the_whole_run_with_exit_3(env):
    add_cases(env, [("a", 3), ("b", 2)])

    class Wrong(Scripted):
        def embed(self, texts):
            self.calls.append(("embed", list(texts)))
            return EmbeddingResult(vectors=[[1.0, 0.0, 0.0]] * len(texts), model="fake-embedding")

    code, rep, text = run(install(Wrong()), env={"AI_EMBEDDING_DIM": "8"}, batch_size=2)
    assert code == 3 and rep["embedded"] == 0 and len(rep["bad_rows"]) == 2 and rows(env, CaseEmbedding) == [] and "every row failed" in text


# ---- pacing and one attempt per request ----------------------------------------------------------------------------------------------------------------------------
def test_pacing_caps_requests_and_tokens_keeps_the_daily_limit_and_sets_the_wait():
    env = {"AI_EMBEDDING_MODEL": "gemini-embedding-001"}
    lim = bf.apply_pacing(env, "gemini-embedding-001")
    assert (lim.rpm, lim.rpd, lim.tpm) == (80, 1000, 25_000)                                  # the table says 100 / 1000 / 30,000
    assert env["AI_BUDGET_MAX_WAIT_S"] == "65"
    budgets = ModelBudgets.from_env(env, provider="gemini")
    got = budgets.limits["gemini-embedding-001"]
    assert (got.rpm, got.rpd, got.tpm) == (80, 1000, 25_000) and budgets.max_wait_s == 65.0


def test_pacing_keeps_lower_configured_limits_and_survives_off():
    env = {"AI_MODEL_LIMITS": "emb-x=10/50/1000,other=1/2/3"}
    lim = bf.apply_pacing(env, "emb-x")
    assert (lim.rpm, lim.rpd, lim.tpm) == (10, 50, 1000) and "other=1/2/3" in env["AI_MODEL_LIMITS"]
    off = {"AI_MODEL_LIMITS": "off"}
    lim = bf.apply_pacing(off, "gemini-embedding-001")
    assert (lim.rpm, lim.rpd, lim.tpm) == (80, 1000, 25_000) and "off" not in off["AI_MODEL_LIMITS"]
    unknown = bf.apply_pacing({}, "no-such-model")                                            # not in the table: our ceiling, no daily limit
    assert (unknown.rpm, unknown.rpd, unknown.tpm) == (80, None, 25_000)


def test_pacing_and_a_single_attempt_are_in_place_before_the_gateway_is_built(env):
    add_cases(env, [("a", 2)])
    seen = {}
    gw = install(Scripted())

    def factory():
        seen.update(limits=e["AI_MODEL_LIMITS"], wait=e["AI_BUDGET_MAX_WAIT_S"], retries=e["AI_MAX_RETRIES"])
        return gw

    e = {"AI_EMBEDDING_MODEL": "gemini-embedding-001", "AI_MAX_RETRIES": "2"}
    code, _ = bf.execute(bf.Options(), gateway_factory=factory, environ=e, used_today=lambda *_: (0, "t", "gemini"), out=lambda s: None)
    assert code == 0 and seen == {"limits": "gemini-embedding-001=80/1000/25000", "wait": "65", "retries": "0"}


def test_the_input_pacer_keeps_a_minute_window():
    c = Clock()
    pacer = bf.InputPacer(80, c.now, c.sleep)
    pacer.wait(80)
    assert c.sleeps == []
    pacer.wait(10)                                                  # 80 + 10 > 80 in the same minute: wait for the window to pass
    assert len(c.sleeps) == 1 and 60.0 <= c.sleeps[0] <= 60.1 and pacer.per_minute == 80
    pacer.wait(70)
    assert len(c.sleeps) == 1                                       # 10 + 70 <= 80


# ---- production path: the env override builds the adapter ---------------------------------------------------------------------------------------------------------
def prod_env(**extra):
    return {"GEMINI_API_KEY": "test-key", "AI_EMBEDDING_MODEL": "emb-m", "AI_EMBEDDING_DIM": "4", "AI_MODEL_LIMITS": "emb-m=100/1000/30000", **extra}


def production_gateway(env, handler, monkeypatch):
    """A gateway whose provider is built by the production factory from ``env`` AFTER the script's overrides; only the HTTP transport is a fake (no network, no Redis)."""
    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(ModelBudgets, "_redis", lambda self: None)
    return lambda: install(build_provider_from_env(env))


def vectors_for(request: httpx.Request, dim: int = 4):
    n = len(json.loads(request.content)["input"])
    return httpx.Response(200, json={"model": "emb-m", "data": [{"index": i, "embedding": [1.0] + [0.0] * (dim - 1)} for i in range(n)]})


def test_a_429_makes_exactly_one_http_request_through_the_production_factory(env, monkeypatch):
    add_cases(env, [("a", 3), ("b", 2)])
    hits = []

    def handler(request):
        hits.append(1)
        return httpx.Response(429, json={"error": {"message": "quota exceeded", "status": "RESOURCE_EXHAUSTED"}})

    e = prod_env(AI_MAX_RETRIES="2")                                # the owner's setting must NOT win: each batch is one attempt
    lines: list[str] = []
    code, rep = bf.execute(bf.Options(batch_size=1), gateway_factory=production_gateway(e, handler, monkeypatch), environ=e, out=lines.append)
    text = "\n".join(lines)
    assert e["AI_MAX_RETRIES"] == "0" and code == 2 and len(hits) == 1 and rep["http_requests"] == 1 and rep["embed_calls"] == 1 and rep["embedded"] == 0
    assert rep["counter_delta"] == 1 and "HTTP 429" in text and rows(env, CaseEmbedding) == []


def test_a_server_error_is_not_retried_either(env, monkeypatch):
    add_cases(env, [("a", 3)])
    hits = []
    e = prod_env()
    code, rep = bf.execute(bf.Options(), gateway_factory=production_gateway(e, lambda r: hits.append(1) or httpx.Response(500, json={"error": {"message": "boom"}}), monkeypatch),
                           environ=e, out=lambda s: None)
    assert code == 3 and len(hits) == 1 and rep["http_requests"] == 1 and rep["counter_delta"] == 1


def test_the_production_path_embeds_and_reports_the_counter_delta(env, monkeypatch):
    add_cases(env, [(f"r{i}", 9 - i) for i in range(5)])
    e = prod_env()
    lines: list[str] = []
    code, rep = bf.execute(bf.Options(batch_size=5), gateway_factory=production_gateway(e, vectors_for, monkeypatch), environ=e, out=lines.append)
    assert code == 0 and rep["embedded"] == 5 and rep["http_requests"] == 1 and (rep["counter_before"], rep["counter_after"], rep["counter_delta"]) == (0, 1, 1)
    assert "daily counter delta" in "\n".join(lines) and rep["model"] == "emb-m"


def test_a_real_adapter_dimension_mismatch_stops_with_exit_3(env, monkeypatch):
    add_cases(env, [("a", 3)])
    e = prod_env()
    code, rep = bf.execute(bf.Options(), gateway_factory=production_gateway(e, lambda r: vectors_for(r, dim=3), monkeypatch), environ=e, out=lambda s: None)
    assert code == 3 and "ProviderResponseInvalid" in "".join(rep["bad_rows"].values()) and rows(env, CaseEmbedding) == []


def real_provider(handler, *, limits="emb-m=80/1000/25000", dim=4):
    budgets = ModelBudgets(parse_limits(limits, {}), provider="gemini", redis_getter=lambda: None, sleep=lambda s: None, max_wait_s=65)
    prov = ChatCompletionsProvider("gemini", "http://provider.test", "test-key", {"embedding": "emb-m"}, client=httpx.Client(transport=httpx.MockTransport(handler)),
                                   sleep=lambda s: None, embedding_dim=dim, budgets=budgets, max_retries=0)
    return CompositeProvider({"embedding": prov}), budgets


def test_a_batch_over_64_inputs_counts_every_http_request(env):
    many(env, 70)
    prov, budgets = real_provider(vectors_for)
    code, rep, _ = run(install(prov), env={"AI_EMBEDDING_DIM": "4", "AI_MODEL_LIMITS": "emb-m=80/1000/25000"}, batch_size=100)
    assert code == 0 and rep["embedded"] == 70 and rep["embed_calls"] == 1 and rep["http_requests"] == 2 and rep["counter_delta"] == 2


def test_a_spent_daily_budget_sends_no_request_and_exits_2(env):
    add_cases(env, [("a", 3)])
    hits = []
    prov, budgets = real_provider(lambda r: hits.append(1) or vectors_for(r), limits="emb-m=80/1/25000")
    budgets.acquire("emb-m")                                                                  # the single request of the day is gone
    code, rep, text = run(install(prov), env={"AI_EMBEDDING_DIM": "4", "AI_MODEL_LIMITS": "emb-m=80/1/25000"})
    assert code == 2 and hits == [] and "BudgetSpent" in text and rows(env, CaseEmbedding) == []


# ---- the local embedder and the provider ---------------------------------------------------------------------------------------------------------------------------
def test_a_failing_local_embedder_falls_back_to_a_counted_and_paced_provider_and_the_report_says_so(env):
    add_cases(env, [("a", 3), ("b", 2), ("c", 1)])
    p = Scripted()
    seen = {}
    gw = install(p, embedder=BrokenEmbedder())

    def factory():
        seen.update(limits=e.get("AI_MODEL_LIMITS"), retries=e.get("AI_MAX_RETRIES"))
        return gw

    e = {"AI_EMBEDDING_MODEL": "fake-embedding", **FAKE_LIMITS}
    lines: list[str] = []
    code, rep = bf.execute(bf.Options(batch_size=10), gateway_factory=factory, environ=e, used_today=lambda *_: (0, "t", "g"), out=lines.append)
    text = "\n".join(lines)
    assert code == 0 and rep["embedded"] == 3 and rep["embedded_provider"] == 3 and rep["embedded_local"] == 0 and rep["local_fallbacks"] == 1
    assert rep["embed_calls"] == 1 and rep["http_requests"] == 1                                    # counted although the local embedder was configured
    assert seen == {"limits": "fake-embedding=100/1000/30000,fake-embedding=80/1000/25000", "retries": "0"} and gw.ai.provider is p     # paced, one attempt, provider restored
    assert "via provider: 3" in text and "local embedder failed in 1" in text and "local embedder first, provider" in text
    assert {r.embedding_model for r in rows(env, CaseEmbedding)} == {"provider:fake-embedding"}


def test_a_working_local_embedder_makes_no_provider_request_and_is_reported_as_local(env):
    add_cases(env, [("a", 3), ("b", 2)])
    p = Scripted()
    code, rep, text = run(install(p, embedder=GoodEmbedder()), batch_size=10)
    assert code == 0 and rep["embedded"] == 2 and rep["embedded_local"] == 2 and rep["embedded_provider"] == 0 and rep["embed_calls"] == 0 and p.sent == []
    assert "via local embedder: 2" in text and {r.embedding_model for r in rows(env, CaseEmbedding)} == {"local@1"}


# ---- more than 100 inputs: --counting, a daily limit, per-input pacing --------------------------------------------------------------------------------------------------
def test_a_run_of_more_than_100_inputs_is_refused_without_counting_and_explains_the_probe(env):
    many(env, 101)
    p = Scripted()
    code, rep, text = run(install(p), env=dict(FAKE_LIMITS))
    assert code == 64 and p.sent == [] and rows(env, CaseEmbedding) == [] and "--counting" in text and "--limit 10 --batch-size 10" in text and "REFUSED" in text


def test_a_probe_of_up_to_100_inputs_needs_no_flag_and_says_when_there_is_no_daily_counter(env):
    many(env, 100)
    p = Scripted()
    code, rep, text = run(install(p), batch_size=100)
    assert code == 0 and rep["embedded"] == 100 and len(p.sent) == 1
    assert rep["counter_delta"] is None and "daily counter delta (compare with Google AI Studio's usage page): not available (no rpd configured)" in text


def test_more_than_100_inputs_are_refused_when_the_model_has_no_daily_limit(env):
    many(env, 101)
    p = Scripted()
    code, rep, text = run(install(p), counting="per-batch")                                    # fake-embedding is not in the budget table
    assert code == 64 and p.sent == [] and "no daily limit" in text


@pytest.mark.parametrize("mode", ["per-batch", "per-input"])
def test_a_counted_run_of_more_than_100_inputs_goes_ahead(env, mode):
    many(env, 101)
    p = Scripted()
    clock = Clock()
    code, rep, _ = run(install(p), env=dict(FAKE_LIMITS), counting=mode, batch_size=100, clock=clock)
    assert code == 0 and rep["embedded"] == 101 and rep["counting"] == mode
    if mode == "per-batch":
        assert [len(s) for s in p.sent] == [100, 1] and clock.sleeps == []
    else:
        assert [len(s) for s in p.sent] == [80, 21] and len(clock.sleeps) == 1 and clock.sleeps[0] >= 60          # never more than 80 inputs in a minute


def test_per_input_counting_stops_when_the_inputs_would_exceed_max_requests(env):
    many(env, 160)
    p = Scripted()
    code, rep, text = run(install(p), env=dict(FAKE_LIMITS), counting="per-input", batch_size=100, max_requests=100, clock=Clock())
    assert code == 2 and [len(s) for s in p.sent] == [80] and rep["embedded"] == 80 and "per-input counting" in text


def test_per_input_counting_respects_the_daily_room_left(env):
    many(env, 101)
    prov, budgets = real_provider(vectors_for)
    budgets._days[budgets._day_key("emb-m")] = 930                                              # 70 requests left today
    code, rep, text = run(install(prov), env={"AI_EMBEDDING_DIM": "4", "AI_MODEL_LIMITS": "emb-m=80/1000/25000"}, counting="per-input", batch_size=100, clock=Clock())
    assert code == 2 and rep["embed_calls"] == 0 and rep["counter_before"] == 930 and "would exceed 70" in text and rows(env, CaseEmbedding) == []


def test_the_daily_ceiling_is_a_hard_stop_that_counts_what_ai_studio_already_showed(env):
    many(env, 200)
    p = Scripted()
    code, rep, text = run(install(p), env=dict(FAKE_LIMITS), counting="per-input", batch_size=50, daily_ceiling=130, assume_used_today=28, clock=Clock())
    assert code == 2 and sum(len(s) for s in p.sent) == 100 and rep["embedded"] == 100          # 28 + 100 = 128 <= 130; the next 50 would pass the ceiling
    assert "would exceed" in text and "EXPECT about 128 requests/day in AI Studio" in text and "daily ceiling: 130" in text


def test_a_run_that_is_already_at_the_ceiling_sends_nothing(env):
    many(env, 20)
    p = Scripted()
    code, rep, text = run(install(p), env=dict(FAKE_LIMITS), counting="per-input", batch_size=10, daily_ceiling=700, assume_used_today=700, clock=Clock())
    assert code == 2 and p.sent == [] and rep["embedded"] == 0 and "nothing was sent" in text and rows(env, CaseEmbedding) == []


# ---- dry run -------------------------------------------------------------------------------------------------------------------------------------------------------------
def test_dry_run_sends_and_writes_nothing_and_prints_both_request_assumptions(env):
    ids = add_cases(env, [("pothole near the school", 9), (None, 8), ("garbage not collected", 7), ("broken streetlight", 6)])
    store(env, ids[3])
    install(Tripwire())
    lines: list[str] = []
    code, rep = bf.execute(bf.Options(dry_run=True, batch_size=2), gateway_factory=no_gateway,
                           environ={"AI_EMBEDDING_MODEL": "gemini-embedding-001"}, used_today=lambda *_: (37, "Redis", "gemini"), out=lines.append)
    text = "\n".join(lines)
    assert code == 0 and rep["stop_reason"] == "dry run"
    assert "cases without an embedding row: 3" in text and "with empty text (skipped, never sent): 1" in text and "to embed: 2 rows in 1 batches (batch size 2)" in text
    assert "assumption A" in text and "assumption B" in text and "UNVERIFIED" in text and "--counting per-batch or --counting per-input" in text
    assert "requests needed, assumption A" in text and ": 1\n" in text.split("assumption A", 1)[1] and "assumption B (every input counts as 1 request): 2" in text
    assert "daily limit: 1000 requests/day; 37 used today" in text and "room today: 963" in text
    assert "minimum time at 80 requests/min and 25000 tokens/min" in text and "per batch min" in text
    assert len(rows(env, CaseEmbedding)) == 1 and rows(env, AIAnalysis) == []                  # nothing written


def test_dry_run_needs_no_model_and_no_key(env):
    add_cases(env, [("a report", 2)])
    lines: list[str] = []
    code, _ = bf.execute(bf.Options(dry_run=True), gateway_factory=no_gateway, environ={}, out=lines.append)
    text = "\n".join(lines)
    assert code == 0 and "model: <not configured>" in text and "daily limit: unknown" in text and "assumption B" in text


def test_main_dry_run_and_argument_errors(env, monkeypatch, capsys):
    monkeypatch.delenv("AI_EMBEDDING_MODEL", raising=False)
    add_cases(env, [("a report", 2)])
    assert bf.main(["--dry-run"]) == 0 and "DRY RUN" in capsys.readouterr().out
    for bad in (["--batch-size", "101"], ["--batch-size", "0"], ["--limit", "0"], ["--counting", "per-second"], ["--bogus"]):
        with pytest.raises(SystemExit) as exc:
            bf.main(bad)
        assert exc.value.code == 64                                                           # argparse's 2 is reserved for "stopped for quota"


# ---- the gateway method ----------------------------------------------------------------------------------------------------------------------------------------------
def test_embed_cases_needs_the_embed_capability(env):
    ids = add_cases(env, [("a", 2)])
    gw = install(Scripted())
    for role in ("citizen", "field_worker", "overlooker"):
        with pytest.raises(CivicConnectException) as exc:
            gw.embed_cases(ids, Actor("u", role))
        assert exc.value.status_code == 403
    assert gw.embed_cases(ids, Actor("u", "operator"))["embedded"] == 1
    assert gw.embed_cases(ids, SYSTEM_ACTOR)["embedded"] == 1                                 # not only_missing: replaces, like embed_case


def test_embed_cases_reports_unknown_empty_and_existing_ids_without_sending_them(env):
    ids = add_cases(env, [("has one", 3), (None, 2), ("fresh", 1)])
    store(env, ids[0])
    p = Scripted()
    out = install(p).embed_cases([*ids, "no-such-case"], SYSTEM_ACTOR, only_missing=True)
    assert p.sent == [["fresh"]] and out["embedded"] == 1 and out["skipped_existing"] == [ids[0]] and out["skipped_empty"] == [ids[1]] and out["not_found"] == ["no-such-case"]
    none = install(Scripted()).embed_cases([ids[0]], SYSTEM_ACTOR, only_missing=True)
    assert none["provider_called"] is False and none["embedded"] == 0


def test_the_single_case_path_is_unchanged(env):
    ids = add_cases(env, [("single case text", 2)])
    p = Scripted()
    out = install(p).embed_case(ids[0], SYSTEM_ACTOR)
    assert out["stored"] and out["source"] == "provider" and p.sent == [["single case text"]]


# ---- seed_demo --with-embeddings ---------------------------------------------------------------------------------------------------------------------------------------
def stub_seed(monkeypatch):
    stub = SimpleNamespace(reset_all=lambda db: None, seed_reference=lambda db: {"departments": 0}, seed_demo_city=lambda db: {"cases": 3, "password": "x", "accounts": []})
    monkeypatch.setattr(seed_demo, "seed", stub)


def test_seed_demo_does_not_touch_embeddings_by_default(env, monkeypatch):
    stub_seed(monkeypatch)
    calls = []
    monkeypatch.setattr(seed_demo, "embed_missing", lambda: calls.append(1) or 0)
    assert seed_demo.main([]) == 0 and calls == []


def test_seed_demo_with_embeddings_only_prints_the_plan_and_the_commands(env, monkeypatch, capsys):
    stub_seed(monkeypatch)
    monkeypatch.delenv("AI_EMBEDDING_MODEL", raising=False)
    monkeypatch.setattr(bf, "_default_gateway", no_gateway)                                    # building a gateway (a provider) would be a bug here
    add_cases(env, [("a report", 2), ("another", 1)])
    assert seed_demo.main(["--with-embeddings"]) == 0
    text = capsys.readouterr().out
    assert "DRY RUN" in text and "cases without an embedding row: 2" in text and "Nothing was embedded" in text
    assert "backfill_embeddings --limit 10 --batch-size 10" in text and "--counting per-batch" in text
    assert rows(env, CaseEmbedding) == [] and rows(env, AIAnalysis) == []
    with pytest.raises(SystemExit):
        seed_demo.main(["--with-embeddings", "--reference-only"])
