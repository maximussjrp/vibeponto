"""Structured logging, correlation IDs, metrics and optional OpenTelemetry."""

from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import time
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from fastapi import Request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from app.core.config import settings

REQUEST_ID_HEADER = settings.request_id_header
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "passwd",
    "secret",
    "token",
    "totp",
    "backup_code",
    "mfa",
    "connection",
    "database_url",
)

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

HTTP_REQUESTS_TOTAL = Counter(
    "vibeponto_http_requests_total",
    "HTTP requests processed by the API. Labels intentionally avoid raw path or IDs.",
    ("method", "route", "status_code"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "vibeponto_http_request_duration_seconds",
    "HTTP request duration in seconds. Route is the normalized route template.",
    ("method", "route", "status_code"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "vibeponto_http_requests_in_progress",
    "HTTP requests currently in progress. Route is unknown until routing completes.",
    ("method",),
)

READINESS_CHECK_DURATION_SECONDS = Histogram(
    "vibeponto_readiness_check_duration_seconds",
    "Readiness dependency check duration in seconds.",
    ("dependency", "result"),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

TIME_ENTRIES_TOTAL = Counter(
    "vibeponto_time_entries_total",
    "Time entries created by source and result. Labels are low-cardinality enumerations.",
    ("source", "result"),
)
OFFLINE_SYNC_TOTAL = Counter(
    "vibeponto_offline_sync_total",
    "Offline sync operations by result. Labels are low-cardinality enumerations.",
    ("result",),
)
AUTH_ATTEMPTS_TOTAL = Counter(
    "vibeponto_auth_attempts_total",
    "Authentication attempts by result. Does not include user, tenant, email or IP labels.",
    ("result",),
)
STORAGE_OPERATIONS_TOTAL = Counter(
    "vibeponto_storage_operations_total",
    "Storage operations by operation and result. Object keys are never labels.",
    ("operation", "result"),
)
STORAGE_OPERATION_DURATION_SECONDS = Histogram(
    "vibeponto_storage_operation_duration_seconds",
    "Storage operation duration in seconds. Object keys are never labels.",
    ("operation", "result"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
CELERY_TASKS_TOTAL = Counter(
    "vibeponto_celery_tasks_total",
    "Celery task executions by task name and result. Task IDs are never labels.",
    ("task_name", "result"),
)
CELERY_TASK_DURATION_SECONDS = Histogram(
    "vibeponto_celery_task_duration_seconds",
    "Celery task duration in seconds by task name and result.",
    ("task_name", "result"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0),
)

_otel_configured = False


def sanitize_request_id(value: str | None) -> str:
    """Accept bounded safe request IDs or generate a fresh UUID."""
    if value and _REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return str(uuid4())


def get_request_id() -> str | None:
    return request_id_var.get()


def set_request_id(value: str) -> contextvars.Token[str | None]:
    return request_id_var.set(value)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    request_id_var.reset(token)


def redact(value: Any) -> Any:
    """Redact sensitive values in dictionaries/lists without logging request bodies globally."""
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in SENSITIVE_KEY_PARTS):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def current_trace_ids() -> tuple[str | None, str | None]:
    try:
        from opentelemetry import trace

        span_context = trace.get_current_span().get_span_context()
        if not span_context.is_valid:
            return None, None
        return f"{span_context.trace_id:032x}", f"{span_context.span_id:016x}"
    except Exception:
        return None, None


class JsonFormatter(logging.Formatter):
    """Small JSON formatter suitable for container logs."""

    def format(self, record: logging.LogRecord) -> str:
        trace_id, span_id = current_trace_ids()
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "service": settings.otel_service_name,
            "environment": settings.environment,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or get_request_id(),
            "trace_id": trace_id,
            "span_id": span_id,
        }

        for attr in ("http_method", "route", "status_code", "duration_ms"):
            value = getattr(record, attr, None)
            if value is not None:
                payload[attr] = value

        extra = getattr(record, "extra", None)
        if extra is not None:
            payload["extra"] = redact(extra)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(redact(payload), ensure_ascii=False, default=str)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    handler = logging.StreamHandler()
    handler.addFilter(RequestContextFilter())

    if settings.structured_logging:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s")
        )

    root.handlers = [handler]


def get_route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return path
    return "unmatched"


def observe_http_request(method: str, route: str, status_code: int, duration_seconds: float) -> None:
    if not settings.metrics_enabled:
        return
    labels = (method.upper(), route, str(status_code))
    HTTP_REQUESTS_TOTAL.labels(*labels).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(*labels).observe(duration_seconds)


def metrics_payload() -> bytes:
    return generate_latest(REGISTRY)


def metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST


def observe_readiness_check(dependency: str, result: str, duration_seconds: float) -> None:
    if settings.metrics_enabled:
        READINESS_CHECK_DURATION_SECONDS.labels(dependency, result).observe(duration_seconds)


def record_time_entry(source: str, result: str) -> None:
    if settings.metrics_enabled:
        TIME_ENTRIES_TOTAL.labels(source, result).inc()


def record_offline_sync(result: str) -> None:
    if settings.metrics_enabled:
        OFFLINE_SYNC_TOTAL.labels(result).inc()


def record_auth_attempt(result: str) -> None:
    if settings.metrics_enabled:
        AUTH_ATTEMPTS_TOTAL.labels(result).inc()


def observe_storage_operation(operation: str, result: str, duration_seconds: float) -> None:
    if not settings.metrics_enabled:
        return
    STORAGE_OPERATIONS_TOTAL.labels(operation, result).inc()
    STORAGE_OPERATION_DURATION_SECONDS.labels(operation, result).observe(duration_seconds)


def observe_celery_task(task_name: str, result: str, duration_seconds: float) -> None:
    if not settings.metrics_enabled:
        return
    CELERY_TASKS_TOTAL.labels(task_name, result).inc()
    CELERY_TASK_DURATION_SECONDS.labels(task_name, result).observe(duration_seconds)


class StorageTimer:
    def __init__(self, operation: str):
        self.operation = operation
        self.start = 0.0
        self.result = "success"

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.result = "error"
        observe_storage_operation(self.operation, self.result, time.perf_counter() - self.start)
        return False


def storage_timer(operation: str) -> StorageTimer:
    return StorageTimer(operation)


def configure_opentelemetry(app=None, engine=None) -> bool:
    """Configure optional OpenTelemetry exporters/instrumentation.

    A missing collector or disabled OTel must never prevent app startup.
    """
    global _otel_configured
    if _otel_configured or not settings.otel_enabled:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception as exc:
        logging.getLogger(__name__).warning("OpenTelemetry dependencies unavailable", extra={"extra": {"error": type(exc).__name__}})
        return False

    try:
        os.environ["OTEL_TRACES_SAMPLER"] = settings.otel_traces_sampler
        os.environ["OTEL_TRACES_SAMPLER_ARG"] = settings.otel_traces_sampler_arg
        resource = Resource.create(
            {
                "service.name": settings.otel_service_name,
                "deployment.environment": settings.environment,
            }
        )
        provider = TracerProvider(resource=resource)
        exporter_kwargs: dict[str, Any] = {}
        if settings.otel_exporter_otlp_endpoint:
            exporter_kwargs["endpoint"] = settings.otel_exporter_otlp_endpoint
        if settings.otel_exporter_otlp_headers:
            headers = {}
            for item in settings.otel_exporter_otlp_headers.split(","):
                if "=" in item:
                    key, value = item.split("=", 1)
                    headers[key.strip()] = value.strip()
            if headers:
                exporter_kwargs["headers"] = headers
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(**exporter_kwargs)))
        trace.set_tracer_provider(provider)

        if app is not None:
            FastAPIInstrumentor.instrument_app(app, excluded_urls="/health,/ready,/metrics")
        if engine is not None:
            SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
        RedisInstrumentor().instrument()
        _otel_configured = True
        return True
    except Exception:
        logging.getLogger(__name__).exception("Failed to configure OpenTelemetry")
        return False


def configure_celery_observability(celery_app) -> None:
    try:
        from celery import signals
    except Exception:
        return

    task_start_times: dict[str, float] = {}

    @signals.task_prerun.connect(weak=False)
    def _task_prerun(task_id=None, task=None, **kwargs):
        if task_id:
            task_start_times[task_id] = time.perf_counter()

    @signals.task_postrun.connect(weak=False)
    def _task_postrun(task_id=None, task=None, state=None, **kwargs):
        task_name = getattr(task, "name", "unknown")
        start = task_start_times.pop(task_id, time.perf_counter()) if task_id else time.perf_counter()
        result = "success" if state == "SUCCESS" else "failure" if state == "FAILURE" else "other"
        observe_celery_task(task_name, result, time.perf_counter() - start)

    if settings.otel_enabled:
        try:
            from opentelemetry.instrumentation.celery import CeleryInstrumentor

            CeleryInstrumentor().instrument()
        except Exception:
            logging.getLogger(__name__).exception("Failed to configure Celery OpenTelemetry")
