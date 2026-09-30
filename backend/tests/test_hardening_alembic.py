"""Alembic migration regressions."""

import asyncio
from pathlib import Path

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.core.config as config_module
import app.core.database as database_module
from alembic import command
from app.core.database import Base

import os

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:54399/test_vibeponto")


async def reset_database():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    await engine.dispose()


async def current_version():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as conn:
        version = await conn.scalar(text("SELECT version_num FROM alembic_version"))
    await engine.dispose()
    return version


def test_alembic_upgrade_head_on_empty_database(monkeypatch):
    asyncio.run(reset_database())

    monkeypatch.setattr(config_module.settings, "database_url", TEST_DATABASE_URL)
    monkeypatch.setattr(database_module.settings, "database_url", TEST_DATABASE_URL)

    alembic_cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    assert asyncio.run(current_version()) == "20260930_0002"
