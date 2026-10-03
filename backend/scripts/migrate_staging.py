"""Script para aplicar migrations/schema Alembic no banco de Staging com guarda OPS-04 (STG.1-PLAN-01)."""

import asyncio
import os
import sys
from pathlib import Path

import app.models  # noqa: F401 - Registra todas as tabelas no Base.metadata
from app.core.database import Base
from tests.destructive_guard import UnsafeTestEnvironment, verify_disposable_environment


async def apply_staging_migrations() -> None:
    db_url = os.getenv("STAGING_DATABASE_URL", "").strip()
    redis_url = os.getenv("STAGING_REDIS_URL", "").strip()

    if not db_url or not redis_url:
        raise RuntimeError("Configuração ausente: STAGING_DATABASE_URL e STAGING_REDIS_URL são obrigatórias.")

    # Guarda OPS-04
    try:
        env_id = await verify_disposable_environment(db_url, redis_url, os.environ)
    except UnsafeTestEnvironment as err:
        raise RuntimeError(f"OPS-04: Impossível aplicar migrations em Staging. {err}") from err

    # Criar schema completo no banco descartável
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    print(f"Migrations/schema sincronizados com sucesso no banco de staging (Ambiente: {env_id})")


if __name__ == "__main__":
    try:
        asyncio.run(apply_staging_migrations())
    except Exception as exc:
        print(f"Erro ao aplicar migrations no staging: {exc}", file=sys.stderr)
        sys.exit(1)
