"""HTTP authentication regression tests with a mocked database boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest

from app.api.deps import get_db
from app.core.security import create_access_token, create_refresh_token
from app.main import app
from app.core.rate_limit import auth_rate_limit


@pytest.fixture
async def client():
    db = Mock()
    db.execute = AsyncMock()

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[auth_rate_limit] = lambda: None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.parametrize("token", ["broken", create_access_token({"sub": "bad-uuid"}),
                                  create_refresh_token({"sub": str(uuid4())})], ids=["malformed", "invalid-sub", "refresh-as-access"])
async def test_reject_invalid_access(client, token):
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_missing_access(client):
    assert (await client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.parametrize("token", ["broken", create_access_token({"sub": str(uuid4())})], ids=["malformed", "access-as-refresh"])
async def test_reject_invalid_refresh(client, token):
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401
