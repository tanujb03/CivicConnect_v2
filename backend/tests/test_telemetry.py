"""OpenTelemetry (WP8): off by default with no opentelemetry SDK/exporter/instrumentation import; on, one server span per request, SQL / httpx / Redis client spans,
trace context through the Redis stream envelope into a worker thread. No network: the in-memory span exporter replaces OTLP; Redis is a fake."""
from __future__ import annotations

import contextlib
import subprocess
import sys
import threading
from unittest.mock import MagicMock, patch

import httpcore
import httpx
import pytest
import redis as redis_lib
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.core import telemetry
from backend.db.session import make_engine

OTEL_ENV = ("OTEL_ENABLED", "OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "OTEL_SERVICE_NAME", "OTEL_RESOURCE_ATTRIBUTES")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    """No leaked state between tests: telemetry off, environment variables unset, instrumentation removed afterwards."""
    for name in OTEL_ENV:
        monkeypatch.delenv(name, raising=False)
    telemetry.shutdown_telemetry()
    yield
    telemetry.shutdown_telemetry()


@pytest.fixture
def otel(monkeypatch):
    """Telemetry on with an in-memory exporter, a private SQLite engine and no global provider. Yields (exporter, engine)."""
    pytest.importorskip("opentelemetry.sdk")
    pytest.importorskip("opentelemetry.exporter.otlp.proto.http.trace_exporter")
    pytest.importorskip("opentelemetry.instrumentation.sqlalchemy")
    pytest.importorskip("opentelemetry.instrumentation.redis")
    pytest.importorskip("opentelemetry.instrumentation.httpx")
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    monkeypatch.setenv("OTEL_ENABLED", "true")
    exporter, engine = InMemorySpanExporter(), make_engine("sqlite://")
    telemetry.setup_telemetry(span_exporter=exporter, engine=engine, set_global=False)
    return exporter, engine


def _run(code: str, **env: str) -> subprocess.CompletedProcess:
    import os
    full = {**{k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}, "CIVIC_IGNORE_ENV_FILE": "1", **env}
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=full, timeout=120)


# ══ off by default ═══════════════════════════════════════════════════════════
class TestDisabled:
    def test_kwargs_turn_native_telemetry_fully_off(self):
        kw = telemetry.telemetry_kwargs()
        assert kw["tracing"] is False and kw["operation_spans"] is False and kw["metrics"] is False and kw["logs"] is False
        assert kw["auto_configure"] is False                     # else FastAPI adds its own OTLP exporter once OTEL_EXPORTER_OTLP_ENDPOINT is set

    @pytest.mark.parametrize("value", ["", "false", "0", "no", "off"])
    def test_falsy_values_are_off(self, monkeypatch, value):
        monkeypatch.setenv("OTEL_ENABLED", value)
        assert telemetry.telemetry_enabled() is False and telemetry.setup_telemetry() is None

    def test_helpers_are_noops(self):
        fields = {"a": "b"}
        assert telemetry.inject_trace_context(fields) == {"a": "b"}
        telemetry.set_request_id("rid")
        with telemetry.producer_span("civic:x"), telemetry.consumer_span("civic:x", "1-0", {"traceparent": "00-" + "1" * 32 + "-" + "2" * 16 + "-01"}):
            pass
        assert telemetry.tracer_provider() is None
        telemetry.shutdown_telemetry()                           # safe when never started

    def test_no_opentelemetry_import_of_our_own(self):
        """Importing the telemetry, publisher and workers modules and calling every helper must import no opentelemetry module that ``import redis`` (redis-py 8 and
        FastAPI load parts of the API/SDK themselves) has not already loaded: no tracer SDK, exporter or instrumentation."""
        code = (
            "import sys, redis\n"
            "otel = lambda: {m for m in sys.modules if m.startswith('opentelemetry')}\n"
            "before = otel()\n"
            "import backend.core.telemetry as t, backend.events.publisher as p, backend.events.workers as w\n"
            "t.telemetry_kwargs(); t.set_request_id('x'); t.setup_telemetry(); t.inject_trace_context({}); t.shutdown_telemetry()\n"
            "with t.producer_span('s'), t.consumer_span('s', '1-0', {}): pass\n"
            "print('NEW', sorted(otel() - before))\n"
        )
        out = _run(code)
        assert out.returncode == 0, out.stderr
        assert "NEW []" in out.stdout, out.stdout

    def test_publish_adds_no_trace_fields_when_off(self):
        from backend.events.publisher import publish
        fake = MagicMock()
        fake.xadd.return_value = "1-0"
        with patch("backend.events.publisher.get_redis", return_value=fake):
            publish("civic:test", {"k": "v"})
        assert set(fake.xadd.call_args.args[1]) == {"k", "_ts"}


# ══ packages missing ═════════════════════════════════════════════════════════
class TestPackagesMissing:
    def test_clear_error_only_when_enabled(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "opentelemetry.sdk.resources", None)           # None in sys.modules makes the import raise ImportError
        assert telemetry.setup_telemetry() is None                                      # off: no error
        monkeypatch.setenv("OTEL_ENABLED", "true")
        with pytest.raises(telemetry.TelemetryUnavailable, match="pip install -r backend/requirements.txt"):
            telemetry.setup_telemetry()
        assert telemetry.tracer_provider() is None


# ══ configuration ════════════════════════════════════════════════════════════
class TestConfig:
    def test_kwargs_when_enabled(self, monkeypatch):
        monkeypatch.setenv("OTEL_ENABLED", "TRUE")
        kw = telemetry.telemetry_kwargs()
        assert kw["tracing"] is True and kw["operation_spans"] is True and kw["auto_configure"] is False and kw["metrics"] is False

    @pytest.mark.parametrize("base,expected", [
        (None, "http://localhost:4318/v1/traces"),
        ("http://jaeger:4318", "http://jaeger:4318/v1/traces"),
        ("http://jaeger:4318/", "http://jaeger:4318/v1/traces"),
        ("http://jaeger:4318/v1/traces", "http://jaeger:4318/v1/traces"),            # the suffix exactly once
    ])
    def test_endpoint_suffix(self, monkeypatch, base, expected):
        if base:
            monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", base)
        assert telemetry.traces_endpoint() == expected

    def test_traces_endpoint_env_is_verbatim(self, monkeypatch):
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector:9/custom")
        assert telemetry.traces_endpoint() == "http://collector:9/custom"

    def test_otlp_exporter_posts_to_the_final_url(self, monkeypatch):
        pytest.importorskip("opentelemetry.exporter.otlp.proto.http.trace_exporter")
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318")
        exporter = OTLPSpanExporter(endpoint=telemetry.traces_endpoint())
        assert exporter._endpoint == "http://jaeger:4318/v1/traces"

    def test_default_exporter_is_otlp_http_and_flushed_on_shutdown(self, monkeypatch):
        pytest.importorskip("opentelemetry.instrumentation.sqlalchemy")
        pytest.importorskip("opentelemetry.instrumentation.redis")
        pytest.importorskip("opentelemetry.instrumentation.httpx")
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        monkeypatch.setenv("OTEL_ENABLED", "true")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318")
        provider = telemetry.setup_telemetry(engine=make_engine("sqlite://"), set_global=False)
        processors = provider._active_span_processor._span_processors
        assert type(processors[0]).__name__ == "QueryScrubber"                    # the scrubber runs before the exporting processor
        exporters = [p.span_exporter for p in processors if hasattr(p, "span_exporter")]
        assert len(exporters) == 1 and isinstance(exporters[0], OTLPSpanExporter) and exporters[0]._endpoint == "http://jaeger:4318/v1/traces"
        from opentelemetry.sdk.trace.export import SpanExportResult
        exported = []
        with patch.object(OTLPSpanExporter, "export", side_effect=lambda spans: exported.extend(spans) or SpanExportResult.SUCCESS):
            with provider.get_tracer("t").start_as_current_span("root"):
                pass                                                 # batched: not exported yet (the batch processor waits for its schedule)
            telemetry.shutdown_telemetry()                           # flush + shutdown: the daemon workers would otherwise lose it
        assert [s.name for s in exported] == ["root"]
        assert telemetry.tracer_provider() is None

    def test_service_name_and_environment(self, otel):
        res = telemetry.tracer_provider().resource.attributes
        assert res["service.name"] == "civicconnect-backend" and "deployment.environment.name" in res

    def test_otel_service_name_env_wins(self, monkeypatch):
        pytest.importorskip("opentelemetry.sdk")
        pytest.importorskip("opentelemetry.instrumentation.sqlalchemy")
        pytest.importorskip("opentelemetry.instrumentation.redis")
        pytest.importorskip("opentelemetry.instrumentation.httpx")
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        monkeypatch.setenv("OTEL_SERVICE_NAME", "other-name")
        provider = telemetry.setup_telemetry(span_exporter=InMemorySpanExporter(), engine=make_engine("sqlite://"), set_global=False)
        assert provider.resource.attributes["service.name"] == "other-name"

    def test_enable_twice_is_idempotent(self, otel):
        exporter, engine = otel
        first = telemetry.tracer_provider()
        assert telemetry.setup_telemetry(span_exporter=exporter, engine=engine, set_global=False) is first
        with telemetry.tracer_provider().get_tracer("t").start_as_current_span("parent"), engine.connect() as c:
            c.exec_driver_sql("select 1")
        names = [s.name for s in exporter.get_finished_spans() if s.attributes.get("db.system") == "sqlite"]
        assert names and len(names) == len(set(names)), names                            # one span per operation (connect, statement): not instrumented twice


# ══ the request ══════════════════════════════════════════════════════════════
def _app(provider, engine, client_factory=None) -> FastAPI:
    """A test app wired like backend.main: native telemetry, the request-id middleware calling set_request_id, an endpoint using SQL and httpx."""
    app = FastAPI(telemetry={**telemetry.telemetry_kwargs(), "tracer_provider": provider})

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        telemetry.set_request_id(request.headers.get("X-Request-ID", "none"))
        return await call_next(request)

    @app.get("/ping")
    def ping():
        with engine.connect() as c:
            c.exec_driver_sql("select 1")
        return {"ok": True}

    @app.get("/search")
    def search(q: str = "", lat: float = 0.0):
        return {"ok": True}

    @app.get("/outbound")
    def outbound():
        with httpx.Client() as client, patch.object(httpcore.ConnectionPool, "handle_request", return_value=httpcore.Response(200, content=b'{"x": 1}')):
            return client.get("http://example.test/ai?email=alice%40example.test&lat=19.07").json()          # the real transport (MockTransport is not instrumented), the network call replaced

    return app


class TestRequest:
    def test_one_server_span_with_sql_child_and_request_id(self, otel):
        exporter, engine = otel
        res = TestClient(_app(telemetry.tracer_provider(), engine)).get("/ping", headers={"X-Request-ID": "req-123"})
        assert res.status_code == 200
        spans = exporter.get_finished_spans()
        from opentelemetry.trace import SpanKind
        servers = [s for s in spans if s.kind == SpanKind.SERVER]
        assert len(servers) == 1, [s.name for s in spans]                    # native telemetry only: no second server span
        server = servers[0]
        assert server.attributes[telemetry.REQUEST_ID_ATTR] == "req-123"
        assert server.resource.attributes["service.name"] == "civicconnect-backend"
        sql = [s for s in spans if s.attributes.get("db.system") == "sqlite"]          # the skip_dep_check path: sqlalchemy 2.1 is outside the declared range
        assert sql, [s.name for s in spans]
        assert {s.context.trace_id for s in sql} == {server.context.trace_id}
        assert any(s.name.startswith("fastapi.") for s in spans)                       # operation spans (endpoint, dependencies)

    def test_off_kwargs_silence_native_telemetry_even_with_a_provider(self, otel, monkeypatch):
        """FastAPI traces by default once a provider exists; the 'off' dict must stop that."""
        exporter, _ = otel
        monkeypatch.setenv("OTEL_ENABLED", "false")
        off = FastAPI(telemetry={**telemetry.telemetry_kwargs(), "tracer_provider": telemetry.tracer_provider()})

        @off.get("/ping")
        def ping():
            return {"ok": True}

        assert TestClient(off).get("/ping").status_code == 200
        assert exporter.get_finished_spans() == ()

    def test_httpx_call_is_a_child_of_the_request(self, otel):
        exporter, engine = otel
        assert TestClient(_app(telemetry.tracer_provider(), engine)).get("/outbound").json() == {"x": 1}
        spans = exporter.get_finished_spans()
        from opentelemetry.trace import SpanKind
        server = next(s for s in spans if s.kind == SpanKind.SERVER)
        http = [s for s in spans if s.kind == SpanKind.CLIENT and "example.test" in str(s.attributes)]
        assert http and http[0].context.trace_id == server.context.trace_id, [(s.name, dict(s.attributes)) for s in spans]

    def test_redis_call_makes_a_span(self, otel):
        exporter, _ = otel
        tracer = telemetry.tracer_provider().get_tracer("t")
        with tracer.start_as_current_span("parent") as parent:
            assert _fake_redis().get("k") is None
        redis_spans = [s for s in exporter.get_finished_spans() if s.name.upper().startswith("GET")]
        assert redis_spans and redis_spans[0].parent.span_id == parent.get_span_context().span_id

    def test_client_spans_without_a_parent_are_dropped(self, otel):
        """Background polling (XREADGROUP, worker DB queries) must not create one-span traces."""
        exporter, engine = otel
        _fake_redis().get("k")
        with engine.connect() as c:
            c.exec_driver_sql("select 1")
        assert exporter.get_finished_spans() == ()

    def test_unsampled_when_sampler_env_says_off(self, monkeypatch):
        pytest.importorskip("opentelemetry.sdk")
        pytest.importorskip("opentelemetry.instrumentation.sqlalchemy")
        pytest.importorskip("opentelemetry.instrumentation.redis")
        pytest.importorskip("opentelemetry.instrumentation.httpx")
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_off")
        exporter = InMemorySpanExporter()
        provider = telemetry.setup_telemetry(span_exporter=exporter, engine=make_engine("sqlite://"), set_global=False)
        with provider.get_tracer("t").start_as_current_span("x"):
            pass
        assert exporter.get_finished_spans() == ()                         # OTEL_TRACES_SAMPLER still honoured under the client-root wrapper


def _fake_redis() -> redis_lib.Redis:
    """A redis-py client whose connection never touches the network (every command answers nil)."""
    class FakeConnection(redis_lib.Connection):
        def connect(self):
            self._sock = object()

        def send_command(self, *args, **kwargs):
            pass

        def read_response(self, *args, **kwargs):
            return None

        def disconnect(self, *args, **kwargs):
            self._sock = None

        def can_read(self, timeout=0):
            return False

        def check_health(self):
            pass

    return redis_lib.Redis(connection_pool=redis_lib.ConnectionPool(connection_class=FakeConnection))


# ══ trace context through the Redis stream ═══════════════════════════════════
class TestStreamPropagation:
    def _publish_in_span(self, otel):
        from backend.events.publisher import publish
        fake = MagicMock()
        fake.xadd.return_value = "1-0"
        tracer = telemetry.tracer_provider().get_tracer("t")
        with tracer.start_as_current_span("api request") as api, patch("backend.events.publisher.get_redis", return_value=fake):
            publish("civic:ai_jobs", {"event_type": "ai_job", "job_type": "intake", "case_id": "c1"})
        return api, fake.xadd.call_args.args[1]

    def test_publish_adds_traceparent_when_a_span_is_active(self, otel):
        exporter, _ = otel
        api, fields = self._publish_in_span(otel)
        trace_id = format(api.get_span_context().trace_id, "032x")
        assert fields["traceparent"].split("-")[1] == trace_id
        assert all(isinstance(v, str) for v in fields.values())            # XADD needs strings
        producer = next(s for s in exporter.get_finished_spans() if s.name == "civic:ai_jobs publish")
        assert producer.parent.span_id == api.get_span_context().span_id
        assert fields["traceparent"].split("-")[2] == format(producer.context.span_id, "016x")      # the worker's parent is the publish span

    def test_publish_without_an_active_span_adds_nothing(self, otel):
        from backend.events.publisher import publish
        fake = MagicMock()
        fake.xadd.return_value = "1-0"
        with patch("backend.events.publisher.get_redis", return_value=fake):
            publish("civic:ai_jobs", {"k": "v"})
        assert set(fake.xadd.call_args.args[1]) == {"k", "_ts"}

    def test_worker_thread_continues_the_producers_trace(self, otel):
        """The worker is a daemon thread with an empty context: the consumer span must take its parent from the message."""
        from backend.events import workers
        exporter, _ = otel
        api, fields = self._publish_in_span(otel)
        stop, seen = threading.Event(), {}
        fake = MagicMock()

        def xreadgroup(*a, **k):
            if seen:
                stop.set()
                return []
            return [("civic:ai_jobs", [("1-0", dict(fields))])]
        fake.xreadgroup.side_effect = xreadgroup

        def handler(msg):
            from opentelemetry import trace
            seen["thread"] = threading.current_thread().name
            seen["span"] = trace.get_current_span().get_span_context()
            with telemetry.tracer_provider().get_tracer("t").start_as_current_span("ai call"):
                pass

        with patch.object(workers, "get_worker_redis", return_value=fake):
            t = threading.Thread(target=workers._stream_worker, args=("civic:ai_jobs", "g", "c", handler, stop), name="worker-test")
            t.start()
            t.join(10)
        assert not t.is_alive() and seen["thread"] == "worker-test"
        spans = {s.name: s for s in exporter.get_finished_spans()}
        producer, consumer, ai = spans["civic:ai_jobs publish"], spans["civic:ai_jobs process"], spans["ai call"]
        assert consumer.parent.span_id == producer.context.span_id
        assert consumer.context.trace_id == producer.context.trace_id == api.get_span_context().trace_id
        assert ai.parent.span_id == consumer.context.span_id               # work inside the handler (AI call, SQL, httpx) joins the same trace
        assert seen["span"].span_id == consumer.context.span_id
        fake.xack.assert_called_once()

    def test_worker_handler_error_is_recorded_and_not_acked(self, otel):
        from backend.events import workers
        exporter, _ = otel
        _, fields = self._publish_in_span(otel)
        stop, fake = threading.Event(), MagicMock()
        batches = [[("civic:ai_jobs", [("1-0", dict(fields))])]]
        fake.xreadgroup.side_effect = lambda *a, **k: batches.pop() if batches else (stop.set() or [])

        def boom(msg):
            raise ValueError("bad job")

        with patch.object(workers, "get_worker_redis", return_value=fake):
            workers._stream_worker("civic:ai_jobs", "g", "c", boom, stop)
        consumer = next(s for s in exporter.get_finished_spans() if s.name == "civic:ai_jobs process")
        assert consumer.status.status_code.name == "ERROR"
        fake.xack.assert_not_called()

    def test_message_without_trace_fields_gets_a_root_consumer_span(self, otel):
        exporter, _ = otel
        with telemetry.consumer_span("civic:audit", "9-0", {"event_type": "audit"}):
            pass
        span = exporter.get_finished_spans()[0]
        assert span.parent is None and span.attributes["messaging.message.id"] == "9-0"


# ══ telemetry never loses an event or skips a handler ════════════════════════
class _BadTracer:
    def start_as_current_span(self, *a, **k):
        raise RuntimeError("tracer exploded")


def _run_worker(fields: dict, handler) -> MagicMock:
    """Drive ``_stream_worker`` with one message through a fake Redis; returns the fake (to inspect xack)."""
    from backend.events import workers
    stop, fake = threading.Event(), MagicMock()
    batches = [[("civic:ai_jobs", [("1-0", dict(fields))])]]
    fake.xreadgroup.side_effect = lambda *a, **k: batches.pop() if batches else (stop.set() or [])
    with patch.object(workers, "get_worker_redis", return_value=fake):
        workers._stream_worker("civic:ai_jobs", "g", "c", handler, stop)
    return fake


class TestNeverLosesEvents:
    def _publish(self, otel):
        from backend.events.publisher import publish
        fake = MagicMock()
        fake.xadd.return_value = "7-0"
        with telemetry.tracer_provider().get_tracer("t").start_as_current_span("api"), patch("backend.events.publisher.get_redis", return_value=fake):
            result = publish("civic:ai_jobs", {"k": "v"})
        return result, fake

    def test_publish_survives_a_tracer_that_raises(self, otel):
        with patch("opentelemetry.trace.get_tracer", return_value=_BadTracer()):
            result, fake = self._publish(otel)
        assert result == "7-0"
        fake.xadd.assert_called_once()
        assert fake.xadd.call_args.args[1]["k"] == "v"

    def test_publish_survives_get_tracer_raising(self, otel):
        with patch("opentelemetry.trace.get_tracer", side_effect=RuntimeError("no tracer")):
            result, fake = self._publish(otel)
        assert result == "7-0" and fake.xadd.call_count == 1

    def test_publish_survives_a_propagator_that_raises(self, otel):
        with patch("opentelemetry.propagate.inject", side_effect=RuntimeError("inject exploded")):
            result, fake = self._publish(otel)
        assert result == "7-0" and fake.xadd.call_count == 1
        assert "traceparent" not in fake.xadd.call_args.args[1]

    def test_publish_survives_a_failing_trace_context_lookup(self, otel):
        with patch.object(telemetry, "_active_span_context", side_effect=RuntimeError("lookup exploded")):
            result, fake = self._publish(otel)
        assert result == "7-0" and fake.xadd.call_count == 1

    def test_publish_error_still_returns_none_as_before(self, otel):
        from backend.events.publisher import publish
        fake = MagicMock()
        fake.xadd.side_effect = redis_lib.exceptions.ConnectionError("down")
        with telemetry.tracer_provider().get_tracer("t").start_as_current_span("api"), patch("backend.events.publisher.get_redis", return_value=fake):
            assert publish("civic:ai_jobs", {"k": "v"}) is None

    @pytest.mark.parametrize("breakage", ["start_as_current_span", "get_tracer", "extract"])
    def test_handler_runs_once_and_is_acked_when_telemetry_breaks(self, otel, breakage):
        patches = {
            "start_as_current_span": patch("opentelemetry.trace.get_tracer", return_value=_BadTracer()),
            "get_tracer": patch("opentelemetry.trace.get_tracer", side_effect=RuntimeError("no tracer")),
            "extract": patch("opentelemetry.propagate.extract", side_effect=RuntimeError("extract exploded")),
        }
        calls = []
        with patches[breakage]:
            fake = _run_worker({"traceparent": "00-" + "1" * 32 + "-" + "2" * 16 + "-01", "k": "v"}, calls.append)
        assert len(calls) == 1 and calls[0]["k"] == "v"
        fake.xack.assert_called_once_with("civic:ai_jobs", "g", "1-0")

    @pytest.mark.parametrize("broken", [False, True], ids=["healthy", "broken tracer"])
    def test_handler_exception_propagates_exactly_as_before(self, otel, broken):
        calls = []

        def boom(msg):
            calls.append(msg)
            raise ValueError("bad job")

        with patch("opentelemetry.trace.get_tracer", return_value=_BadTracer()) if broken else contextlib.nullcontext():
            fake = _run_worker({"k": "v"}, boom)                       # _stream_worker logs the error and does not ack: unchanged
            with pytest.raises(ValueError, match="bad job"), telemetry.consumer_span("civic:ai_jobs", "1-0", {}):
                boom({})
        assert len(calls) == 2
        fake.xack.assert_not_called()

    @pytest.mark.parametrize("traceparent,tracestate", [
        pytest.param("garbage", "also garbage", id="garbage"),
        pytest.param("00-" + "z" * 32 + "-" + "y" * 16 + "-01", ",,,=,=", id="non-hex"),
        pytest.param("00-" + "0" * 32 + "-" + "0" * 16 + "-01", "", id="all-zero ids"),
        pytest.param("x" * 3000, "k=" + "v" * 3000, id="huge"),
        pytest.param("00---01", "", id="control characters"),
        pytest.param("", "", id="empty"),
    ])
    def test_malformed_trace_context_does_not_crash_or_lose_the_handler_call(self, otel, traceparent, tracestate):
        exporter, _ = otel
        calls = []
        fake = _run_worker({"traceparent": traceparent, "tracestate": tracestate, "k": "v"}, calls.append)
        assert len(calls) == 1
        fake.xack.assert_called_once()
        consumer = next(s for s in exporter.get_finished_spans() if s.name == "civic:ai_jobs process")
        assert consumer.parent is None                                   # nothing usable in the message: a root span

    def test_a_span_that_fails_on_exit_does_not_break_the_body(self, otel):
        class ExitFails:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                raise RuntimeError("end exploded")

        ran = []
        with telemetry._guarded("test span", ExitFails):
            ran.append(1)
        assert ran == [1]
        with pytest.raises(KeyError), telemetry._guarded("test span", ExitFails):
            raise KeyError("body error wins")


# ══ query strings are redacted before export ═════════════════════════════════
class TestRedaction:
    @pytest.mark.parametrize("value,expected", [
        ("http://h:1/p?q=alice&lat=19.07", "http://h:1/p?q=REDACTED&lat=REDACTED"),
        ("/p?q=a%40b.c&limit=10#frag", "/p?q=REDACTED&limit=REDACTED#REDACTED"),
        ("https://user:secret@h/p?x=1", "https://REDACTED@h/p?x=REDACTED"),
        ("/p?alice@example.test", "/p?REDACTED"),
        ("/p?a=&b", "/p?a=REDACTED&REDACTED"),
        ("/p?", "/p?"),
        ("/cases/123", "/cases/123"),
        ("http://h/p", "http://h/p"),
    ])
    def test_redact_url(self, value, expected):
        assert telemetry.redact_url(value) == expected

    def test_scrub_attributes_keeps_names_and_untouched_spans(self):
        assert telemetry.scrub_attributes({"url.query": "q=alice&limit=5", "url.path": "/x"}) == {"url.query": "q=REDACTED&limit=REDACTED", "url.path": "/x"}
        assert telemetry.scrub_attributes({"url.path": "/cases/1", "http.method": "GET"}) is None

    def test_server_span_has_no_query_values(self, otel):
        exporter, engine = otel
        res = TestClient(_app(telemetry.tracer_provider(), engine)).get("/search?q=alice@example.test&lat=19.07")
        assert res.status_code == 200
        from opentelemetry.trace import SpanKind
        server = next(s for s in exporter.get_finished_spans() if s.kind == SpanKind.SERVER)
        assert server.attributes["url.query"] == "q=REDACTED&lat=REDACTED"            # names survive, values do not
        assert server.attributes["url.path"] == "/search"
        for span in exporter.get_finished_spans():
            dump = repr(dict(span.attributes)) + span.name
            assert "alice" not in dump and "19.07" not in dump, dump

    def test_httpx_client_span_has_no_query_values(self, otel):
        exporter, engine = otel
        TestClient(_app(telemetry.tracer_provider(), engine)).get("/outbound")
        client_spans = [s for s in exporter.get_finished_spans() if "example.test" in repr(dict(s.attributes))]
        assert client_spans
        for span in client_spans:
            dump = repr(dict(span.attributes))
            assert "alice" not in dump and "19.07" not in dump, dump
            assert "email=REDACTED&lat=REDACTED" in dump                                # the key names survive

    def test_span_without_a_query_is_untouched(self, otel):
        exporter, engine = otel
        TestClient(_app(telemetry.tracer_provider(), engine)).get("/ping")
        from opentelemetry.trace import SpanKind
        server = next(s for s in exporter.get_finished_spans() if s.kind == SpanKind.SERVER)
        assert server.attributes["url.path"] == "/ping" and "url.query" not in server.attributes

    def test_sql_and_redis_spans_carry_no_parameter_values(self, otel):
        exporter, engine = otel
        with telemetry.tracer_provider().get_tracer("t").start_as_current_span("parent"):
            with engine.connect() as c:
                c.exec_driver_sql("select ?", ("alice@example.test",))
            _fake_redis().set("case:1", "alice@example.test")
        spans = [s for s in exporter.get_finished_spans() if s.name != "parent"]
        assert any(s.attributes.get("db.system") == "sqlite" for s in spans) and any(s.attributes.get("db.system") == "redis" for s in spans)
        assert "alice" not in repr([dict(s.attributes) for s in spans])

    def test_scrubber_matches_the_sdk_layout(self, otel):
        """Fails loudly if a newer SDK stores span attributes elsewhere: the scrubber would then silently stop working."""
        exporter, _ = otel
        with telemetry.tracer_provider().get_tracer("t").start_as_current_span("x", attributes={"url.query": "q=alice", "keep": "alice-is-not-a-url"}):
            pass
        span = exporter.get_finished_spans()[0]
        assert hasattr(span, "_attributes"), "ReadableSpan no longer has _attributes: update telemetry._replace_attributes"
        assert span.attributes["url.query"] == "q=REDACTED" and span.attributes["keep"] == "alice-is-not-a-url"
        assert span.attributes.get("url.query") == span._attributes["url.query"]

    def test_scrubber_failure_drops_the_risky_attributes_instead_of_exporting_them(self, otel):
        exporter, _ = otel
        with patch.object(telemetry, "scrub_attributes", side_effect=RuntimeError("scrub exploded")):
            with telemetry.tracer_provider().get_tracer("t").start_as_current_span("x", attributes={"url.query": "q=alice", "keep": "1"}):
                pass
        span = exporter.get_finished_spans()[0]
        assert "url.query" not in span.attributes and span.attributes["keep"] == "1"


# ══ lifecycle ════════════════════════════════════════════════════════════════
class TestLifecycle:
    def test_global_provider_cannot_be_restarted_after_shutdown(self, monkeypatch):
        pytest.importorskip("opentelemetry.sdk")
        pytest.importorskip("opentelemetry.instrumentation.sqlalchemy")
        pytest.importorskip("opentelemetry.instrumentation.redis")
        pytest.importorskip("opentelemetry.instrumentation.httpx")
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        monkeypatch.setenv("OTEL_ENABLED", "true")
        monkeypatch.setattr(telemetry, "_global_retired", False)                     # restored afterwards
        installed = MagicMock()
        monkeypatch.setattr("opentelemetry.trace.set_tracer_provider", installed)
        assert telemetry.setup_telemetry(span_exporter=InMemorySpanExporter(), engine=make_engine("sqlite://"), set_global=True) is not None
        installed.assert_called_once()
        telemetry.shutdown_telemetry()
        with pytest.raises(telemetry.TelemetryUnavailable, match="restart the process"):
            telemetry.setup_telemetry(span_exporter=InMemorySpanExporter(), engine=make_engine("sqlite://"), set_global=True)
        assert telemetry.tracer_provider() is None
        assert telemetry.setup_telemetry(span_exporter=InMemorySpanExporter(), engine=make_engine("sqlite://"), set_global=False) is not None      # a private provider is fine

    def test_failed_setup_rolls_back_the_instrumentors(self, monkeypatch):
        pytest.importorskip("opentelemetry.sdk")
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        monkeypatch.setenv("OTEL_ENABLED", "true")
        monkeypatch.setattr(telemetry, "_global_retired", False)
        installed = MagicMock()
        monkeypatch.setattr("opentelemetry.trace.set_tracer_provider", installed)
        with patch.object(RedisInstrumentor, "_instrument", side_effect=RuntimeError("redis instrumentation exploded")):
            with pytest.raises(telemetry.TelemetryUnavailable, match="redis instrumentation exploded"):
                telemetry.setup_telemetry(span_exporter=InMemorySpanExporter(), engine=make_engine("sqlite://"), set_global=True)
        assert telemetry.tracer_provider() is None
        assert not SQLAlchemyInstrumentor().is_instrumented_by_opentelemetry          # the one that succeeded was undone
        assert not RedisInstrumentor().is_instrumented_by_opentelemetry and not HTTPXClientInstrumentor().is_instrumented_by_opentelemetry
        installed.assert_not_called()                                                 # the global provider is installed last, so the process can retry
        assert telemetry._global_retired is False
        assert telemetry.setup_telemetry(span_exporter=InMemorySpanExporter(), engine=make_engine("sqlite://"), set_global=False) is not None
