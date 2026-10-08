"""OpenTelemetry wiring (WP8). Off by default: with ``OTEL_ENABLED`` false nothing here imports an ``opentelemetry`` module and every helper returns at once.

Pieces
* ``telemetry_kwargs()``   : the ``telemetry=`` argument of ``FastAPI(...)``. FastAPI >= 0.142 traces natively (and by default), so the server span comes from it
                             (never also from opentelemetry-instrumentation-fastapi). Off: everything disabled, ``auto_configure`` False (else FastAPI would add its own
                             OTLP exporter as soon as ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set). On: tracing only; we own the provider, so ``auto_configure`` is False too.
* ``setup_telemetry()``    : call from the app lifespan (inside the serving process: the BatchSpanProcessor thread is not fork-safe). Builds the provider, the OTLP/HTTP
                             exporter and the SQLAlchemy / Redis / httpx instrumentors. Idempotent. ``shutdown_telemetry()`` flushes (workers are daemon threads).
* ``set_request_id()``     : puts the request id on the active (server) span.
* ``producer_span`` / ``inject_trace_context`` / ``consumer_span``: trace context through the Redis event envelope (``traceparent`` / ``tracestate`` fields).
                             Telemetry can never lose an event or skip a handler: any failure of the tracer or propagator is logged once and the code runs as without it;
                             exceptions of the wrapped code itself propagate untouched.
* Privacy: query strings are redacted before export. A span processor runs first and rewrites ``url.query`` / ``url.full`` / ``http.url`` / ``http.target`` /
  ``url.path`` (FastAPI's server span and httpx's client span carry the raw query, which can hold names, e-mails, phone numbers, coordinates): parameter names stay,
  every value becomes ``REDACTED`` (``q=REDACTED&limit=REDACTED``); passwords in a URL are replaced too. SQL spans carry placeholders and Redis arguments are sanitised by
  the instrumentation (asserted in the tests). Exception messages recorded as span events are not scrubbed.
* One start per process: after ``shutdown_telemetry()`` a global provider cannot be installed again (OpenTelemetry refuses to replace it), so ``setup_telemetry()``
  then raises ``TelemetryUnavailable`` (restart the process).
"""
from __future__ import annotations

import contextlib
import logging
import os
import re
import sys
import threading
from collections.abc import Callable, Iterator, Mapping, MutableMapping
from typing import Any

from backend.core.config import settings

log = logging.getLogger("civicconnect.telemetry")

SERVICE_NAME = "civicconnect-backend"
DEFAULT_ENDPOINT = "http://localhost:4318"          # OTLP/HTTP base URL; the exporter path /v1/traces is appended here
TRACES_PATH = "/v1/traces"
REQUEST_ID_ATTR = "civic.request_id"
CONTEXT_FIELDS = ("traceparent", "tracestate")      # W3C trace context, the extra fields of the Redis stream envelope
_TRUE = {"1", "true", "yes", "on"}

REDACTED = "REDACTED"
URL_KEYS = ("url.query", "url.full", "http.url", "http.target", "url.path")     # span attributes that may carry a query string (or a password)

_lock = threading.RLock()
_state: dict[str, Any] = {"provider": None, "instrumentors": [], "global": False}
_global_retired = False         # a global provider was installed and shut down: OpenTelemetry refuses to install another one in this process
_warned: set[str] = set()


class TelemetryUnavailable(RuntimeError):
    """``OTEL_ENABLED`` is true but the OpenTelemetry packages are not installed."""


def _warn_once(what: str, exc: BaseException) -> None:
    """Telemetry failures are never fatal: log the first of each kind (type and message only) at warning, the rest at debug."""
    (log.debug if what in _warned else log.warning)("OpenTelemetry %s failed, continuing without it: %s: %s", what, type(exc).__name__, exc)
    _warned.add(what)


def _setting(name: str) -> str | None:
    """The live process environment first (it always wins, also when set after start-up, as in tests), else the Settings field of ``config.py`` (so the repo's environment file works)."""
    value = os.environ.get(name)
    if value is None or value == "":
        value = getattr(settings, name, None)
    return None if value is None or value == "" else str(value)


def telemetry_enabled() -> bool:
    """``OTEL_ENABLED`` (default false)."""
    return (_setting("OTEL_ENABLED") or "").strip().lower() in _TRUE


