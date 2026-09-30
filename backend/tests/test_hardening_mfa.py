"""MFA hardening regressions."""

import asyncio
from uuid import uuid4

import pyotp
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.core.redis as redis_module
from app.core.database import Base
from app.core.security import encrypt_totp_secret, hash_password
from app.models import Tenant, UserRole, UserStatus, Usuario
from app.services.mfa import (
    check_mfa_rate_limit,
    consume_backup_code,
    replace_backup_codes,
    verify_mfa_code,
)

import os

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:54399/test_vibeponto")
pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
async def session_factory():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.fixture
async def redis_mfa(monkeypatch):
    monkeypatch.setattr(redis_module.settings, "redis_url", "redis://localhost:56379/14")
    await redis_module.redis_client.close()
    client = await redis_module.get_redis()
    await client.client.flushdb()
    try:
        yield client
    finally:
        await client.client.flushdb()
        await redis_module.redis_client.close()


async def seed_mfa_user(session_factory, secret: str):
    tenant_id = uuid4()
    user_id = uuid4()
    async with session_factory() as session:
        session.add(Tenant(id=tenant_id, nome="MFA Tenant", cnpj=str(tenant_id.int)[:14], email="mfa@example.com"))
        usuario = Usuario(
            id=user_id,
            tenant_id=tenant_id,
            nome="MFA User",
            email=f"{user_id}@example.com",
            cpf=str(user_id.int)[:11],
            matricula=str(user_id)[:8],
            password_hash=hash_password("Password123!"),
            papel=UserRole.COLABORADOR,
            status=UserStatus.ACTIVE,
            mfa_enabled=True,
            mfa_secret=encrypt_totp_secret(secret),
        )
        session.add(usuario)
        await replace_backup_codes(session, user_id, ["BACKUPCODE01"])
        await session.commit()
    return user_id


async def load_user(session_factory, user_id):
    async with session_factory() as session:
        return session, await session.get(Usuario, user_id)


async def test_totp_valid_invalid_and_replay(session_factory, redis_mfa):
    secret = pyotp.random_base32()
    user_id = await seed_mfa_user(session_factory, secret)
    code = pyotp.TOTP(secret).now()

    async with session_factory() as session:
        usuario = await session.get(Usuario, user_id)
        assert await verify_mfa_code(session, usuario, "000000") is False
        assert await verify_mfa_code(session, usuario, code) is True
        await session.commit()
        assert await verify_mfa_code(session, usuario, code) is False


async def _consume(session_factory, user_id, code):
    async with session_factory() as session:
        ok = await consume_backup_code(session, user_id, code)
        await session.commit()
        return ok


async def test_backup_code_single_use_under_concurrency(session_factory, redis_mfa):
    user_id = await seed_mfa_user(session_factory, pyotp.random_base32())

    results = await asyncio.gather(
        _consume(session_factory, user_id, "BACKUPCODE01"),
        _consume(session_factory, user_id, "BACKUPCODE01"),
    )

    assert sorted(results) == [False, True]


async def test_mfa_rate_limit(redis_mfa, monkeypatch):
    monkeypatch.setattr("app.services.mfa.settings.mfa_attempts_limit", 2)
    monkeypatch.setattr("app.services.mfa.settings.mfa_attempts_window_seconds", 60)
    user_id = uuid4()

    await check_mfa_rate_limit(user_id)
    await check_mfa_rate_limit(user_id)
    with pytest.raises(HTTPException) as exc:
        await check_mfa_rate_limit(user_id)
    assert exc.value.status_code == 429
