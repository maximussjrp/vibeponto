"""Atomic, shared limits on authentication endpoints."""

import hashlib

from fastapi import HTTPException, Request
from redis.exceptions import RedisError

from app.core.redis import get_redis


async def auth_rate_limit(request: Request):
    if request.method != "POST":
        return
    # Do not trust arbitrary X-Forwarded-For headers. Configure trusted proxies in uvicorn.
    address = request.client.host if request.client else "unknown"
    key = hashlib.sha256(f"{request.url.path}:{address}".encode()).hexdigest()
    maximum = 60 if request.url.path.endswith(("/refresh", "/logout")) else 10
    try:
        redis = await get_redis()
        allowed, _, _ = await redis.check_rate_limit(key, maximum, 60)
    except RedisError:
        raise HTTPException(503, "Serviço de autenticação indisponível") from None
    if not allowed:
        raise HTTPException(429, "Muitas tentativas. Aguarde e tente novamente", headers={"Retry-After": "60"})