def telemetry_kwargs() -> dict[str, Any]:
    """The ``telemetry=`` argument of ``FastAPI(...)``: native server spans on when enabled, otherwise every signal and the env auto-configuration off."""
    on = telemetry_enabled()
    return {"tracing": on, "operation_spans": on, "metrics": False, "logs": False, "auto_configure": False}


def traces_endpoint() -> str:
    """Final OTLP/HTTP traces URL: ``OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`` verbatim, else ``<OTEL_EXPORTER_OTLP_ENDPOINT>/v1/traces`` (the suffix exactly once).

    The exporter's ``endpoint=`` argument is used verbatim since opentelemetry 1.45, so the suffix is added here instead of leaving it to the library."""
    verbatim = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    if verbatim:
        return verbatim
    base = (_setting("OTEL_EXPORTER_OTLP_ENDPOINT") or DEFAULT_ENDPOINT).rstrip("/")
    return base if base.endswith(TRACES_PATH) else base + TRACES_PATH


def _resource_attributes() -> dict[str, str]:
    attrs = {"deployment.environment.name": settings.ENVIRONMENT}
    if not os.environ.get("OTEL_SERVICE_NAME") and "service.name=" not in os.environ.get("OTEL_RESOURCE_ATTRIBUTES", ""):
        attrs["service.name"] = SERVICE_NAME            # an explicit OTEL_SERVICE_NAME / OTEL_RESOURCE_ATTRIBUTES wins; the SDK lets arguments beat the environment
    return attrs


_USERINFO = re.compile(r"(?<=//)[^/?#@]*@")


def _redact_query(query: str) -> str:
    """``q=alice&lat=1`` -> ``q=REDACTED&lat=REDACTED``; a bare token without ``=`` is itself a value."""
    return "&".join((f"{part.partition('=')[0]}={REDACTED}" if "=" in part else REDACTED) for part in query.split("&") if part != "")


def redact_url(value: str) -> str:
    """Redact the query string (values only), a fragment and the credentials of a URL, absolute or ``/path?query``; a value without any of them is returned as is."""
    if "?" not in value and "#" not in value and "@" not in value:
        return value
    rest, hash_, _fragment = value.partition("#")
    base, mark, query = rest.partition("?")
    base = _USERINFO.sub(f"{REDACTED}@", base)
    return base + (mark + _redact_query(query) if mark else "") + (f"#{REDACTED}" if hash_ else "")


def scrub_attributes(attributes: Mapping[str, Any]) -> dict[str, Any] | None:
    """The attributes with every query string redacted, or None when nothing had to change."""
    changed: dict[str, Any] = {}
    for key in URL_KEYS:
        value = attributes.get(key)
        if isinstance(value, str):
            new = _redact_query(value) if key == "url.query" else redact_url(value)
            if new != value:
                changed[key] = new
    return {**attributes, **changed} if changed else None


def _replace_attributes(span: Any, attributes: Mapping[str, Any]) -> None:
    """The one place that touches a private field: a finished ``ReadableSpan`` keeps its (immutable) attributes in ``_attributes``. The span object handed to
    ``on_end`` is a snapshot made for the processors, so replacing the field changes only what is exported. ``test_scrubber_matches_the_sdk_layout`` fails if the SDK changes."""
    from opentelemetry.attributes import BoundedAttributes
    old = span._attributes
    new = BoundedAttributes(maxlen=getattr(old, "maxlen", None), attributes=dict(attributes), max_value_len=getattr(old, "max_value_len", None))
    new.dropped = getattr(old, "dropped", 0)
    span._attributes = new


def _scrubbing_processor():
    """A span processor that redacts query strings on every finished span. It must be added before the exporting processor (processors see the same span in order)."""
    from opentelemetry.sdk.trace import SpanProcessor

    class QueryScrubber(SpanProcessor):
        def on_end(self, span) -> None:
            try:
                clean = scrub_attributes(span.attributes or {})
                if clean is not None:
                    _replace_attributes(span, clean)
            except Exception as exc:                                  # never export an unscrubbed query: drop the risky keys instead
                _warn_once("query scrubbing", exc)
                with contextlib.suppress(Exception):
                    _replace_attributes(span, {k: v for k, v in span.attributes.items() if k not in URL_KEYS})

    return QueryScrubber()


