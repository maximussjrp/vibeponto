"""Teste de integração com Redis real para o fluxo completo de reset de senha (USR-39)."""

import os

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:54399/test_vibeponto")
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:56379/0")

# Definir a variável de ambiente antes de qualquer import do app
os.environ["REDIS_URL"] = TEST_REDIS_URL
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest
import redis.asyncio as redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.core.config import settings
from app.core.database import Base
from app.core.rate_limit import auth_rate_limit
from app.core.redis import RedisClient, get_redis
from app.core.security import hash_password, verify_password
from app.main import app
from app.models import Tenant, UserRole, UserStatus, Usuario

settings.redis_url = TEST_REDIS_URL
settings.database_url = TEST_DATABASE_URL


@pytest.fixture
async def db_session_factory():
    ddl_engine = create_async_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    async with ddl_engine.connect() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        await conn.run_sync(Base.metadata.create_all)
    await ddl_engine.dispose()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield session_maker
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_full_password_reset_flow_with_real_redis(db_session_factory):
    """
    USR-39: Teste de integração real cobrindo a sequência completa do reset de senha:
    1. Emitir token.
    2. Verificar token: válido (POST /auth/password/reset/verify).
    3. Confirmar que ele CONTINUA no Redis (operação PEEK não destrutiva).
    4. Confirmar a redefinição de senha.
    5. Verificar que a senha foi alterada no banco.
    6. Verificar que o token foi consumido (GETDEL).
    7. Tentar reutilizar o token: operação negada.
    8. Confirmar a revogação das sessões.
    """
    # Inicializar o pool de conexões do Redis estritamente dentro do event loop deste teste
    if RedisClient._pool is not None:
        await RedisClient._pool.disconnect()
        RedisClient._pool = None
    RedisClient._instance = None

    redis_pool = redis.ConnectionPool.from_url(TEST_REDIS_URL, decode_responses=True)
    redis_client_obj = RedisClient()
    redis_client_obj._pool = redis_pool
    raw_redis = redis.Redis(connection_pool=redis_pool)
    await raw_redis.flushdb()

    tenant_id = uuid4()
    user_id = uuid4()
    original_password = "OldPassword123!"
    new_password = "NewSecurePassword123!"

    # 1. Seed user e tenant no banco com dados válidos
    async with db_session_factory() as session:
        tenant = Tenant(
            id=tenant_id,
            nome="Real Redis Tenant",
            cnpj="88776655000144",
            email="rr@test.com",
            ativo=True,
        )
        user = Usuario(
            id=user_id,
            tenant_id=tenant_id,
            nome="Real Redis User",
            email="realredis@test.com",
            cpf="98765432100",
            matricula="RR001",
            password_hash=hash_password(original_password),
            papel=UserRole.COLABORADOR,
            status=UserStatus.ACTIVE,
        )
        session.add(tenant)
        session.add(user)
        await session.commit()

    # Configurar dependency overrides
    async def override_get_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: redis_client_obj
    app.dependency_overrides[auth_rate_limit] = lambda: None

    try:
        with patch("app.core.email.email_service.send_password_reset", return_value=True):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                # --- Passo 1: Emitir token de reset ---
                res_req = await client.post("/api/v1/auth/password/reset", json={"email": "realredis@test.com"})
                assert res_req.status_code == 200, res_req.text

                # Recuperar token gravado no Redis real
                keys = await raw_redis.keys("password_reset:*")
                assert len(keys) == 1, "Token de reset deveria ter sido gravado no Redis"
                captured_token = keys[0].split("password_reset:")[1]

                # Simular criação de sessão ativa para testar revogação no final
                session_key = f"session:{user_id}:test_session_1"
                await raw_redis.set(session_key, "active_session_data")

                # --- Passo 2: Verificar token via POST /auth/password/reset/verify ---
                res_v1 = await client.post("/api/v1/auth/password/reset/verify", json={"token": captured_token})
                assert res_v1.status_code == 200
                assert res_v1.json()["message"] == "Token válido"

                # --- Passo 3: Confirmar que o token CONTINUA no Redis real (operação PEEK não destrutiva) ---
                val_after_verify = await raw_redis.get(f"password_reset:{captured_token}")
                assert val_after_verify == str(user_id), "PEEK não pode consumir o token!"

                # --- Passo 4: Confirmar a redefinição de senha ---
                res_conf = await client.post("/api/v1/auth/password/reset/confirm", json={
                    "token": captured_token,
                    "new_password": new_password,
                    "confirm_password": new_password,
                })
                assert res_conf.status_code == 200
                assert res_conf.json()["message"] == "Senha redefinida com sucesso"

                # --- Passo 5: Verificar que a senha foi alterada no banco ---
                async with db_session_factory() as session:
                    user_db = await session.scalar(select(Usuario).where(Usuario.id == user_id))
                    assert verify_password(new_password, user_db.password_hash)
                    assert not verify_password(original_password, user_db.password_hash)

                # --- Passo 6: Verificar que o token foi consumido (GETDEL) ---
                val_after_confirm = await raw_redis.get(f"password_reset:{captured_token}")
                assert val_after_confirm is None, "Token deveria ter sido consumido (GETDEL) após confirmação"

                # --- Passo 7: Tentar reutilizar o token -> Operação Negada (400) ---
                res_reuse = await client.post("/api/v1/auth/password/reset/confirm", json={
                    "token": captured_token,
                    "new_password": "ThirdPassword123!",
                    "confirm_password": "ThirdPassword123!",
                })
                assert res_reuse.status_code == 400
                assert "Token inválido ou expirado" in res_reuse.json()["detail"]

                # --- Passo 8: Confirmar revogação das sessões ---
                session_val = await raw_redis.get(session_key)
                assert session_val is None, "Sessão ativa deveria ter sido revogada"
    finally:
        await raw_redis.flushdb()
        await redis_pool.disconnect()
        RedisClient._instance = None
        RedisClient._pool = None
        app.dependency_overrides.clear()
