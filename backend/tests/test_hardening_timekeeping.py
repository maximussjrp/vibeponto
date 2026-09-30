"""Timekeeping integrity regressions for offline sync."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.security import hash_password
from app.models import (
    MarcacaoEvento,
    MarcacaoPonto,
    MarcacaoTipo,
    Tenant,
    UserRole,
    UserStatus,
    Usuario,
)
from app.schemas import MarcacaoCreate
from app.services.timekeeping import MarcacaoContext, create_offline_marcacao_idempotent

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


async def seed_user(session_factory, tenant_id=None):
    tenant_id = tenant_id or uuid4()
    user_id = uuid4()
    async with session_factory() as session:
        session.add(Tenant(id=tenant_id, nome=f"Tenant {tenant_id}", cnpj=str(tenant_id.int)[:14], email="t@example.com"))
        session.add(
            Usuario(
                id=user_id,
                tenant_id=tenant_id,
                nome="Colaborador",
                email=f"{user_id}@example.com",
                cpf=str(user_id.int)[:11],
                matricula=str(user_id)[:8],
                password_hash=hash_password("Password123!"),
                papel=UserRole.COLABORADOR,
                status=UserStatus.ACTIVE,
            )
        )
        await session.commit()
    return tenant_id, user_id


def marcacao(sync_id: str, evento=MarcacaoEvento.ENTRADA):
    return MarcacaoCreate(
        tipo=MarcacaoTipo.WEB,
        evento=evento,
        timestamp_local=datetime(2026, 1, 23, 12, 0, tzinfo=UTC),
        timezone="America/Sao_Paulo",
        latitude=Decimal("0.0"),
        longitude=Decimal("0.0"),
        accuracy_metros=5,
        sync_id=sync_id,
    )


async def create_one(session_factory, tenant_id, user_id, sync_id):
    async with session_factory() as session:
        record = await create_offline_marcacao_idempotent(
            session,
            marcacao(sync_id),
            MarcacaoContext(tenant_id=tenant_id, usuario_id=user_id, origem="test"),
        )
        await session.commit()
        return record.id


async def count_sync(session_factory, tenant_id, user_id, sync_id):
    async with session_factory() as session:
        return await session.scalar(
            select(func.count(MarcacaoPonto.id)).where(
                MarcacaoPonto.tenant_id == tenant_id,
                MarcacaoPonto.usuario_id == user_id,
                MarcacaoPonto.sync_id == sync_id,
            )
        )


async def test_offline_sync_idempotent_sequential_and_zero_coordinates(session_factory):
    tenant_id, user_id = await seed_user(session_factory)

    first_id = await create_one(session_factory, tenant_id, user_id, "local-1")
    second_id = await create_one(session_factory, tenant_id, user_id, "local-1")

    assert first_id == second_id
    assert await count_sync(session_factory, tenant_id, user_id, "local-1") == 1
    async with session_factory() as session:
        record = await session.get(MarcacaoPonto, first_id)
        assert record.latitude == Decimal("0E-8")
        assert record.longitude == Decimal("0E-8")
        assert record.geom is not None


async def test_offline_sync_idempotent_concurrent(session_factory):
    tenant_id, user_id = await seed_user(session_factory)

    ids = await asyncio.gather(
        create_one(session_factory, tenant_id, user_id, "race-1"),
        create_one(session_factory, tenant_id, user_id, "race-1"),
    )

    assert ids[0] == ids[1]
    assert await count_sync(session_factory, tenant_id, user_id, "race-1") == 1


async def test_offline_sync_scope_and_distinct_ids(session_factory):
    tenant_id, user_id = await seed_user(session_factory)
    other_tenant_id, other_user_id = await seed_user(session_factory)

    first_id = await create_one(session_factory, tenant_id, user_id, "same-local-id")
    other_id = await create_one(session_factory, other_tenant_id, other_user_id, "same-local-id")
    distinct_id = await create_one(session_factory, tenant_id, user_id, "different-local-id")

    assert first_id != other_id
    assert first_id != distinct_id
