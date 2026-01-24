"""
Fixtures compartilhados para os testes
"""

import pytest
import asyncio
from typing import AsyncGenerator

import httpx


API_BASE_URL = "http://localhost:8000/api/v1"


@pytest.fixture(scope="session")
def event_loop():
    """Criar event loop para a sessão de testes."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Cliente HTTP para testes de API."""
    async with httpx.AsyncClient(
        base_url=API_BASE_URL,
        timeout=30.0,
        follow_redirects=True
    ) as client:
        yield client


@pytest.fixture
async def admin_token(http_client: httpx.AsyncClient) -> str:
    """Token de autenticação do admin."""
    response = await http_client.post("/auth/login", json={
        "email": "maximussjrp@hotmail.com",
        "password": "Admin@123"
    })
    
    if response.status_code != 200:
        pytest.skip("Não foi possível autenticar")
    
    return response.json()["access_token"]


@pytest.fixture
async def auth_headers(admin_token: str) -> dict:
    """Headers com autenticação."""
    return {"Authorization": f"Bearer {admin_token}"}
