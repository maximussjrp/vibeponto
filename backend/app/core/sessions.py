"""Revocable sessions: Redis stores identifiers and refresh hashes, never JWTs."""

import hashlib
import time
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, Response
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis import get_redis
from app.core.security import create_access_token, create_refresh_token, decode_token

COOKIE_NAME = "vibeponto_refresh"
COOKIE_PATH = "/api/v1/auth"


def unauthorized():
    return HTTPException(401, "Token inválido ou expirado", headers={"WWW-Authenticate": "Bearer"})


def session_key(payload):
    return f"session:{payload['sub']}:{payload['sid']}"


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def cookie_mode(request: Request) -> bool:
    return request.headers.get("X-Auth-Mode") == "cookie" or COOKIE_NAME in request.cookies


def check_cookie_origin(request: Request):
    # The custom header requires a CORS preflight; Origin must match our allowlist.
    if request.headers.get("X-Auth-Mode") != "cookie" or request.headers.get("origin") not in settings.cors_origins:
        raise HTTPException(403, "Origem da requisição inválida")


def set_refresh_cookie(response: Response, token: str, expires: int):
    response.set_cookie(COOKIE_NAME, token, httponly=True,
                        secure=settings.environment != "development", samesite="strict",
                        path=COOKIE_PATH, max_age=max(0, expires - int(time.time())))
    response.headers["Cache-Control"] = "no-store"


def clear_refresh_cookie(response: Response):
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, httponly=True,
                           secure=settings.environment != "development", samesite="strict")
    response.headers["Cache-Control"] = "no-store"


async def validate_session(token: str, expected_type: str):
    payload = decode_token(token)
    if not payload or payload.get("type") != expected_type:
        raise unauthorized()
    try:
        UUID(payload["sid"])
        UUID(payload["jti"])
    except (KeyError, ValueError, TypeError, AttributeError):
        raise unauthorized() from None
    try:
        client = await get_redis()
        stored = await client.client.get(session_key(payload))
    except RedisError:
        raise HTTPException(503, "Serviço de autenticação indisponível") from None
    if not stored or (expected_type == "refresh" and stored != digest(token)):
        raise unauthorized()
    return payload


async def issue_tokens(user_id, tenant_id, papel, previous=None):
    sid = previous["sid"] if previous else str(uuid4())
    claims = {"sub": str(user_id), "sid": sid}
    access = create_access_token({**claims, "tenant_id": str(tenant_id), "papel": papel})
    refresh = create_refresh_token(claims)
    expires = decode_token(refresh)["exp"]
    try:
        client = await get_redis()
        if previous:
            # Rotation and revocation cannot race into resurrecting a logged-out session.
            rotated = await client.client.eval(
                "if redis.call('GET', KEYS[1]) == ARGV[1] then "
                "redis.call('SET', KEYS[1], ARGV[2], 'KEEPTTL'); return 1 end; return 0",
                1, session_key(previous), previous["refresh_digest"], digest(refresh),
            )
            if not rotated:
                raise unauthorized()
            ttl = await client.client.ttl(session_key(previous))
            if ttl <= 0:
                raise unauthorized()
            expires = int(time.time()) + ttl
        else:
            await client.client.set(session_key(claims), digest(refresh), ex=expires - int(time.time()))
    except RedisError:
        raise HTTPException(503, "Serviço de autenticação indisponível") from None
    return access, refresh, expires
