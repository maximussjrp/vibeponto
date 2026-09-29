"""Security/configuration regressions, without external services."""

import importlib
import secrets
from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import create_access_token, decode_token


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("secret", ["", "short", "CHANGE_ME_IN_PRODUCTION_123456789", "x" * 64])
def test_reject_unsafe_production_secret(environment, secret):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment=environment, secret_key=secret)


def test_legacy_jwt_secret_environment(monkeypatch):
    secret = secrets.token_urlsafe(48)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("JWT_SECRET_KEY", secret)
    assert Settings(_env_file=None).secret_key == secret


def test_development_cors_origins_cover_local_frontends():
    settings = Settings(_env_file=None)

    assert "http://localhost:3000" in settings.cors_origins
    assert "http://localhost:3001" in settings.cors_origins


def test_worker_configuration(monkeypatch):
    from app.core.config import settings

    worker = importlib.import_module("app.worker")
    assert worker.celery_app.conf.broker_url == settings.celery_broker_url
    assert worker.celery_app.conf.result_backend == settings.celery_result_backend
    worker.celery_app.loader.import_default_modules()
    assert "app.tasks.auditoria.processar_auditoria_marcacao" in worker.celery_app.tasks
    from celery.beat import ScheduleEntry

    for name, entry in worker.celery_app.conf.beat_schedule.items():
        ScheduleEntry(name=name, app=worker.celery_app, **entry).is_due()


def test_invalid_and_expired_tokens():
    assert decode_token("not-a-token") is None
    assert decode_token(create_access_token({"sub": str(uuid4())}, timedelta(seconds=-10))) is None


def test_api_import_without_storage_network():
    importlib.import_module("app.main")
