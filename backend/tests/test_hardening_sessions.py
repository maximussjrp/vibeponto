"""Redis-backed session regressions."""

from uuid import uuid4

import pytest

import app.core.redis as redis_module
from app.core.sessions import digest, issue_tokens, session_key, validate_session


async def test_refresh_rotation_and_session_revocation(monkeypatch):
    monkeypatch.setattr(redis_module.settings, "redis_url", "redis://localhost:56379/15")
    await redis_module.redis_client.close()
    redis_sessions = await redis_module.get_redis()
    await redis_sessions.client.flushdb()

    user_id = uuid4()
    tenant_id = uuid4()

    try:
        access, refresh, _ = await issue_tokens(user_id, tenant_id, "colaborador")
        refresh_payload = await validate_session(refresh, "refresh")
        access_payload = await validate_session(access, "access")

        rotated_access, rotated_refresh, _ = await issue_tokens(
            user_id,
            tenant_id,
            "colaborador",
            previous={**refresh_payload, "refresh_digest": digest(refresh)},
        )

        with pytest.raises(Exception) as old_refresh_error:
            await validate_session(refresh, "refresh")
        assert getattr(old_refresh_error.value, "status_code", None) == 401

        rotated_payload = await validate_session(rotated_refresh, "refresh")
        assert rotated_payload["sid"] == refresh_payload["sid"]
        await validate_session(rotated_access, "access")

        await redis_sessions.client.delete(session_key(access_payload))
        with pytest.raises(Exception) as access_error:
            await validate_session(rotated_access, "access")
        assert getattr(access_error.value, "status_code", None) == 401
    finally:
        await redis_sessions.client.flushdb()
        await redis_module.redis_client.close()
