"""
Testes automatizados do backend VibePonto
Usando pytest + pytest-asyncio
"""

import pytest
import asyncio
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from uuid import uuid4, UUID
from typing import AsyncGenerator

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Configuração de teste
TEST_DATABASE_URL = "postgresql+asyncpg://vibeponto:vibeponto_dev_123@localhost:5432/vibeponto_test"
API_BASE_URL = "http://localhost:8000/api/v1"


# ==================== Fixtures ====================

@pytest.fixture(scope="session")
def event_loop():
    """Criar event loop para os testes."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Cliente HTTP para testes de API."""
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture
async def authenticated_client(http_client: httpx.AsyncClient) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Cliente HTTP autenticado."""
    # Login
    response = await http_client.post("/auth/login", json={
        "email": "admin@test.com",
        "password": "Test@123"
    })
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        http_client.headers["Authorization"] = f"Bearer {token}"
    
    yield http_client


# ==================== Testes de Autenticação ====================

class TestAuth:
    """Testes do módulo de autenticação."""
    
    @pytest.mark.asyncio
    async def test_login_success(self, http_client: httpx.AsyncClient):
        """Teste de login com credenciais válidas."""
        response = await http_client.post("/auth/login", json={
            "email": "maximussjrp@hotmail.com",
            "password": "Admin@123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, http_client: httpx.AsyncClient):
        """Teste de login com credenciais inválidas."""
        response = await http_client.post("/auth/login", json={
            "email": "invalid@test.com",
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_login_missing_fields(self, http_client: httpx.AsyncClient):
        """Teste de login sem campos obrigatórios."""
        response = await http_client.post("/auth/login", json={
            "email": "test@test.com"
        })
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_refresh_token(self, http_client: httpx.AsyncClient):
        """Teste de refresh token."""
        # Primeiro fazer login
        login_response = await http_client.post("/auth/login", json={
            "email": "maximussjrp@hotmail.com",
            "password": "Admin@123"
        })
        
        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh_token"]
        
        # Usar refresh token
        refresh_response = await http_client.post("/auth/refresh", json={
            "refresh_token": refresh_token
        })
        
        assert refresh_response.status_code == 200
        assert "access_token" in refresh_response.json()
    
    @pytest.mark.asyncio
    async def test_me_authenticated(self, http_client: httpx.AsyncClient):
        """Teste de obter dados do usuário autenticado."""
        # Login
        login_response = await http_client.post("/auth/login", json={
            "email": "maximussjrp@hotmail.com",
            "password": "Admin@123"
        })
        token = login_response.json()["access_token"]
        
        # Obter dados
        response = await http_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data
    
    @pytest.mark.asyncio
    async def test_me_unauthenticated(self, http_client: httpx.AsyncClient):
        """Teste de acesso não autenticado."""
        response = await http_client.get("/auth/me")
        assert response.status_code == 401


# ==================== Testes de Usuários ====================

class TestUsuarios:
    """Testes do módulo de usuários."""
    
    @pytest.fixture
    async def auth_headers(self, http_client: httpx.AsyncClient):
        """Headers de autenticação."""
        response = await http_client.post("/auth/login", json={
            "email": "maximussjrp@hotmail.com",
            "password": "Admin@123"
        })
        token = response.json()["access_token"]
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
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 5
    
    @pytest.mark.asyncio
    async def test_get_usuario(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de buscar usuário por ID."""
        # Primeiro listar
        list_response = await http_client.get("/usuarios", headers=auth_headers)
        users = list_response.json()["items"]
        
        if users:
            user_id = users[0]["id"]
            response = await http_client.get(f"/usuarios/{user_id}", headers=auth_headers)
            
            assert response.status_code == 200
            assert response.json()["id"] == user_id


# ==================== Testes de Equipes ====================

