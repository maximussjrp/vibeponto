"""Observability contract regressions."""

import json
import logging
import re
from io import StringIO
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

import app.core.observability as obs
import app.main as main_module


class DummyConnection:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def execute(self, statement):
        return None


class HealthyEngine:
    def connect(self):
        return DummyConnection()


class FailingEngine:
    def connect(self):
        raise RuntimeError("database unavailable")


class HealthyRedis:
    @property
    def client(self):
        return self

    async def ping(self):
        return True


async def healthy_redis():
    return HealthyRedis()


@pytest.mark.asyncio
async def test_health_check_is_liveness_only():
    response = await main_module.health_check()

    assert response["status"] == "ok"
    assert response["version"]


@pytest.mark.asyncio
async def test_readiness_check_reports_ready_when_dependencies_are_available(monkeypatch):
    monkeypatch.setattr(main_module, "engine", HealthyEngine())
    monkeypatch.setattr(main_module, "get_redis", healthy_redis)

    response = await main_module.readiness_check()

    assert response["status"] == "ready"
    assert response["checks"] == {"database": "ok", "redis": "ok"}


@pytest.mark.asyncio
async def test_readiness_check_returns_503_without_internal_error_details(monkeypatch):
    monkeypatch.setattr(main_module, "engine", FailingEngine())
    monkeypatch.setattr(main_module, "get_redis", healthy_redis)

    with pytest.raises(HTTPException) as exc:
        await main_module.readiness_check()

    assert exc.value.status_code == 503
    assert exc.value.detail == {
        "status": "unready",
        "version": main_module.settings.app_version,
        "checks": {"database": "error", "redis": "ok"},
    }


@pytest.mark.asyncio
async def test_request_id_valid_invalid_and_response_header():
    transport = httpx.ASGITransport(app=main_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        valid = await client.get("/health", headers={obs.REQUEST_ID_HEADER: "req-123_ok"})
        invalid = await client.get("/health", headers={obs.REQUEST_ID_HEADER: "x" * 200})

    assert valid.headers[obs.REQUEST_ID_HEADER] == "req-123_ok"
    generated = invalid.headers[obs.REQUEST_ID_HEADER]
    assert generated != "x" * 200
    assert re.fullmatch(r"[0-9a-f-]{36}", generated)


@pytest.mark.asyncio
async def test_metrics_endpoint_uses_low_cardinality_route_labels():
    transport = httpx.ASGITransport(app=main_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")
        response = await client.get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert "vibeponto_http_requests_total" in body
    assert 'route="/health"' in body
    assert "req-" not in body


def test_route_template_prefers_normalized_route_path():
    request = SimpleNamespace(scope={"route": SimpleNamespace(path="/documentos/{documento_id}")})

    assert obs.get_route_template(request) == "/documentos/{documento_id}"


def test_json_log_redacts_sensitive_fields_and_does_not_emit_tokens():
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(obs.JsonFormatter())
    logger = logging.getLogger("observability-test")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    logger.info(
        "login failed",
        extra={
            "extra": {
                "Authorization": "Bearer header.payload.signature",
                "password": "secret-password",
                "safe": "value",
            }
        },
    )

    line = stream.getvalue()
    payload = json.loads(line)
    assert "header.payload.signature" not in line
    assert "secret-password" not in line
    assert payload["extra"]["Authorization"] == "[REDACTED]"
    assert payload["extra"]["password"] == "[REDACTED]"
    assert payload["extra"]["safe"] == "value"


def test_opentelemetry_disabled_or_dependency_failure_does_not_break_app(monkeypatch):
    monkeypatch.setattr(obs.settings, "otel_enabled", False)
    assert obs.configure_opentelemetry(app=main_module.app, engine=main_module.engine) is False

    real_import = __import__

    def fail_otel_import(name, *args, **kwargs):
        if name.startswith("opentelemetry"):
            raise ImportError("simulated missing otel dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(obs, "_otel_configured", False)
    monkeypatch.setattr(obs.settings, "otel_enabled", True)
    monkeypatch.setattr("builtins.__import__", fail_otel_import)

    assert obs.configure_opentelemetry(app=main_module.app, engine=main_module.engine) is False