def _drop_client_roots(delegate):
    """Sampler wrapper: a CLIENT span without a parent is dropped. Background threads (the blocking XREADGROUP poll every 5 s, the push and scan workers' DB
    polling, startup queries) would otherwise each emit a one-span trace and drown Jaeger; real work is always under a server or consumer span."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace.sampling import Decision, Sampler, SamplingResult
    from opentelemetry.trace import SpanKind

    class DropClientRoots(Sampler):
        def should_sample(self, parent_context, trace_id, name, kind=None, attributes=None, links=None, trace_state=None):
            if kind == SpanKind.CLIENT and not trace.get_current_span(parent_context).get_span_context().is_valid:
                return SamplingResult(Decision.DROP)
            return delegate.should_sample(parent_context, trace_id, name, kind, attributes, links, trace_state)

        def get_description(self) -> str:
            return f"DropClientRoots({delegate.get_description()})"

    return DropClientRoots()


def setup_telemetry(app: Any = None, *, span_exporter: Any = None, engine: Any = None, set_global: bool = True):
    """Build the tracer provider, exporter and instrumentors once; returns the provider (None when telemetry is off). Call from the lifespan, not at import.

    ``span_exporter`` (tests) replaces the OTLP exporter and uses a SimpleSpanProcessor; ``set_global=False`` keeps the process-wide provider untouched (it can only be
    set once); ``engine`` defaults to the engine of ``backend.db.session``."""
    if not telemetry_enabled() and span_exporter is None:
        return None
    with _lock:
        if _state["provider"] is not None:
            return _state["provider"]
        if set_global and _global_retired:
            raise TelemetryUnavailable("OpenTelemetry was shut down in this process and cannot be started again (the global tracer provider cannot be replaced); restart the process")
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
            if span_exporter is None:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            from opentelemetry.instrumentation.redis import RedisInstrumentor
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        except ImportError as exc:
            raise TelemetryUnavailable(f"OTEL_ENABLED=true needs the OpenTelemetry packages ({exc}); run: pip install -r backend/requirements.txt") from exc
        provider = TracerProvider(resource=Resource.create(_resource_attributes()))
        provider.sampler = _drop_client_roots(provider.sampler)         # the SDK default sampler honours OTEL_TRACES_SAMPLER / _ARG
        provider.add_span_processor(_scrubbing_processor())              # first: the exporting processor below then only ever sees redacted spans
        if span_exporter is not None:
            provider.add_span_processor(SimpleSpanProcessor(span_exporter))
        else:
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=traces_endpoint())))
        if engine is None:
            from backend.db import session as db_session
            engine = db_session.engine
        instrumentors = []
        try:
            for instrumentor, kwargs in (
                # skip_dep_check: the SQLAlchemy instrumentation declares sqlalchemy<2.1 and, with 2.1.x, otherwise logs a DependencyConflict and records NO spans
                # (opentelemetry-python-contrib issue 5118, fix PR 5120 not merged when pinned).
                (SQLAlchemyInstrumentor(), {"engine": engine, "skip_dep_check": True}),
                (RedisInstrumentor(), {}),
                (HTTPXClientInstrumentor(), {}),
            ):
                instrumentor.instrument(tracer_provider=provider, **kwargs)
                instrumentors.append(instrumentor)
        except Exception as exc:
            for done in instrumentors:
                with contextlib.suppress(Exception):
                    done.uninstrument()
            provider.shutdown()
            # SQLAlchemy 2.1 made greenlet optional, yet the SQLAlchemy instrumentation wraps sqlalchemy.ext.asyncio, which imports it (greenlet is pinned in requirements.txt)
            raise TelemetryUnavailable(f"OpenTelemetry instrumentation failed ({type(exc).__name__}: {exc}); run: pip install -r backend/requirements.txt") from exc
        if set_global:
            trace.set_tracer_provider(provider)                          # last, so a failed setup leaves the process able to try again
        _state.update(provider=provider, instrumentors=instrumentors, **{"global": set_global})
        if app is not None:
            app.state.tracer_provider = provider
        log.info("OpenTelemetry on: service=%s exporter=%s", SERVICE_NAME, "in-memory" if span_exporter is not None else traces_endpoint())
        return provider


def tracer_provider():
    """The provider built by ``setup_telemetry`` (None while off)."""
    return _state["provider"]


def shutdown_telemetry() -> None:
    """Flush pending spans, stop the exporter and remove the instrumentation. Safe when telemetry is off; call at app shutdown (daemon workers die without flushing)."""
    global _global_retired
    with _lock:
        provider, instrumentors = _state["provider"], _state["instrumentors"]
        _global_retired = _global_retired or (provider is not None and _state["global"])
        _state.update(provider=None, instrumentors=[], **{"global": False})
    for instrumentor in instrumentors:
        with contextlib.suppress(Exception):
            instrumentor.uninstrument()
    if provider is not None:
        try:
            provider.force_flush()
            provider.shutdown()
        except Exception as exc:
            log.warning("OpenTelemetry flush failed: %s", exc)


def set_request_id(request_id: str) -> None:
    """Put the request id (``X-Request-ID``) on the active span; call from the request-id middleware."""
    if _state["provider"] is None:
        return
    from opentelemetry import trace
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute(REQUEST_ID_ATTR, request_id)


# ── trace context through the Redis event envelope ───────────────────────────
def _active_span_context():
    from opentelemetry import trace
    ctx = trace.get_current_span().get_span_context()
    return ctx if ctx.is_valid else None


@contextlib.contextmanager
def _guarded(what: str, make: Callable[[], Any]) -> Iterator[None]:
    """Enter ``make()`` (a context manager) around the body. If telemetry fails while entering or leaving, log it once and run the body without the span; an exception
    of the body propagates exactly as it would without telemetry (the span records it on the way out)."""
    stack = contextlib.ExitStack()
    entered = False
    try:
        stack.enter_context(make())
        entered = True
    except Exception as exc:
        _warn_once(what, exc)
    try:
        yield
    except BaseException:
        if entered:
            _leave(what, stack, sys.exc_info())
        raise
    if entered:
        _leave(what, stack, (None, None, None))


def _leave(what: str, stack: contextlib.ExitStack, exc_info: Any) -> None:
    try:
        stack.__exit__(*exc_info)
    except Exception as exc:
        if exc_info[1] is not exc:
            _warn_once(what, exc)


def _in_a_trace() -> bool:
    """Telemetry is on and a span is active (a lookup failure counts as no)."""
    if _state["provider"] is None:
        return False
    try:
        return _active_span_context() is not None
    except Exception as exc:
        _warn_once("trace context lookup", exc)
        return False


def producer_span(stream: str):
    """A PRODUCER span around an XADD, only when telemetry is on and a span is already active (the publish is part of a traced request)."""
    if not _in_a_trace():
        return contextlib.nullcontext()

    def make():
        from opentelemetry import trace
        tracer = trace.get_tracer("civicconnect.events", tracer_provider=_state["provider"])
        attrs = {"messaging.system": "redis", "messaging.destination.name": stream}
        return tracer.start_as_current_span(f"{stream} publish", kind=trace.SpanKind.PRODUCER, attributes=attrs)

    return _guarded("producer span", make)


def inject_trace_context(fields: MutableMapping[str, str]) -> MutableMapping[str, str]:
    """Add ``traceparent`` (and ``tracestate`` when set) to the envelope fields when telemetry is on and a span is active; otherwise (and on any failure) leave them untouched."""
    if not _in_a_trace():
        return fields
    try:
        from opentelemetry import propagate
        carrier: dict[str, str] = {}
        propagate.inject(carrier)
        found = {key: carrier[key] for key in CONTEXT_FIELDS if isinstance(carrier.get(key), str) and carrier[key]}
    except Exception as exc:
        _warn_once("trace context injection", exc)
        return fields
    fields.update(found)
    return fields


def extract_trace_context(fields: Mapping[str, Any]):
    """The OpenTelemetry context carried by the envelope fields (an empty context when there is none or it is malformed)."""
    from opentelemetry import propagate
    return propagate.extract({k: v for k in CONTEXT_FIELDS if isinstance(v := fields.get(k), str)})


def consumer_span(stream: str, entry_id: str, fields: Mapping[str, Any]):
    """Run a stream handler inside a CONSUMER span parented on the producer's context. Worker threads start with an empty context, so the parent is passed explicitly.
    A no-op while telemetry is off; if the span cannot be started the handler still runs, exactly once."""
    if _state["provider"] is None:
        return contextlib.nullcontext()

    def make():
        from opentelemetry import trace
        tracer = trace.get_tracer("civicconnect.events", tracer_provider=_state["provider"])
        attrs = {"messaging.system": "redis", "messaging.destination.name": stream, "messaging.message.id": str(entry_id)}
        return tracer.start_as_current_span(f"{stream} process", context=extract_trace_context(fields), kind=trace.SpanKind.CONSUMER, attributes=attrs)

    return _guarded("consumer span", make)
