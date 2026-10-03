"""
Testes para regras do Gestor, PII por papel e rejeição de PENDING.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4, UUID
import httpx
import pytest
from app.api.deps import get_db, get_tenant_context, get_current_user
from app.main import app
from app.models.models import UserRole, UserStatus
from app.core.security import hash_password


class MockUser:
    def __init__(self, user_id, tenant_id, papel, equipe_id=None, nome="Test User", status=UserStatus.ACTIVE, cpf="52998224725"):
        now = datetime.now(timezone.utc)
        self.id = user_id
        self.tenant_id = tenant_id
        self.papel = papel
        self.equipe_id = equipe_id
        self.status = status
        self.nome = nome
        self.email = f"{nome.lower().replace(' ', '')}@test.com"
        self.matricula = "123"
        self.cpf = cpf
        self.telefone = "11999999999"
        self.password_hash = hash_password("Password@123")
        self.mfa_enabled = False
        self.foto_base_url = None
        self.ultimo_login = None
        self.created_at = now
        self.updated_at = now


class MockEquipe:
    def __init__(self, equipe_id, tenant_id, lider_id, nome="Equipe Test"):
        now = datetime.now(timezone.utc)
        self.id = equipe_id
        self.tenant_id = tenant_id
        self.lider_id = lider_id
        self.nome = nome
        self.descricao = "Desc"
        self.config = {}
        self.ativa = True
        self.created_at = now
        self.updated_at = now


class MockTenantContext:
    def __init__(self, tenant_id):
        self.tenant_id = tenant_id


class FakeScalarList:
    def __init__(self, items):
        self._items = items
    def all(self):
        return self._items


class FakeResult:
    def __init__(self, items, scalar_val=None):
        self._items = items
        self._scalar_val = scalar_val

    def scalar_one_or_none(self):
        return self._scalar_val

    def scalar_one(self):
        return len(self._items)

    def scalars(self):
        return FakeScalarList(self._items)


@pytest.mark.asyncio
async def test_pii_minimization_by_role():
    tenant_id = uuid4()
    u_id = uuid4()
    user = MockUser(u_id, tenant_id, UserRole.COLABORADOR, cpf="52998224725")

    async def override_tenant():
        return MockTenantContext(tenant_id)

    async def fake_execute(statement, *args, **kwargs):
        return FakeResult([user], scalar_val=user)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        yield db

    app.dependency_overrides[get_tenant_context] = override_tenant
    app.dependency_overrides[get_db] = override_db

    # 1. Auditor view -> masked CPF
    auditor = MockUser(uuid4(), tenant_id, UserRole.AUDITOR)
    app.dependency_overrides[get_current_user] = lambda: auditor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/v1/usuarios/{u_id}")
        assert res.status_code == 200
        data = res.json()
        assert "cpf" in data
        assert data["cpf"].startswith("***.***.")

    # 2. Gestor view -> no CPF
    gestor = MockUser(uuid4(), tenant_id, UserRole.GESTOR)
    app.dependency_overrides[get_current_user] = lambda: gestor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/v1/usuarios/{u_id}")
        assert res.status_code == 200
        data = res.json()
        assert "cpf" not in data

    # 3. Colaborador view -> minimal (no cpf, no telefone)
    colab = MockUser(u_id, tenant_id, UserRole.COLABORADOR)
    app.dependency_overrides[get_current_user] = lambda: colab
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/v1/usuarios/{u_id}")
        assert res.status_code == 200
        data = res.json()
        assert "cpf" not in data
        assert "telefone" not in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_pending_user_rejected():
    tenant_id = uuid4()
    user_pending = MockUser(uuid4(), tenant_id, UserRole.COLABORADOR, status=UserStatus.PENDING, nome="PendingUser")

    async def fake_execute(statement, *args, **kwargs):
        return FakeResult([user_pending], scalar_val=user_pending)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        yield db

    from app.core.rate_limit import auth_rate_limit
    app.dependency_overrides[auth_rate_limit] = lambda: None
    app.dependency_overrides[get_db] = override_db

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/v1/auth/login", json={
            "email": "pendinguser@test.com",
            "password": "Password@123"
        })
        assert res.status_code == 403
        assert "Cadastro pendente de ativação." in res.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gestor_team_scope_validation():
    tenant_id = uuid4()
    gestor_id = uuid4()
    other_gestor_id = uuid4()

    eq1_id = uuid4() # led by gestor_id
    eq2_id = uuid4() # led by other_gestor_id

    gestor = MockUser(gestor_id, tenant_id, UserRole.GESTOR, equipe_id=eq1_id, nome="Gestor1")
    eq1 = MockEquipe(eq1_id, tenant_id, lider_id=gestor_id, nome="Equipe 1")
    eq2 = MockEquipe(eq2_id, tenant_id, lider_id=other_gestor_id, nome="Equipe 2")

    u_other_team = MockUser(uuid4(), tenant_id, UserRole.COLABORADOR, equipe_id=eq2_id, nome="UserOtherTeam")

    async def override_tenant():
        return MockTenantContext(tenant_id)

    async def override_user():
        return gestor

    async def fake_execute(statement, *args, **kwargs):
        compiled = str(statement).lower()
        params = getattr(statement, "compile", lambda: None)()
        param_dict = getattr(params, "params", {}) if params else {}
        target_id = param_dict.get("id_1") or param_dict.get("id")

        if "from equipes" in compiled:
            if target_id and UUID(str(target_id)) == eq2_id:
                return FakeResult([eq2], scalar_val=eq2)
            return FakeResult([eq1], scalar_val=eq1)

        return FakeResult([u_other_team], scalar_val=u_other_team)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tenant_context] = override_tenant
    app.dependency_overrides[get_db] = override_db

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Gestor trying to update user in unmanaged team (eq2) -> 403 Forbidden
        res = await client.patch(f"/api/v1/usuarios/{u_other_team.id}", json={"nome": "Novo Nome"})
        assert res.status_code == 403
        assert "Gestor só pode alterar usuários de sua própria equipe" in res.json()["detail"]

    app.dependency_overrides.clear()
