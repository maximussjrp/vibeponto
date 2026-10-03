"""Testes de integração com PostgreSQL e Redis reais protegidos contra ambientes não autorizados (OPS-04, USR-43)."""

import asyncio
import os
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest
import redis.asyncio as aioredis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.core.config import settings
from app.core.database import Base
from app.core.rate_limit import auth_rate_limit
from app.core.redis import RedisClient, get_redis, redis_client
from app.core.security import hash_password, verify_password
from app.main import app
from app.models import Tenant, UserRole, UserStatus, Usuario

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:54399/test_vibeponto"
)
TEST_REDIS_URL = os.getenv(
    "TEST_REDIS_URL",
    "redis://localhost:56379/0"
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


from tests.destructive_guard import (
    UnsafeTestEnvironment,
    destructive_testing_allowed,
    verify_disposable_environment,
)


def assert_safe_test_environment() -> None:
    """
    OPS-04: Valida estritamente se os alvos de teste são ambientes dedicados e descartáveis.
    Aborta com pytest.skip antes de executar qualquer DROP SCHEMA ou FLUSHDB.
    """
    if not destructive_testing_allowed(os.environ):
        pytest.skip("OPS-04: Testes destrutivos desativados via ALLOW_DESTRUCTIVE_TESTING (padrão: false).")

    try:
        asyncio.run(verify_disposable_environment(TEST_DATABASE_URL, TEST_REDIS_URL, os.environ))
    except UnsafeTestEnvironment as exc:
        pytest.skip(f"OPS-04: Ambiente de teste não seguro ou não autorizado: {exc}")
    except Exception as exc:
        pytest.skip(f"OPS-04: Erro ao verificar ambiente de teste: {exc}")


@pytest.fixture(autouse=True)
def configure_test_settings(monkeypatch):
    """
    OPS-04: Altera configurações do sistema somente no escopo de execução do teste (via monkeypatch),
    sem produzir efeitos colaterais globais na importação do módulo.
    """
    assert_safe_test_environment()
    monkeypatch.setattr(settings, "redis_url", TEST_REDIS_URL)
    monkeypatch.setattr(settings, "database_url", TEST_DATABASE_URL)


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


@pytest.fixture
async def raw_redis():
    """
    Conexão Redis separada exclusivamente para asserções e limpeza nos testes.
    NÃO é usada pela aplicação; a app cria seu próprio pool via get_redis().
    """
    pool = aioredis.ConnectionPool.from_url(TEST_REDIS_URL, decode_responses=True)
    client = aioredis.Redis(connection_pool=pool)
    env_id = os.getenv("VIBEPONTO_DISPOSABLE_ENV_ID")
    await client.flushdb()
    if env_id:
        await client.set("__vibeponto_disposable_test_env__", env_id)
    try:
        yield client
    finally:
        await client.flushdb()
        if env_id:
            await client.set("__vibeponto_disposable_test_env__", env_id)
        await pool.disconnect()


@pytest.fixture(autouse=True)
async def _reset_redis_singleton():
    """
    Reseta o singleton RedisClient antes e depois de cada teste para garantir
    que a aplicação crie um pool fresco dentro do contexto ASGI.
    """
    # Antes do teste: limpar qualquer pool anterior
    if redis_client._pool is not None:
        try:
            await redis_client._pool.disconnect()
        except Exception:
            pass
    redis_client._pool = None
    if hasattr(redis_client, "_bound_loop"):
        delattr(redis_client, "_bound_loop")

    yield

    # Depois do teste: limpar novamente
    if redis_client._pool is not None:
        try:
            await redis_client._pool.disconnect()
        except Exception:
            pass
    redis_client._pool = None
    if hasattr(redis_client, "_bound_loop"):
        delattr(redis_client, "_bound_loop")


async def test_full_password_reset_flow_with_real_redis(db_session_factory, raw_redis):
    """
    USR-39 / USR-43: Sequência completa de reset de senha com Redis e PostgreSQL reais.
    """
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

    async def override_get_db():
        async with db_session_factory() as session:
            yield session

    # NÃO sobrescrever get_redis: deixar a app criar o pool dentro do contexto ASGI
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[auth_rate_limit] = lambda: None

    try:
        with patch("app.core.email.email_service.send_password_reset", return_value=True):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                # 1. Emitir token de reset
                res_req = await client.post("/api/v1/auth/password/reset", json={"email": "realredis@test.com"})
                assert res_req.status_code == 200, res_req.text

                # Recuperar token do Redis real (via raw_redis separado)
                keys = await raw_redis.keys("password_reset:*")
                assert len(keys) == 1, "Token de reset deveria ter sido gravado no Redis"
                captured_token = keys[0].split("password_reset:")[1]

                # Simular sessão ativa (via raw_redis separado)
                session_key = f"session:{user_id}:test_session_1"
                await raw_redis.set(session_key, "active_session_data")

                # 2. Verificar token via POST /auth/password/reset/verify
                res_v1 = await client.post("/api/v1/auth/password/reset/verify", json={"token": captured_token})
                assert res_v1.status_code == 200
                assert res_v1.json()["message"] == "Token válido"

                # 3. Confirmar que o token CONTINUA no Redis (PEEK não destrutivo)
                val_after_verify = await raw_redis.get(f"password_reset:{captured_token}")
                user_id_in_redis, fingerprint_in_redis = RedisClient._parse_password_reset_data(val_after_verify)
                assert user_id_in_redis == str(user_id), "PEEK não pode consumir o token!"
                assert fingerprint_in_redis is not None, "Token deve conter o fingerprint da credencial na emissão"

                # 4. Confirmar a redefinição de senha
                res_conf = await client.post("/api/v1/auth/password/reset/confirm", json={
                    "token": captured_token,
                    "new_password": new_password,
                    "confirm_password": new_password,
                })
                assert res_conf.status_code == 200
                assert res_conf.json()["message"] == "Senha redefinida com sucesso"

                # 5. Verificar que a senha foi alterada no banco
                async with db_session_factory() as session:
                    user_db = await session.scalar(select(Usuario).where(Usuario.id == user_id))
                    assert verify_password(new_password, user_db.password_hash)
                    assert not verify_password(original_password, user_db.password_hash)

                # 6. Verificar que o token foi consumido (GETDEL)
                val_after_confirm = await raw_redis.get(f"password_reset:{captured_token}")
                assert val_after_confirm is None, "Token deveria ter sido consumido após confirmação"

                # 7. Tentar reutilizar o token -> Negado (400)
                res_reuse = await client.post("/api/v1/auth/password/reset/confirm", json={
                    "token": captured_token,
                    "new_password": "ThirdPassword123!",
                    "confirm_password": "ThirdPassword123!",
                })
                assert res_reuse.status_code == 400
                assert "Token inválido" in res_reuse.json()["detail"] or "expirado" in res_reuse.json()["detail"]

                # 8. Confirmar revogação de sessões
                session_val = await raw_redis.get(session_key)
                assert session_val is None, "Sessão ativa deveria ter sido revogada"
    finally:
        app.dependency_overrides.clear()


async def test_concurrent_password_reset_confirmations_with_real_redis(db_session_factory, raw_redis):
    """
    USR-43: Duas confirmações simultâneas com o mesmo token e senhas diferentes.
    Garante exclusividade atômica (apenas uma requisição é processada com sucesso; a outra é rejeitada).
    """
    tenant_id = uuid4()
    user_id = uuid4()
    original_pass = "OldPassword123!"
    password_alpha = "PasswordAlpha123!"
    password_beta = "PasswordBeta456!"

    async with db_session_factory() as session:
        tenant = Tenant(
            id=tenant_id,
            nome="Concurrent Tenant",
            cnpj="77665544000133",
            email="conc@test.com",
            ativo=True,
        )
        user = Usuario(
            id=user_id,
            tenant_id=tenant_id,
            nome="Concurrent User",
            email="concurrent@test.com",
            cpf="87654321009",
            matricula="CONC001",
            password_hash=hash_password(original_pass),
            papel=UserRole.COLABORADOR,
            status=UserStatus.ACTIVE,
        )
        session.add(tenant)
        session.add(user)
        await session.commit()

    async def override_get_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[auth_rate_limit] = lambda: None

    try:
        with patch("app.core.email.email_service.send_password_reset", return_value=True):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                # Emitir token
                res_req = await client.post("/api/v1/auth/password/reset", json={"email": "concurrent@test.com"})
                assert res_req.status_code == 200

                keys = await raw_redis.keys("password_reset:*")
                captured_token = keys[0].split("password_reset:")[1]

                # Executar duas confirmações simultâneas via asyncio.gather
                req_a = client.post("/api/v1/auth/password/reset/confirm", json={
                    "token": captured_token,
                    "new_password": password_alpha,
                    "confirm_password": password_alpha,
                })
                req_b = client.post("/api/v1/auth/password/reset/confirm", json={
                    "token": captured_token,
                    "new_password": password_beta,
                    "confirm_password": password_beta,
                })

                res_a, res_b = await asyncio.gather(req_a, req_b)

                statuses = sorted([res_a.status_code, res_b.status_code])
                assert statuses == [200, 400], f"Esperado um 200 e um 400 sob concorrência, obteve: {statuses}"

                # Confirmar qual requisição venceu no banco
                async with db_session_factory() as session:
                    user_db = await session.scalar(select(Usuario).where(Usuario.id == user_id))
                    alpha_match = verify_password(password_alpha, user_db.password_hash)
                    beta_match = verify_password(password_beta, user_db.password_hash)

                    # Exatamente uma das duas senhas foi gravada
                    assert (alpha_match and not beta_match) or (beta_match and not alpha_match)

                # Confirmar que o token foi removido do Redis
                val_after = await raw_redis.get(f"password_reset:{captured_token}")
                assert val_after is None
    finally:
        app.dependency_overrides.clear()


async def test_password_reset_db_failure_retains_token_in_redis(db_session_factory, raw_redis):
    """
    USR-43: Em caso de falha no banco durante o commit da nova senha, o token NÃO pode ser consumido no Redis.
    Garante que a trava é liberada e que o usuário pode tentar novamente após o banco se recuperar.
    """
    tenant_id = uuid4()
    user_id = uuid4()
    original_pass = "OldPassword123!"
    new_pass = "RecoverablePassword123!"

    async with db_session_factory() as session:
        tenant = Tenant(
            id=tenant_id,
            nome="Failure Recovery Tenant",
            cnpj="66554433000122",
            email="failrec@test.com",
            ativo=True,
        )
        user = Usuario(
            id=user_id,
            tenant_id=tenant_id,
            nome="Failure User",
            email="failure@test.com",
            cpf="76543210098",
            matricula="FAIL001",
            password_hash=hash_password(original_pass),
            papel=UserRole.COLABORADOR,
            status=UserStatus.ACTIVE,
        )
        session.add(tenant)
        session.add(user)
        await session.commit()

    # Injetar falha de banco simulada no primeiro commit
    async def failing_db_override():
        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(side_effect=RuntimeError("Simulated Database Outage"))
        db_mock.rollback = AsyncMock()
        yield db_mock

    app.dependency_overrides[auth_rate_limit] = lambda: None

    try:
        with patch("app.core.email.email_service.send_password_reset", return_value=True):
            # Primeiro: emitir token com banco normal
            async def normal_db_override():
                async with db_session_factory() as session:
                    yield session

            app.dependency_overrides[get_db] = normal_db_override
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                res_req = await client.post("/api/v1/auth/password/reset", json={"email": "failure@test.com"})
                assert res_req.status_code == 200

                keys = await raw_redis.keys("password_reset:*")
                captured_token = keys[0].split("password_reset:")[1]

                # Agora simular falha de banco durante o confirm
                app.dependency_overrides[get_db] = failing_db_override
                res_fail = await client.post("/api/v1/auth/password/reset/confirm", json={
                    "token": captured_token,
                    "new_password": new_pass,
                    "confirm_password": new_pass,
                })
                assert res_fail.status_code == 500
                assert "Erro ao atualizar a senha no banco" in res_fail.json()["detail"]

                # Verificar que o token CONTINUA no Redis intacto
                token_val_after_fail = await raw_redis.get(f"password_reset:{captured_token}")
                user_id_fail, _ = RedisClient._parse_password_reset_data(token_val_after_fail)
                assert user_id_fail == str(user_id), "Token não pode ser consumido quando o banco falha!"

                # E a trava de concorrência foi liberada
                lock_val = await raw_redis.get(f"password_reset_lock:{captured_token}")
                assert lock_val is None, "Trava de concorrência deve ser liberada após erro no banco"

                # Restaurar banco normal e tentar confirmação novamente -> Sucesso!
                app.dependency_overrides[get_db] = normal_db_override
                res_retry = await client.post("/api/v1/auth/password/reset/confirm", json={
                    "token": captured_token,
                    "new_password": new_pass,
                    "confirm_password": new_pass,
                })
                assert res_retry.status_code == 200
                assert res_retry.json()["message"] == "Senha redefinida com sucesso"

                # Agora sim o token foi consumido
                token_val_after_success = await raw_redis.get(f"password_reset:{captured_token}")
                assert token_val_after_success is None
    finally:
        app.dependency_overrides.clear()
