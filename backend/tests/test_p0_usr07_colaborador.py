"""
Testes HTTP autenticados para P0 USR-07 (Colaborador sem equipe e com equipe).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4, UUID
import httpx
import pytest
from app.api.deps import get_db, get_tenant_context, get_current_user
from app.main import app
from app.models.models import UserRole, UserStatus


class MockUser:
    def __init__(self, user_id, tenant_id, papel, equipe_id=None, nome="Test User"):
        now = datetime.now(timezone.utc)
        self.id = user_id
        self.tenant_id = tenant_id
        self.papel = papel
        self.equipe_id = equipe_id
        self.status = UserStatus.ACTIVE
        self.nome = nome
        self.email = f"{nome.lower().replace(' ', '')}@test.com"
        self.matricula = "123"
        self.cpf = "52998224725"
        self.telefone = None
        self.mfa_enabled = False
        self.foto_base_url = None
        self.ultimo_login = None
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
async def test_colaborador_sem_equipe_scenarios():
    tenant_id = uuid4()
    u1_id = uuid4()
    u2_id = uuid4()
    
    colab_sem_equipe = MockUser(u1_id, tenant_id, UserRole.COLABORADOR, equipe_id=None, nome="Self")
    colab_outro = MockUser(u2_id, tenant_id, UserRole.COLABORADOR, equipe_id=None, nome="Other")
    
    users_by_id = {
        u1_id: colab_sem_equipe,
        u2_id: colab_outro,
    }

    async def override_user():
        return colab_sem_equipe
        
    async def override_tenant():
        return MockTenantContext(tenant_id)

    async def fake_execute(statement, *args, **kwargs):
        compiled = str(statement).lower()
        
        # Count query
        if "count(" in compiled:
            return FakeResult([colab_sem_equipe], scalar_val=1)
            
        # Select single field equipe_id: select(Usuario.equipe_id)
        if "equipe_id" in compiled and "select usuarios.id" not in compiled and "from usuarios" in compiled and "select usuarios.tenant_id" not in compiled:
            return FakeResult([], scalar_val=None)
            
        # Select full Usuario object
        params = getattr(statement, "compile", lambda: None)()
        param_dict = getattr(params, "params", {}) if params else {}
        target_id = param_dict.get("id_1") or param_dict.get("id")
        
        if target_id and UUID(str(target_id)) in users_by_id:
            user_found = users_by_id[UUID(str(target_id))]
            return FakeResult([user_found], scalar_val=user_found)
            
        return FakeResult([colab_sem_equipe], scalar_val=colab_sem_equipe)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tenant_context] = override_tenant
    app.dependency_overrides[get_db] = override_db

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # GET /api/v1/usuarios (list) -> Must return only self
        resp = await client.get("/api/v1/usuarios")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(u1_id)
        
        # GET /api/v1/usuarios/{u1_id} (own profile) -> 200 OK
        resp_self = await client.get(f"/api/v1/usuarios/{u1_id}")
        assert resp_self.status_code == 200
        assert resp_self.json()["id"] == str(u1_id)
        
        # GET /api/v1/usuarios/{u2_id} (other user without team) -> 403 Forbidden
        resp_other = await client.get(f"/api/v1/usuarios/{u2_id}")
        assert resp_other.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_colaborador_com_equipe_scenarios():
    tenant_id = uuid4()
    equipe_id = uuid4()
    outra_equipe_id = uuid4()
    
    u1_id = uuid4()
    u2_id = uuid4()
    u3_id = uuid4()
    
    colab_equipe = MockUser(u1_id, tenant_id, UserRole.COLABORADOR, equipe_id=equipe_id, nome="Colab1")
    colab_colega = MockUser(u2_id, tenant_id, UserRole.COLABORADOR, equipe_id=equipe_id, nome="Teammate")
    colab_outra_equipe = MockUser(u3_id, tenant_id, UserRole.COLABORADOR, equipe_id=outra_equipe_id, nome="OutraEquipe")
    
    users_by_id = {
        u1_id: colab_equipe,
        u2_id: colab_colega,
        u3_id: colab_outra_equipe,
    }

    async def override_user():
        return colab_equipe
        
    async def override_tenant():
        return MockTenantContext(tenant_id)

    async def fake_execute(statement, *args, **kwargs):
        compiled = str(statement).lower()
        
        if "count(" in compiled:
            return FakeResult([colab_equipe, colab_colega], scalar_val=2)
            
        if "equipe_id" in compiled and "select usuarios.id" not in compiled and "from usuarios" in compiled and "select usuarios.tenant_id" not in compiled:
            return FakeResult([], scalar_val=equipe_id)
            
        params = getattr(statement, "compile", lambda: None)()
        param_dict = getattr(params, "params", {}) if params else {}
        target_id = param_dict.get("id_1") or param_dict.get("id")
        
        if target_id and UUID(str(target_id)) in users_by_id:
            user_found = users_by_id[UUID(str(target_id))]
            return FakeResult([user_found], scalar_val=user_found)
            
        return FakeResult([colab_equipe, colab_colega], scalar_val=colab_equipe)

    async def override_db():
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_tenant_context] = override_tenant
    app.dependency_overrides[get_db] = override_db

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # GET /api/v1/usuarios/{u2_id} (teammate) -> 200 OK
        resp_teammate = await client.get(f"/api/v1/usuarios/{u2_id}")
        assert resp_teammate.status_code == 200
        
        # GET /api/v1/usuarios/{u3_id} (other team) -> 403 Forbidden
        resp_other = await client.get(f"/api/v1/usuarios/{u3_id}")
        assert resp_other.status_code == 403

    app.dependency_overrides.clear()
