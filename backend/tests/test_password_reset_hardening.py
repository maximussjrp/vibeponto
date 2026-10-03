"""Testes de endurecimento do reset de senha (USR-34, USR-37, USR-38)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest

from app.api.deps import get_current_user, get_db, get_tenant_context
from app.core.rate_limit import auth_rate_limit
from app.core.redis import get_redis
from app.core.security import credential_fingerprint, hash_password
from app.main import app
from app.models.models import UserRole, UserStatus
from app.services.password_reset import PasswordResetEmailError, execute_password_reset_request


class MockUser:
    def __init__(self, user_id, tenant_id, papel, email="target@reset.com", nome="Reset Target"):
        now = datetime.now(timezone.utc)
        self.id = user_id
        self.tenant_id = tenant_id
        self.papel = papel
        self.equipe_id = None
        self.status = UserStatus.ACTIVE
        self.nome = nome
        self.email = email
        self.matricula = "RST001"
        self.cpf = "52998224725"
        self.telefone = None
        self.mfa_enabled = False
        self.foto_base_url = None
        self.ultimo_login = None
        self.created_at = now
        self.updated_at = now
        self.password_hash = hash_password("OldPassword123!")


class MockTenantContext:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id


class FakeResult:
    def __init__(self, items, scalar_val=None, rowcount=1):
        self._items = items
        self._scalar_val = scalar_val
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self._scalar_val

    def scalars(self):
        class FakeList:
            def __init__(self, data):
                self._data = data
            def all(self):
                return self._data
        return FakeList(self._items)


@pytest.fixture(autouse=True)
def override_rate_limit():
    app.dependency_overrides[auth_rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(auth_rate_limit, None)


@pytest.mark.asyncio
async def test_execute_password_reset_request_invalidates_token_on_failure():
    """USR-34: Helper unificado invalida o token no Redis se o e-mail falhar."""
    user_id = uuid4()
    mock_redis = AsyncMock()
    mock_redis.store_password_reset_token = AsyncMock()
    mock_redis.invalidate_password_reset_token = AsyncMock()

    with patch("app.services.password_reset.get_redis", return_value=mock_redis):
        # 1. Falha retornando False
        with patch("app.core.email.email_service.send_password_reset", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = False
            with pytest.raises(PasswordResetEmailError) as exc_info:
                await execute_password_reset_request(user_id, "test@example.com", "Test User")

            assert "Falha ao enviar e-mail" in str(exc_info.value)
            mock_redis.invalidate_password_reset_token.assert_called_once()

        mock_redis.invalidate_password_reset_token.reset_mock()

        # 2. Exceção no serviço de e-mail
        with patch("app.core.email.email_service.send_password_reset", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = Exception("SMTP server offline")
            with pytest.raises(PasswordResetEmailError) as exc_info:
                await execute_password_reset_request(user_id, "test@example.com", "Test User")

            assert "Serviço de e-mail indisponível" in str(exc_info.value)
            mock_redis.invalidate_password_reset_token.assert_called_once()


@pytest.mark.asyncio
async def test_public_password_reset_route_hides_email_failure():
    """USR-34: Rota pública POST /auth/password/reset retorna 200 genérico mesmo em falha de e-mail."""
    tenant_id = uuid4()
    user_id = uuid4()
    target_user = MockUser(user_id, tenant_id, UserRole.COLABORADOR)

    async def fake_execute(stmt, *args, **kwargs):
        return FakeResult([target_user], scalar_val=target_user)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        yield db

    app.dependency_overrides[get_db] = override_db

    with patch("app.api.routes.auth.execute_password_reset_request", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = PasswordResetEmailError("Falha ao enviar e-mail")

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/v1/auth/password/reset", json={"email": "target@reset.com"})
            assert res.status_code == 200
            assert "link de recuperação" in res.json()["message"]

    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_admin_password_reset_route_reports_502_error():
    """USR-34: Rota administrativa POST /usuarios/{id}/reset-password retorna 502 explícito ao Admin em falha."""
    tenant_id = uuid4()
    admin_id = uuid4()
    target_user_id = uuid4()

    admin = MockUser(admin_id, tenant_id, UserRole.ADMIN_DP)
    target_user = MockUser(target_user_id, tenant_id, UserRole.COLABORADOR)

    async def override_tenant():
        return MockTenantContext(tenant_id)

    async def fake_execute(stmt, *args, **kwargs):
        return FakeResult([target_user], scalar_val=target_user)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        yield db

    app.dependency_overrides[get_tenant_context] = override_tenant
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin

    with patch("app.api.routes.usuarios.execute_password_reset_request", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = PasswordResetEmailError("Falha ao enviar e-mail de recuperação de senha")

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(f"/api/v1/usuarios/{target_user_id}/reset-password")
            assert res.status_code == 502
            assert "Falha ao enviar e-mail" in res.json()["detail"]

    app.dependency_overrides.pop(get_tenant_context, None)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_verify_password_reset_token_endpoint():
    """USR-38 / USR-39: POST /auth/password/reset/verify valida a existência do token no Redis sem consumi-lo."""
    mock_redis = AsyncMock()

    async def fake_peek_user(token):
        if token == "valid_token_123":
            return str(uuid4())
        return None

    mock_redis.peek_password_reset_user = AsyncMock(side_effect=fake_peek_user)

    app.dependency_overrides[get_redis] = lambda: mock_redis

    try:
        with patch("app.core.redis.get_redis", return_value=mock_redis):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                # 1. Token válido -> 200 OK via POST no body
                res_valid = await client.post("/api/v1/auth/password/reset/verify", json={"token": "valid_token_123"})
                assert res_valid.status_code == 200
                assert res_valid.json()["message"] == "Token válido"

                # 2. Token inválido -> 400 Bad Request
                res_invalid = await client.post("/api/v1/auth/password/reset/verify", json={"token": "invalid_token_999"})
                assert res_invalid.status_code == 400
                assert "Token inválido ou expirado" in res_invalid.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_confirm_password_reset_updates_password_and_invalidates():
    """USR-43 / USR-44: confirmação atualiza a senha, finaliza com posse da trava e revoga sessões."""
    tenant_id = uuid4()
    user_id = uuid4()
    user = MockUser(user_id, tenant_id, UserRole.COLABORADOR)

    mock_redis = AsyncMock()
    mock_redis.reserve_password_reset_token = AsyncMock(
        return_value=(str(user_id), "mock_lock_id", credential_fingerprint(user.password_hash))
    )
    mock_redis.finalize_password_reset = AsyncMock(return_value=True)
    mock_redis.revoke_all_user_sessions = AsyncMock(return_value=1)

    async def fake_execute(stmt, *args, **kwargs):
        return FakeResult([user], scalar_val=user, rowcount=1)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        db.commit = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: mock_redis

    try:
        with patch("app.core.redis.get_redis", return_value=mock_redis):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                res = await client.post("/api/v1/auth/password/reset/confirm", json={
                    "token": "valid_reset_token",
                    "new_password": "NewSecurePassword123!",
                    "confirm_password": "NewSecurePassword123!",
                })
                assert res.status_code == 200
                body = res.json()
                assert body["message"] == "Senha redefinida com sucesso"
                assert body["password_changed"] is True
                assert body["sessions_revoked"] is True
                assert body["session_revocation_pending"] is False

                mock_redis.reserve_password_reset_token.assert_called_once_with("valid_reset_token")
                mock_redis.finalize_password_reset.assert_called_once_with("valid_reset_token", "mock_lock_id")
                mock_redis.revoke_all_user_sessions.assert_awaited_once_with(str(user_id))
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_confirm_password_reset_conditional_update_zero_rows_is_rejected_without_commit():
    """USR-43: credencial já alterada (rowcount=0) -> 400, rollback, nenhum commit, token descartado."""
    user_id = uuid4()
    mock_redis = AsyncMock()
    mock_redis.reserve_password_reset_token = AsyncMock(return_value=(str(user_id), "lock", "stale-fp"))
    mock_redis.finalize_password_reset = AsyncMock(return_value=True)
    mock_redis.revoke_all_user_sessions = AsyncMock()
    db = AsyncMock()
    db.execute = AsyncMock(return_value=FakeResult([], rowcount=0))

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/v1/auth/password/reset/confirm", json={
                "token": "t", "new_password": "NewSecurePassword123!", "confirm_password": "NewSecurePassword123!",
            })
        assert res.status_code == 400
        assert "já utilizado" in res.json()["detail"]
        db.commit.assert_not_awaited()
        db.rollback.assert_awaited()
        mock_redis.finalize_password_reset.assert_awaited_once_with("t", "lock")
        mock_redis.revoke_all_user_sessions.assert_not_awaited()
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_confirm_password_reset_rejects_legacy_token_without_fingerprint():
    """USR-43: token sem vínculo com a credencial não chega ao banco."""
    mock_redis = AsyncMock()
    mock_redis.reserve_password_reset_token = AsyncMock(return_value=(str(uuid4()), "lock", None))
    mock_redis.finalize_password_reset = AsyncMock(return_value=True)
    db = AsyncMock()

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/v1/auth/password/reset/confirm", json={
                "token": "legacy", "new_password": "NewSecurePassword123!", "confirm_password": "NewSecurePassword123!",
            })
        assert res.status_code == 400
        db.execute.assert_not_awaited()
        db.commit.assert_not_awaited()
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_redis, None)
