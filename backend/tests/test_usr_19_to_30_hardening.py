"""
Testes unitários e de regressão para os achados USR-19 a USR-26 da Micro-Sprint 02C.1.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4
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
    def __init__(self, equipe_id, tenant_id, lider_id, nome="Equipe Test", ativa=True):
        now = datetime.now(timezone.utc)
        self.id = equipe_id
        self.tenant_id = tenant_id
        self.lider_id = lider_id
        self.nome = nome
        self.descricao = "Desc"
        self.config = {}
        self.ativa = ativa
        self.membros = []
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
async def test_usr19_gestor_patch_user_pii_sanitized():
    """USR-19: PATCH /usuarios/{id} por Gestor não vaza CPF, MFA, telefone ou ultimo_login."""
    tenant_id = uuid4()
    gestor_id = uuid4()
    colab_id = uuid4()
    equipe_id = uuid4()

    gestor = MockUser(gestor_id, tenant_id, UserRole.GESTOR, equipe_id=equipe_id, nome="Gestor User")
    target_colab = MockUser(colab_id, tenant_id, UserRole.COLABORADOR, equipe_id=equipe_id, nome="Colab Target", cpf="52998224725")
    equipe = MockEquipe(equipe_id, tenant_id, lider_id=gestor_id)

    async def override_tenant():
        return MockTenantContext(tenant_id)

    async def fake_execute(statement, *args, **kwargs):
        stmt_str = str(statement).lower()
        if "from equipes" in stmt_str or "into equipes" in stmt_str:
            return FakeResult([equipe], scalar_val=equipe)
        return FakeResult([target_colab], scalar_val=target_colab)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        yield db

    app.dependency_overrides[get_tenant_context] = override_tenant
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: gestor

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.patch(f"/api/v1/usuarios/{colab_id}", json={"nome": "Colab Target Updated"})
        assert res.status_code == 200
        body = res.json()
        assert body["nome"] == "Colab Target"
        assert "cpf" not in body
        assert "mfa_enabled" not in body
        assert "telefone" not in body
        assert "ultimo_login" not in body

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_usr20_gestor_cannot_edit_non_collaborator():
    """USR-20: Gestor não pode editar outro Gestor ou Admin."""
    tenant_id = uuid4()
    gestor_id = uuid4()
    target_gestor_id = uuid4()
    equipe_id = uuid4()

    gestor = MockUser(gestor_id, tenant_id, UserRole.GESTOR, equipe_id=equipe_id, nome="Gestor 1")
    target_gestor = MockUser(target_gestor_id, tenant_id, UserRole.GESTOR, equipe_id=equipe_id, nome="Gestor 2")

    async def override_tenant():
        return MockTenantContext(tenant_id)

    async def fake_execute(statement, *args, **kwargs):
        return FakeResult([target_gestor], scalar_val=target_gestor)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        yield db

    app.dependency_overrides[get_tenant_context] = override_tenant
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: gestor

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.patch(f"/api/v1/usuarios/{target_gestor_id}", json={"nome": "Tentativa"})
        assert res.status_code == 403
        assert "Gestor só pode editar colaboradores" in res.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_usr21_gestor_cannot_change_lider_id():
    """USR-21: Gestor tentando alterar lider_id (inclusive null) recebe 403 Forbidden."""
    tenant_id = uuid4()
    gestor_id = uuid4()
    equipe_id = uuid4()

    gestor = MockUser(gestor_id, tenant_id, UserRole.GESTOR, equipe_id=equipe_id)
    equipe = MockEquipe(equipe_id, tenant_id, lider_id=gestor_id)

    async def override_tenant():
        return MockTenantContext(tenant_id)

    async def fake_execute(statement, *args, **kwargs):
        return FakeResult([equipe], scalar_val=equipe)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        yield db

    app.dependency_overrides[get_tenant_context] = override_tenant
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: gestor

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.patch(f"/api/v1/equipes/{equipe_id}", json={"lider_id": None})
        assert res.status_code == 403
        assert "Apenas Admin pode alterar a liderança" in res.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_usr22_leader_eligibility_validation():
    """USR-22: Admin tentando definir colaborador comum ou usuário inativo como líder recebe 400 Bad Request."""
    tenant_id = uuid4()
    admin_id = uuid4()
    colab_id = uuid4()

    admin = MockUser(admin_id, tenant_id, UserRole.ADMIN_DP)
    colab = MockUser(colab_id, tenant_id, UserRole.COLABORADOR, status=UserStatus.ACTIVE)

    async def override_tenant():
        return MockTenantContext(tenant_id)

    async def fake_execute(statement, *args, **kwargs):
        return FakeResult([colab], scalar_val=colab)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        yield db

    app.dependency_overrides[get_tenant_context] = override_tenant
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/v1/equipes", json={"nome": "Nova Equipe", "lider_id": str(colab_id)})
        assert res.status_code == 400
        assert "Líder inelegível ou de outro tenant" in res.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_usr23_24_get_equipe_members_sanitized():
    """USR-23/24: GET /equipes/{id} por colaborador comum retorna membros minimizados sem email/matricula."""
    tenant_id = uuid4()
    colab_id = uuid4()
    equipe_id = uuid4()
    lider_id = uuid4()

    colab = MockUser(colab_id, tenant_id, UserRole.COLABORADOR, equipe_id=equipe_id)
    membro = MockUser(uuid4(), tenant_id, UserRole.COLABORADOR, equipe_id=equipe_id, nome="Membro Equipe")
    equipe = MockEquipe(equipe_id, tenant_id, lider_id=lider_id)
    equipe.membros = [membro]

    async def override_tenant():
        return MockTenantContext(tenant_id)

    async def fake_execute(statement, *args, **kwargs):
        return FakeResult([equipe], scalar_val=equipe)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        yield db

    app.dependency_overrides[get_tenant_context] = override_tenant
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: colab

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/v1/equipes/{equipe_id}")
        assert res.status_code == 200
        membros = res.json()["membros"]
        assert len(membros) == 1
        assert membros[0]["nome"] == "Membro Equipe"
        assert "email" not in membros[0]
        assert "matricula" not in membros[0]
        assert "cpf" not in membros[0]

    app.dependency_overrides.clear()
