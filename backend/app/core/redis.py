"""Cliente Redis para cache, blacklist de tokens e rate limiting."""

import json
import secrets
from typing import Any, Optional

import redis.asyncio as redis

from app.core.config import settings


class RedisClient:
    """Cliente Redis singleton."""

    _instance: Optional["RedisClient"] = None
    _pool: Optional[redis.ConnectionPool] = None

    def __new__(cls) -> "RedisClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """Inicializa o pool de conexões."""
        import asyncio

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self._pool is not None and current_loop is not None:
            bound_loop = getattr(self, "_bound_loop", None)
            if bound_loop is not None and (bound_loop.is_closed() or bound_loop is not current_loop):
                self._pool = None

        if self._pool is None:
            self._bound_loop = current_loop
            self._pool = redis.ConnectionPool.from_url(
                str(settings.redis_url),
                max_connections=20,
                decode_responses=True,
            )

    @property
    def client(self) -> redis.Redis:
        """Retorna cliente Redis."""
        if self._pool is None:
            raise RuntimeError("Redis não conectado. Chame connect() primeiro.")
        return redis.Redis(connection_pool=self._pool)

    async def close(self) -> None:
        """Fecha conexões."""
        if self._pool:
            await self._pool.disconnect()
            self._pool = None

    # =========================================================================
    # Token Blacklist (Logout)
    # =========================================================================

    async def blacklist_token(self, token: str, ttl_seconds: int = 86400) -> None:
        """
        Adiciona token à blacklist.

        Args:
            token: Token JWT
            ttl_seconds: Tempo de vida na blacklist (padrão 24h)
        """
        await self.client.setex(f"blacklist:{token}", ttl_seconds, "1")

    async def is_token_blacklisted(self, token: str) -> bool:
        """Verifica se token está na blacklist."""
        result = await self.client.get(f"blacklist:{token}")
        return result is not None

    # =========================================================================
    # Rate Limiting
    # =========================================================================

    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        Verifica rate limit com sliding window.

        Args:
            key: Identificador único (ex: user_id, ip)
            max_requests: Máximo de requisições permitidas
            window_seconds: Janela de tempo

        Returns:
            tuple: (allowed, remaining, reset_time)
        """
        import time
        from uuid import uuid4

        now = int(time.time())
        window_start = now - window_seconds

        pipeline = self.client.pipeline()
        redis_key = f"ratelimit:{key}"

        # Remover entradas antigas
        pipeline.zremrangebyscore(redis_key, "-inf", window_start)
        # Adicionar requisição atual
        pipeline.zadd(redis_key, {str(uuid4()): now})
        # Contar requisições na janela
        pipeline.zcard(redis_key)
        # Definir expiração
        pipeline.expire(redis_key, window_seconds)

        results = await pipeline.execute()
        request_count = results[2]

        allowed = request_count <= max_requests
        remaining = max(0, max_requests - request_count)
        reset_time = now + window_seconds

        return allowed, remaining, reset_time

    # =========================================================================
    # Cache Genérico
    # =========================================================================

    async def cache_get(self, key: str) -> Optional[Any]:
        """Obtém valor do cache."""
        data = await self.client.get(f"cache:{key}")
        if data:
            return json.loads(data)
        return None

    async def cache_set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 300,
    ) -> None:
        """Define valor no cache."""
        await self.client.setex(
            f"cache:{key}",
            ttl_seconds,
            json.dumps(value, default=str),
        )

    async def cache_delete(self, key: str) -> None:
        """Remove valor do cache."""
        await self.client.delete(f"cache:{key}")

    async def cache_clear_pattern(self, pattern: str) -> None:
        """Remove valores que correspondem ao padrão."""
        async for key in self.client.scan_iter(f"cache:{pattern}"):
            await self.client.delete(key)

    # =========================================================================
    # Password Reset Tokens
    # =========================================================================

    async def store_password_reset_token(
        self,
        user_id: str,
        token: str,
        ttl_seconds: int = 3600,
    ) -> None:
        """Armazena token de reset de senha (1h padrão)."""
        await self.client.setex(f"password_reset:{token}", ttl_seconds, user_id)

    async def peek_password_reset_user(self, token: str) -> Optional[str]:
        """Consulta user_id pelo token de reset sem consumi-lo (operação GET pura)."""
        return await self.client.get(f"password_reset:{token}")

    async def consume_password_reset_user(self, token: str) -> Optional[str]:
        """Obtém e consome user_id pelo token de reset em operação atômica (GETDEL)."""
        return await self.client.getdel(f"password_reset:{token}")

    async def get_password_reset_user(self, token: str) -> Optional[str]:
        """Consulta user_id pelo token de reset sem consumi-lo (GET - alias de peek)."""
        return await self.peek_password_reset_user(token)

    async def invalidate_password_reset_token(self, token: str) -> None:
        """Invalida token de reset."""
        await self.client.delete(f"password_reset:{token}")

    async def reserve_password_reset_token(
        self,
        token: str,
        lock_ttl_seconds: int = 30,
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Reserva o token de reset atomicamente sob concorrência (USR-43).
        """
        user_id = await self.client.get(f"password_reset:{token}")
        if not user_id:
            return None, None

        lock_id = secrets.token_hex(16)
        acquired = await self.client.set(
            f"password_reset_lock:{token}",
            lock_id,
            nx=True,
            ex=lock_ttl_seconds,
        )
        if not acquired:
            return None, None

        return user_id, lock_id

    async def release_password_reset_lock(self, token: str, lock_id: str) -> bool:
        """
        Liberta a trava do token de reset de senha se o lock_id corresponder (USR-43).
        """
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = await self.client.eval(script, 1, f"password_reset_lock:{token}", lock_id)
        return bool(result)

    async def finalize_password_reset(self, token: str, lock_id: str, user_id: str) -> bool:
        """
        Finaliza a redefinição de senha (USR-43):
        1. Consome o token no Redis.
        2. Libera a trava de concorrência.
        3. Revoga todas as sessões ativas do usuário.
        """
        await self.consume_password_reset_user(token)
        await self.release_password_reset_lock(token, lock_id)
        await self.revoke_all_user_sessions(user_id)
        return True

    # =========================================================================
    # Session Management
    # =========================================================================

    async def store_user_session(
        self,
        user_id: str,
        session_id: str,
        data: dict,
        ttl_seconds: int = 86400 * 7,
    ) -> None:
        """Armazena sessão do usuário (7 dias padrão)."""
        await self.client.setex(
            f"session:{user_id}:{session_id}",
            ttl_seconds,
            json.dumps(data, default=str),
        )

    async def get_user_sessions(self, user_id: str) -> list[dict]:
        """Lista todas as sessões ativas do usuário."""
        sessions = []
        async for key in self.client.scan_iter(f"session:{user_id}:*"):
            data = await self.client.get(key)
            if data:
                session = json.loads(data)
                session["session_id"] = key.split(":")[-1]
                sessions.append(session)
        return sessions

    async def revoke_user_session(self, user_id: str, session_id: str) -> None:
        """Revoga uma sessão específica."""
        await self.client.delete(f"session:{user_id}:{session_id}")

    async def revoke_all_user_sessions(self, user_id: str) -> int:
        """Revoga todas as sessões do usuário."""
        count = 0
        async for key in self.client.scan_iter(f"session:{user_id}:*"):
            await self.client.delete(key)
            count += 1
        return count


# Singleton global
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """Dependency para obter cliente Redis."""
    await redis_client.connect()
    return redis_client
