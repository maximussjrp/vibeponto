"""OPS-04: guarda obrigatória para testes que executam DROP SCHEMA / FLUSHDB.

Regras (todas obrigatórias, avaliadas antes de qualquer operação destrutiva):

1. Autorização explícita: ALLOW_DESTRUCTIVE_TESTING=true (padrão: false).
2. Ambiente da aplicação não pode ser production/staging.
3. Validação estrutural das URLs (urllib.parse), sem busca por substring:
   esquema esperado, host loopback, porta explícita e diferente da padrão,
   banco PostgreSQL com prefixo ``test_``, sem query string (que poderia
   redirecionar o host, ex.: ``?host=``).
4. Identificação positiva: o operador declara VIBEPONTO_DISPOSABLE_ENV_ID e
   AMBOS os alvos precisam carregar esse mesmo identificador:
   - PostgreSQL: ``COMMENT ON DATABASE`` = ``vibeponto-disposable-test-env:<id>``
     (o comentário de banco sobrevive ao DROP SCHEMA public);
   - Redis: chave ``__vibeponto_disposable_test_env__`` = ``<id>``.
   Os marcadores são gravados somente por ``python -m tests.mark_disposable_env``
   ao provisionar contêineres dedicados. Localhost, porta alternativa ou nome
   contendo "test" NÃO bastam: sem marcador, a execução é interrompida.

Mensagens de erro nunca incluem URLs, usuários ou senhas.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.parse import urlsplit

LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
PG_SCHEMES = frozenset({"postgresql", "postgresql+asyncpg"})
REDIS_SCHEMES = frozenset({"redis"})
PG_DEFAULT_PORT = 5432
REDIS_DEFAULT_PORT = 6379
PG_DB_NAME_RE = re.compile(r"test_[a-z0-9_]{1,50}")
ENV_ID_RE = re.compile(r"[A-Za-z0-9_-]{16,64}")
ENV_ID_VAR = "VIBEPONTO_DISPOSABLE_ENV_ID"
PG_MARKER_PREFIX = "vibeponto-disposable-test-env:"
REDIS_MARKER_KEY = "__vibeponto_disposable_test_env__"
FORBIDDEN_APP_ENVIRONMENTS = frozenset({"production", "prod", "staging"})


class UnsafeTestEnvironment(Exception):
    """Alvo não comprovadamente descartável; nenhuma operação destrutiva deve ocorrer."""


def destructive_testing_allowed(environ: Mapping[str, str]) -> bool:
    return environ.get("ALLOW_DESTRUCTIVE_TESTING", "false").strip().lower() == "true"


def _split(url: str, label: str):
    try:
        parts = urlsplit(url)
        port = parts.port  # levanta ValueError para porta inválida
    except ValueError:
        raise UnsafeTestEnvironment(f"{label}: URL malformada") from None
    return parts, port


def validate_postgres_url(url: str) -> str:
    parts, port = _split(url, "PostgreSQL")
    if parts.scheme not in PG_SCHEMES:
        raise UnsafeTestEnvironment("PostgreSQL: esquema de URL não suportado")
    if (parts.hostname or "") not in LOOPBACK_HOSTS:
        raise UnsafeTestEnvironment("PostgreSQL: host não é loopback")
    if port is None or port == PG_DEFAULT_PORT:
        raise UnsafeTestEnvironment("PostgreSQL: porta deve ser explícita e diferente da padrão")
    if parts.query or parts.fragment:
        raise UnsafeTestEnvironment("PostgreSQL: parâmetros na URL não são permitidos")
    db_name = parts.path.lstrip("/")
    if not PG_DB_NAME_RE.fullmatch(db_name):
        raise UnsafeTestEnvironment("PostgreSQL: nome do banco deve seguir o padrão test_<nome>")
    return db_name


def validate_redis_url(url: str) -> int:
    parts, port = _split(url, "Redis")
    if parts.scheme not in REDIS_SCHEMES:
        raise UnsafeTestEnvironment("Redis: esquema de URL não suportado")
    if (parts.hostname or "") not in LOOPBACK_HOSTS:
        raise UnsafeTestEnvironment("Redis: host não é loopback")
    if port is None or port == REDIS_DEFAULT_PORT:
        raise UnsafeTestEnvironment("Redis: porta deve ser explícita e diferente da padrão")
    if parts.query or parts.fragment:
        raise UnsafeTestEnvironment("Redis: parâmetros na URL não são permitidos")
    db_index = parts.path.lstrip("/") or "0"
    if not db_index.isdigit():
        raise UnsafeTestEnvironment("Redis: índice de banco inválido")
    return int(db_index)


def require_env_id(environ: Mapping[str, str]) -> str:
    env_id = environ.get(ENV_ID_VAR, "").strip()
    if not ENV_ID_RE.fullmatch(env_id):
        raise UnsafeTestEnvironment(
            f"{ENV_ID_VAR} ausente ou inválido (16-64 caracteres [A-Za-z0-9_-])"
        )
    return env_id


def check_static(db_url: str, redis_url: str, environ: Mapping[str, str]) -> str:
    """Validações sem rede. Retorna o identificador declarado do ambiente."""
    app_env = environ.get("ENVIRONMENT", "").strip().lower()
    if app_env in FORBIDDEN_APP_ENVIRONMENTS:
        raise UnsafeTestEnvironment("ENVIRONMENT indica ambiente não descartável")
    validate_postgres_url(db_url)
    validate_redis_url(redis_url)
    return require_env_id(environ)


def check_markers(env_id: str, pg_comment: str | None, redis_marker: str | None) -> None:
    """Compara os marcadores lidos dos alvos com o identificador declarado."""
    if pg_comment != f"{PG_MARKER_PREFIX}{env_id}":
        raise UnsafeTestEnvironment("PostgreSQL: marcador de ambiente descartável ausente ou divergente")
    if redis_marker != env_id:
        raise UnsafeTestEnvironment("Redis: marcador de ambiente descartável ausente ou divergente")


PG_MARKER_QUERY = (
    "SELECT shobj_description(oid, 'pg_database') FROM pg_database "
    "WHERE datname = current_database()"
)


async def read_postgres_marker(db_url: str) -> str | None:
    """Leitura somente-consulta do comentário do banco (nenhuma escrita)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(db_url)
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(PG_MARKER_QUERY))).scalar()
    finally:
        await engine.dispose()


async def read_redis_marker(redis_url: str) -> str | None:
    import redis.asyncio as aioredis

    client = aioredis.Redis.from_url(redis_url, decode_responses=True)
    try:
        return await client.get(REDIS_MARKER_KEY)
    finally:
        await client.aclose()


async def verify_disposable_environment(db_url: str, redis_url: str, environ: Mapping[str, str]) -> str:
    """Validação completa; levanta UnsafeTestEnvironment com mensagem sanitizada."""
    env_id = check_static(db_url, redis_url, environ)
    try:
        pg_comment = await read_postgres_marker(db_url)
    except Exception as exc:
        raise UnsafeTestEnvironment(f"PostgreSQL: não foi possível identificar o alvo ({type(exc).__name__})") from None
    try:
        redis_marker = await read_redis_marker(redis_url)
    except Exception as exc:
        raise UnsafeTestEnvironment(f"Redis: não foi possível identificar o alvo ({type(exc).__name__})") from None
    check_markers(env_id, pg_comment, redis_marker)
    return env_id
