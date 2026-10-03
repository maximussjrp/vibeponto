"""Testes de segurança e idempotência para backend/scripts/seed_staging.py (STG.1-PLAN-01)."""

import os
import pytest
from scripts.seed_staging import seed_staging


@pytest.mark.asyncio
async def test_seed_staging_fails_when_db_url_missing(monkeypatch):
    """Garante que seed_staging aborta se STAGING_DATABASE_URL não for informada."""
    monkeypatch.delenv("STAGING_DATABASE_URL", raising=False)
    monkeypatch.setenv("STAGING_REDIS_URL", "redis://localhost:56379/0")
    with pytest.raises(RuntimeError, match="STAGING_DATABASE_URL e STAGING_REDIS_URL são obrigatórias"):
        await seed_staging()


@pytest.mark.asyncio
async def test_seed_staging_fails_when_credentials_missing(monkeypatch):
    """Garante que seed_staging aborta se credenciais sintéticas estivem ausentes."""
    monkeypatch.setenv("STAGING_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:54399/test_vibeponto")
    monkeypatch.setenv("STAGING_REDIS_URL", "redis://localhost:56379/0")
    monkeypatch.delenv("STAGING_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("STAGING_ADMIN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError):
        await seed_staging()


@pytest.mark.asyncio
async def test_seed_staging_fails_on_staging_environment(monkeypatch):
    """Garante que seed_staging recusa rodar quando ENVIRONMENT=staging (OPS-04)."""
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_TESTING", "true")
    monkeypatch.setenv("VIBEPONTO_DISPOSABLE_ENV_ID", "testenv_staging_e2e_1234567890abcdef")
    monkeypatch.setenv("STAGING_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:54399/test_vibeponto")
    monkeypatch.setenv("STAGING_REDIS_URL", "redis://localhost:56379/0")
    monkeypatch.setenv("STAGING_ADMIN_EMAIL", "admin@staging.vibeponto.com")
    monkeypatch.setenv("STAGING_ADMIN_PASSWORD", "AdminPass123!")
    monkeypatch.setenv("STAGING_USER_EMAIL", "user@staging.vibeponto.com")
    monkeypatch.setenv("STAGING_USER_PASSWORD", "UserPass123!")

    with pytest.raises(RuntimeError, match="ENVIRONMENT indica ambiente não descartável"):
        await seed_staging()


@pytest.mark.asyncio
async def test_seed_staging_fails_without_disposable_markers(monkeypatch):
    """Garante que seed_staging aborta se os marcadores OPS-04 não forem validados."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_TESTING", "false")
    monkeypatch.setenv("STAGING_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:54399/test_vibeponto")
    monkeypatch.setenv("STAGING_REDIS_URL", "redis://localhost:56379/0")
    monkeypatch.setenv("STAGING_ADMIN_EMAIL", "admin@staging.vibeponto.com")
    monkeypatch.setenv("STAGING_ADMIN_PASSWORD", "AdminPass123!")
    monkeypatch.setenv("STAGING_USER_EMAIL", "user@staging.vibeponto.com")
    monkeypatch.setenv("STAGING_USER_PASSWORD", "UserPass123!")

    with pytest.raises(RuntimeError, match="OPS-04: Impossível realizar seed"):
        await seed_staging()
