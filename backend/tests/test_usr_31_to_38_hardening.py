"""
Testes unitários e de regressão para os achados USR-31 a USR-38 da Micro-Sprint 02C.2.
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
async def test_usr31_openapi_patch_response_schema():
    """USR-31: OpenAPI documenta UsuarioReadOperacional (sem CPF/MFA) em PATCH /usuarios/{id}."""
    openapi_schema = app.openapi()
    patch_route = openapi_schema["paths"]["/api/v1/usuarios/{usuario_id}"]["patch"]
    resp_200_ref = patch_route["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert "UsuarioReadOperacional" in resp_200_ref

    # Verify UsuarioReadOperacional schema definition has no cpf or mfa_enabled
    schema_def = openapi_schema["components"]["schemas"]["UsuarioReadOperacional"]
    properties = schema_def["properties"]
    assert "cpf" not in properties
    assert "mfa_enabled" not in properties


@pytest.mark.asyncio
async def test_usr32_gestor_member_management_collaborators_only():
    """USR-32: Gestor tentando adicionar/remover Gestor ou Admin da equipe recebe 403 Forbidden."""
    tenant_id = uuid4()
    gestor_id = uuid4()
    equipe_id = uuid4()
    target_gestor_id = uuid4()

    gestor = MockUser(gestor_id, tenant_id, UserRole.GESTOR, equipe_id=equipe_id)
    target_gestor = MockUser(target_gestor_id, tenant_id, UserRole.GESTOR)
    equipe = MockEquipe(equipe_id, tenant_id, lider_id=gestor_id)

    async def override_tenant():
        return MockTenantContext(tenant_id)

    async def fake_execute(statement, *args, **kwargs):
        stmt_str = str(statement).lower()
        if "from equipes" in stmt_str:
            return FakeResult([equipe], scalar_val=equipe)
        return FakeResult([target_gestor], scalar_val=target_gestor)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        yield db

    app.dependency_overrides[get_tenant_context] = override_tenant
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: gestor

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/v1/equipes/{equipe_id}/membros/{target_gestor_id}")
        assert res.status_code == 403
        assert "Gestor só pode gerenciar colaboradores" in res.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_usr33_collaborator_cannot_view_other_equipe_members():
    """USR-33: Colaborador tentando consultar membros de equipe fora do escopo recebe 403 Forbidden."""
    tenant_id = uuid4()
    colab_id = uuid4()
    my_equipe_id = uuid4()
    other_equipe_id = uuid4()

    colab = MockUser(colab_id, tenant_id, UserRole.COLABORADOR, equipe_id=my_equipe_id)
    other_equipe = MockEquipe(other_equipe_id, tenant_id, lider_id=uuid4())

    async def override_tenant():
        return MockTenantContext(tenant_id)

    async def fake_execute(statement, *args, **kwargs):
        return FakeResult([other_equipe], scalar_val=other_equipe)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        yield db

    app.dependency_overrides[get_tenant_context] = override_tenant
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: colab

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/v1/equipes/{other_equipe_id}")
        assert res.status_code == 403
        assert "Acesso negado a membros de outras equipes" in res.json()["detail"]

    app.dependency_overrides.clear()
