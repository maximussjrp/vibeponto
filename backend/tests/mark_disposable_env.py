"""Script utilitário para marcar ambientes descartáveis dedicados de teste (OPS-04).

Só deve ser executado para provisionar bases de teste isoladas.
Grava o marcador VIBEPONTO_DISPOSABLE_ENV_ID no PostgreSQL (COMMENT ON DATABASE)
e no Redis (chave __vibeponto_disposable_test_env__).
"""

import asyncio
import os
import secrets
import sys
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.destructive_guard import (
    ENV_ID_VAR,
    PG_MARKER_PREFIX,
    REDIS_MARKER_KEY,
    check_static,
)

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:54399/test_vibeponto",
)
TEST_REDIS_URL = os.getenv(
    "TEST_REDIS_URL",
    "redis://localhost:56379/0",
)


async def provision_markers(env_id: str) -> None:
    # 1. PostgreSQL COMMENT ON DATABASE
    engine = create_async_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            db_name = (await conn.execute(text("SELECT current_database()"))).scalar()
            stmt = text(f'COMMENT ON DATABASE "{db_name}" IS \'{PG_MARKER_PREFIX}{env_id}\';')
            await conn.execute(stmt)
    finally:
        await engine.dispose()

    # 2. Redis marker key
    redis_client = aioredis.Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    try:
        await redis_client.set(REDIS_MARKER_KEY, env_id)
    finally:
        await redis_client.aclose()


def main():
    env_id = os.getenv(ENV_ID_VAR)
    if not env_id:
        env_id = secrets.token_hex(16)
        os.environ[ENV_ID_VAR] = env_id

    # Validar URLs estaticamente antes de conectar
    check_static(TEST_DATABASE_URL, TEST_REDIS_URL, os.environ)

    asyncio.run(provision_markers(env_id))
    print(f"Marcadores de ambiente descartável provisionados com sucesso: {env_id}")


if __name__ == "__main__":
    main()