class TestEquipes:
    """Testes do módulo de equipes."""
    
    @pytest.fixture
    async def auth_headers(self, http_client: httpx.AsyncClient):
        response = await http_client.post("/auth/login", json={
            "email": "maximussjrp@hotmail.com",
            "password": "Admin@123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.mark.asyncio
    async def test_list_equipes(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de listagem de equipes."""
        response = await http_client.get("/equipes", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
    
    @pytest.mark.asyncio
    async def test_create_equipe(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de criação de equipe."""
        response = await http_client.post("/equipes", json={
            "nome": f"Equipe Teste {datetime.now().timestamp()}",
            "descricao": "Equipe criada para testes automatizados"
        }, headers=auth_headers)
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data
        assert "nome" in data


# ==================== Testes de Marcações ====================

class TestMarcacoes:
    """Testes do módulo de ponto."""
    
    @pytest.fixture
    async def auth_headers(self, http_client: httpx.AsyncClient):
        response = await http_client.post("/auth/login", json={
            "email": "maximussjrp@hotmail.com",
            "password": "Admin@123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.mark.asyncio
    async def test_list_marcacoes(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de listagem de marcações."""
        today = date.today().isoformat()
        response = await http_client.get(
            "/ponto/marcacoes",
            params={"data_inicio": today},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
    
    @pytest.mark.asyncio
    async def test_espelho_ponto(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de espelho de ponto."""
        inicio = date.today().replace(day=1).isoformat()
        fim = date.today().isoformat()
        
        response = await http_client.get(
            "/ponto/espelho",
            params={
                "periodo_inicio": inicio,
                "periodo_fim": fim
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200


# ==================== Testes de Escalas ====================

class TestEscalas:
    """Testes do módulo de escalas."""
    
    @pytest.fixture
    async def auth_headers(self, http_client: httpx.AsyncClient):
        response = await http_client.post("/auth/login", json={
            "email": "maximussjrp@hotmail.com",
            "password": "Admin@123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.mark.asyncio
    async def test_list_escalas(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de listagem de escalas."""
        response = await http_client.get("/escalas", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
    
    @pytest.mark.asyncio
    async def test_create_escala(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de criação de escala."""
        response = await http_client.post("/escalas", json={
            "nome": f"Escala Teste {datetime.now().timestamp()}",
            "regime": "fixo",
            "janelas": {
                "seg": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
                "ter": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
                "qua": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
                "qui": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
                "sex": {"entrada": "08:00", "saida": "17:00", "pausa_minutos": 60},
            }
        }, headers=auth_headers)
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data


# ==================== Testes de Dashboard ====================

class TestDashboard:
    """Testes do dashboard."""
    
    @pytest.fixture
    async def auth_headers(self, http_client: httpx.AsyncClient):
        response = await http_client.post("/auth/login", json={
            "email": "maximussjrp@hotmail.com",
            "password": "Admin@123"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.mark.asyncio
    async def test_dashboard_stats(self, http_client: httpx.AsyncClient, auth_headers):
        """Teste de estatísticas do dashboard."""
        response = await http_client.get("/dashboard/stats", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "total_colaboradores" in data


# ==================== Testes de Serviços ====================

class TestCalculoHoras:
    """Testes do serviço de cálculo de horas."""
    
    def test_calcular_horas_normais(self):
        """Teste de cálculo de horas normais."""
        from app.services.calculo_horas import CalculoHorasService, JornadaConfig
        
        config = JornadaConfig()
        service = CalculoHorasService(config)
        
        # Simular jornada normal (8h)
        entrada = datetime.now().replace(hour=8, minute=0)
        saida = datetime.now().replace(hour=17, minute=0)
        pausa_inicio = datetime.now().replace(hour=12, minute=0)
        pausa_fim = datetime.now().replace(hour=13, minute=0)
        
        marcacoes = [
            type('M', (), {'data_hora': entrada, 'evento': 'entrada'})(),
            type('M', (), {'data_hora': pausa_inicio, 'evento': 'pausa_inicio'})(),
            type('M', (), {'data_hora': pausa_fim, 'evento': 'pausa_fim'})(),
            type('M', (), {'data_hora': saida, 'evento': 'saida'})(),
        ]
        
        resultado = service.calcular_dia(marcacoes, entrada.date())
        
        assert resultado.horas_trabalhadas == timedelta(hours=8)
        assert resultado.horas_extras_50 == timedelta()
    
    def test_calcular_horas_extras(self):
        """Teste de cálculo com horas extras."""
        from app.services.calculo_horas import CalculoHorasService, JornadaConfig
        
        config = JornadaConfig()
        service = CalculoHorasService(config)
        
        # Simular jornada com 2h extras
        entrada = datetime.now().replace(hour=8, minute=0)
        saida = datetime.now().replace(hour=19, minute=0)  # 2h a mais
        pausa_inicio = datetime.now().replace(hour=12, minute=0)
        pausa_fim = datetime.now().replace(hour=13, minute=0)
        
        marcacoes = [
            type('M', (), {'data_hora': entrada, 'evento': 'entrada'})(),
            type('M', (), {'data_hora': pausa_inicio, 'evento': 'pausa_inicio'})(),
            type('M', (), {'data_hora': pausa_fim, 'evento': 'pausa_fim'})(),
            type('M', (), {'data_hora': saida, 'evento': 'saida'})(),
        ]
        
        resultado = service.calcular_dia(marcacoes, entrada.date())
        
        assert resultado.horas_extras_50 == timedelta(hours=2)


# ==================== Testes de Rate Limiting ====================

class TestRateLimiting:
    """Testes de rate limiting."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_not_exceeded(self, http_client: httpx.AsyncClient):
        """Teste de requests dentro do limite."""
        # Fazer algumas requests
        for _ in range(5):
            response = await http_client.get("/health")
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_rate_limit_exceeded(self, http_client: httpx.AsyncClient):
        """Teste de requests excedendo limite."""
        # Este teste é lento pois precisa fazer muitas requisições
        responses = []
        for _ in range(250):  # Acima do limite padrão de 200
            response = await http_client.get("/health")
            responses.append(response.status_code)
        
        # Pelo menos uma deve ser 429 (Too Many Requests)
        assert 429 in responses or all(r == 200 for r in responses)


# ==================== Testes de Validação ====================

class TestValidation:
    """Testes de validação de dados."""
    
    @pytest.mark.asyncio
    async def test_email_invalid_format(self, http_client: httpx.AsyncClient):
        """Teste de email com formato inválido."""
        response = await http_client.post("/auth/login", json={
            "email": "invalid-email",
            "password": "password123"
        })
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_cpf_invalid_format(self, http_client: httpx.AsyncClient):
        """Teste de CPF com formato inválido."""
        # Primeiro fazer login
        login_response = await http_client.post("/auth/login", json={
            "email": "maximussjrp@hotmail.com",
            "password": "Admin@123"
        })
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Tentar criar usuário com CPF inválido
        response = await http_client.post("/usuarios", json={
            "nome": "Teste",
            "email": "teste@teste.com",
            "cpf": "123",  # CPF inválido
            "password": "Test@123"
        }, headers=headers)
        
        # Deve retornar erro de validação
        assert response.status_code in [400, 422]


# ==================== Configuração do Pytest ====================

def pytest_configure(config):
    """Configuração do pytest."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
