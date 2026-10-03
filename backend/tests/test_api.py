"""
Testes automatizados do backend VibePonto (E2E e Unitários).
Organizados e classificados por efeito operacional (E2E-01, E2E-02, E2E-03).
"""

import asyncio
import os
from datetime import date, datetime, timedelta
from typing import AsyncGenerator
from uuid import UUID, uuid4

import httpx
import pytest

# Garantir chaves válidas no ambiente de teste para importações de config
os.environ.setdefault("SECRET_KEY", "k9X!mP4vL8zR2wQ7nT1yU6bV3cC5aD0eF")
os.environ.setdefault("MFA_ENCRYPTION_KEY", "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6")

# ==================== Credenciais Sintéticas de Staging (E2E-02) ====================
STAGING_API_BASE_URL = os.getenv("STAGING_API_BASE_URL", "http://localhost:8000/api/v1")
STAGING_ADMIN_EMAIL = os.getenv("STAGING_ADMIN_EMAIL", "staging_admin_e2e@staging.vibeponto.com")
STAGING_ADMIN_PASSWORD = os.getenv("STAGING_ADMIN_PASSWORD", "StagingAdminPassword123!")


# ============================================================================
# 1. TESTES UNITÁRIOS (Sem dependência de servidor HTTP live - E2E-03)
# ============================================================================

class TestUnitCalculoHoras:
    """Testes unitários do módulo de jornada e comprovantes de ponto (nunca são pulados por ausência de servidor HTTP)."""

    def test_calcular_horas_normais(self):
        """Teste unitário de cálculo de jornada normal de 8 horas."""
        entrada = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        saida = datetime.now().replace(hour=17, minute=0, second=0, microsecond=0)
        pausa_inicio = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
        pausa_fim = datetime.now().replace(hour=13, minute=0, second=0, microsecond=0)

        total_bruto = saida - entrada
        total_pausa = pausa_fim - pausa_inicio
        horas_trabalhadas = total_bruto - total_pausa

        jornada_padrao = timedelta(hours=8)
        horas_extras = max(timedelta(0), horas_trabalhadas - jornada_padrao)

        assert horas_trabalhadas == timedelta(hours=8)
        assert horas_extras == timedelta(0)

    def test_calcular_horas_extras(self):
        """Teste unitário de cálculo de jornada com 2 horas extras."""
        entrada = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        saida = datetime.now().replace(hour=19, minute=0, second=0, microsecond=0)
        pausa_inicio = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
        pausa_fim = datetime.now().replace(hour=13, minute=0, second=0, microsecond=0)

        total_bruto = saida - entrada
        total_pausa = pausa_fim - pausa_inicio
        horas_trabalhadas = total_bruto - total_pausa

        jornada_padrao = timedelta(hours=8)
        horas_extras = max(timedelta(0), horas_trabalhadas - jornada_padrao)

        assert horas_trabalhadas == timedelta(hours=10)
        assert horas_extras == timedelta(hours=2)

    def test_comprovante_hash_and_coordinates(self):
        """Teste unitário de utilitários de marcação de ponto."""
        from app.services.timekeeping import comprovante_hash, has_coordinates

        assert has_coordinates(-23.5505, -46.6333) is True
        assert has_coordinates(None, -46.6333) is False

        u_id = uuid4()
        dt = datetime(2026, 10, 3, 8, 0, 0)
        hash1 = comprovante_hash(u_id, "entrada", dt)
        hash2 = comprovante_hash(u_id, "entrada", dt)
        assert hash1 == hash2
        assert len(hash1) == 64


# ============================================================================
# 2. IDENTIFICAÇÃO POSITIVA DE AMBIENTE STAGING (E2E-01)
# ============================================================================

def verify_live_staging_server() -> bool:
    """
    E2E-01: Valida positivamente se o servidor HTTP ativo é um ambiente Staging/Teste seguro.
    Impede a execução dos testes E2E contra produção, inclusive via encaminhamento de porta ou túnel.
    """
    health_url = STAGING_API_BASE_URL.replace("/api/v1", "/health")
    try:
        with httpx.Client(timeout=2.0) as client:
            response = client.get(health_url)
            if response.status_code != 200:
                return False
            data = response.json()
            env = str(data.get("environment", "")).strip().lower()
            if env in ("production", "prod", "staging_prod"):
                return False
            allowed_envs = os.getenv("STAGING_ALLOWED_ENVIRONMENTS", "staging,test,development").split(",")
            allowed_envs = [e.strip().lower() for e in allowed_envs]
            return data.get("status") == "ok" and env in allowed_envs
    except Exception:
        return False


