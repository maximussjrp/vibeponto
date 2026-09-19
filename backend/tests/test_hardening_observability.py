"""Health and readiness regressions."""

import pytest
from fastapi import HTTPException

import app.main as main_module

pytestmark = pytest.mark.asyncio


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


async def test_health_check_is_liveness_only():
    response = await main_module.health_check()

    assert response["status"] == "ok"
    assert response["version"]


async def test_readiness_check_reports_ready_when_dependencies_are_available(monkeypatch):
    monkeypatch.setattr(main_module, "engine", HealthyEngine())
    monkeypatch.setattr(main_module, "get_redis", healthy_redis)

    response = await main_module.readiness_check()

    assert response["status"] == "ready"
    assert response["checks"] == {"database": "ok", "redis": "ok"}


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