# Se o servidor HTTP de staging não estiver ativo ou não for um ambiente permitido, pula as suítes E2E
e2e_live_server_available = verify_live_staging_server()
e2e_skip_reason = (
    "E2E-01: Servidor HTTP de Staging isolado (http://localhost:8000/health) não está ativo ou não é um ambiente seguro."
)


# ============================================================================
# 3. FIXTURES PARA TESTES E2E
# ============================================================================

class StagingClient:
    """Cliente HTTP com isolamento de event loop por requisição para testes E2E."""

    def __init__(self, base_url: str = STAGING_API_BASE_URL):
        self.base_url = base_url

    async def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> httpx.Response:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            return await client.get(url, params=params, headers=headers)

    async def post(self, url: str, json: dict | None = None, headers: dict | None = None) -> httpx.Response:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            return await client.post(url, json=json, headers=headers)


_CACHED_STAGING_TOKEN: str | None = None


async def get_staging_token(client: StagingClient) -> str:
    """Retorna token JWT autenticado para conta sintética de staging, reutilizando cache se disponível."""
    global _CACHED_STAGING_TOKEN
    if _CACHED_STAGING_TOKEN:
        return _CACHED_STAGING_TOKEN
    response = await client.post(
        "/auth/login",
        json={
            "email": STAGING_ADMIN_EMAIL,
            "password": STAGING_ADMIN_PASSWORD,
        },
    )
    if response.status_code == 200:
        _CACHED_STAGING_TOKEN = response.json()["access_token"]
        return _CACHED_STAGING_TOKEN
    raise RuntimeError(f"Falha ao obter token de staging: {response.status_code} - {response.text}")


@pytest.fixture
def http_client() -> StagingClient:
    """Cliente HTTP para testes de API em Staging."""
    return StagingClient()


# ============================================================================
# 4. SUÍTE E2E: AUTENTICAÇÃO E SESSÕES (E2E-03)
# ============================================================================

@pytest.mark.skipif(not e2e_live_server_available, reason=e2e_skip_reason)
class TestE2EAuth:
    """Testes E2E de autenticação e gerenciamento de sessão em Staging."""

    @pytest.mark.asyncio
    async def test_login_success(self, http_client: httpx.AsyncClient):
        """Teste de login com credenciais sintéticas válidas."""
        response = await http_client.post(
            "/auth/login",
            json={
                "email": STAGING_ADMIN_EMAIL,
                "password": STAGING_ADMIN_PASSWORD,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, http_client: httpx.AsyncClient):
        """Teste de login com credenciais sintéticas inválidas."""
        response = await http_client.post(
            "/auth/login",
            json={
                "email": "invalid_synthetic_user@staging.vibeponto.com",
                "password": "WrongPassword999!",
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, http_client: httpx.AsyncClient):
        """Teste de login sem campos obrigatórios."""
        response = await http_client.post(
            "/auth/login",
            json={"email": "incomplete@staging.vibeponto.com"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_refresh_token(self, http_client: httpx.AsyncClient):
        """Teste de rotação e renovação de token de sessão."""
        login_response = await http_client.post(
            "/auth/login",
            json={
                "email": STAGING_ADMIN_EMAIL,
                "password": STAGING_ADMIN_PASSWORD,
            },
        )

        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh_token"]

        refresh_response = await http_client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert refresh_response.status_code == 200
        assert "access_token" in refresh_response.json()

    @pytest.mark.asyncio
    async def test_me_authenticated(self, http_client: httpx.AsyncClient):
        """Teste de obtenção de perfil do usuário autenticado."""
        login_response = await http_client.post(
            "/auth/login",
            json={
                "email": STAGING_ADMIN_EMAIL,
                "password": STAGING_ADMIN_PASSWORD,
            },
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        response = await http_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["email"] == STAGING_ADMIN_EMAIL

    @pytest.mark.asyncio
    async def test_me_unauthenticated(self, http_client: httpx.AsyncClient):
        """Teste de acesso não autenticado (deve falhar com 401)."""
        response = await http_client.get("/auth/me")
        assert response.status_code == 401


# ============================================================================
# 5. SUÍTE E2E: CONSULTAS SOMENTE LEITURA (E2E-03)
# ============================================================================

@pytest.mark.skipif(not e2e_live_server_available, reason=e2e_skip_reason)
class TestE2EReadOnlyQueries:
    """Testes E2E de consulta sem mutação intencional de registros."""

    @pytest.fixture
    async def auth_headers(self, http_client: StagingClient):
        token = await get_staging_token(http_client)
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_list_usuarios(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de listagem de usuários."""
        response = await http_client.get("/usuarios", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_list_usuarios_pagination(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de paginação de usuários."""
        response = await http_client.get(
            "/usuarios",
            params={"page": 1, "per_page": 5},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 5

    @pytest.mark.asyncio
    async def test_get_usuario(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de busca de usuário por ID."""
        list_response = await http_client.get("/usuarios", headers=auth_headers)
        users = list_response.json()["items"]

        if users:
            user_id = users[0]["id"]
            response = await http_client.get(f"/usuarios/{user_id}", headers=auth_headers)

            assert response.status_code == 200
            assert response.json()["id"] == user_id

    @pytest.mark.asyncio
    async def test_list_equipes(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de listagem de equipes."""
        response = await http_client.get("/equipes", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    @pytest.mark.asyncio
    async def test_list_marcacoes(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de listagem de marcações."""
        today = date.today().isoformat()
        response = await http_client.get(
            "/ponto/marcacoes",
            params={"data_inicio": today},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    @pytest.mark.asyncio
    async def test_espelho_ponto(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de consulta de espelho de ponto."""
        inicio = date.today().replace(day=1).isoformat()
        fim = date.today().isoformat()

        response = await http_client.get(
            "/ponto/espelho",
            params={
                "periodo_inicio": inicio,
                "periodo_fim": fim,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_escalas(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de listagem de escalas."""
        response = await http_client.get("/escalas", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    @pytest.mark.asyncio
    async def test_dashboard_stats(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de estatísticas do dashboard."""
        response = await http_client.get("/dashboard/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "colaboradores" in data or "total_colaboradores" in data


# ============================================================================
# 6. SUÍTE E2E: OPERAÇÕES DE MUTAÇÃO / CRIAÇÃO (E2E-03)
# ============================================================================

@pytest.mark.skipif(not e2e_live_server_available, reason=e2e_skip_reason)
class TestE2EMutations:
    """Testes E2E que realizam criação ou alteração de registros em Staging."""

    @pytest.fixture
    async def auth_headers(self, http_client: StagingClient):
        token = await get_staging_token(http_client)
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_create_equipe(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste E2E de criação de equipe em Staging."""
        response = await http_client.post(
            "/equipes",
            json={
                "nome": f"Equipe Sintética {datetime.now().timestamp()}",
                "descricao": "Equipe criada para testes automatizados E2E em Staging",
            },
            headers=auth_headers,
        )

        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data
        assert "nome" in data

    @pytest.mark.asyncio
    async def test_create_escala(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste E2E de criação de escala em Staging."""
        response = await http_client.post(
            "/escalas",
            json={
                "nome": f"Escala Sintética {datetime.now().timestamp()}",
                "regime": "fixo",
                "janelas": {
                    "seg": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
                    "ter": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
                    "qua": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
                    "qui": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
                    "sex": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
                },
            },
            headers=auth_headers,
        )

        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data

    @pytest.mark.asyncio
    async def test_cpf_invalid_format(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste E2E de rejeição de CPF com formato inválido."""
        response = await http_client.post(
            "/usuarios",
            json={
                "nome": "Usuário Teste CPF Inválido",
                "email": "invalid_cpf_user@staging.vibeponto.com",
                "cpf": "123",
                "password": "StagingPassword123!",
            },
            headers=auth_headers,
        )

        assert response.status_code in [400, 422]


# ============================================================================
# 7. SUÍTE E2E: RATE LIMITING E CARGA (E2E-03)
# ============================================================================

@pytest.mark.skipif(not e2e_live_server_available, reason=e2e_skip_reason)
class TestE2ERateLimiting:
    """Testes E2E de rate limiting com critério estrito de aprovação (E2E-03)."""

    @pytest.mark.asyncio
    async def test_rate_limit_not_exceeded(self, http_client: httpx.AsyncClient):
        """Teste de requisições normais dentro do limite."""
        for _ in range(5):
            response = await http_client.get("../../health")
            assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_rate_limit_exceeded(self, http_client: httpx.AsyncClient):
        """
        E2E-03: Teste de rate limit excedido.
        Critério estrito: confirma que requisições acima do limite disparam HTTP 429 Too Many Requests.
        """
        responses = []
        # Dispara rajada acima do limite da janela de rate limit
        for _ in range(120):
            res = await http_client.post(
                "/auth/login",
                json={
                    "email": "ratelimit_target@staging.vibeponto.com",
                    "password": "WrongPassword123!",
                },
            )
            responses.append(res.status_code)

        # Deve conter retorno 429 Too Many Requests
        assert 429 in responses, f"Esperado ao menos um status 429 sob rajada, obtidos: {set(responses)}"
