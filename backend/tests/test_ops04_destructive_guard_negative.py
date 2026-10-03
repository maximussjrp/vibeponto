"""Testes negativos para a guarda destrutiva OPS-04 (destructive_guard.py).

Garante que NENHUMA operação destrutiva (DROP SCHEMA, FLUSHDB) pode ser executada se:
1. ALLOW_DESTRUCTIVE_TESTING estiver ausente ou false.
2. VIBEPONTO_DISPOSABLE_ENV_ID estiver ausente, malformado ou divergente.
3. As URLs de PostgreSQL/Redis não cumprirem os requisitos estruturais.
4. Os marcadores de ambiente descartável no PostgreSQL ou Redis forem ausentes ou incompatíveis.
5. O parâmetro ENVIRONMENT indicar produção/staging.
"""

import pytest

from tests.destructive_guard import (
    UnsafeTestEnvironment,
    check_markers,
    check_static,
    destructive_testing_allowed,
    require_env_id,
    validate_postgres_url,
    validate_redis_url,
)


def test_destructive_guard_rejected_when_allow_destructive_testing_false():
    """OPS-04: ALLOW_DESTRUCTIVE_TESTING desativado por padrão ou false."""
    assert not destructive_testing_allowed({})
    assert not destructive_testing_allowed({"ALLOW_DESTRUCTIVE_TESTING": "false"})
    assert not destructive_testing_allowed({"ALLOW_DESTRUCTIVE_TESTING": "0"})
    assert not destructive_testing_allowed({"ALLOW_DESTRUCTIVE_TESTING": "no"})
    assert destructive_testing_allowed({"ALLOW_DESTRUCTIVE_TESTING": "true"})
    assert destructive_testing_allowed({"ALLOW_DESTRUCTIVE_TESTING": "TRUE"})


def test_destructive_guard_rejected_when_env_id_missing_or_invalid():
    """OPS-04: Identificador do ambiente descartável é obrigatório (16-64 chars A-Z, a-z, 0-9, _, -)."""
    with pytest.raises(UnsafeTestEnvironment, match="VIBEPONTO_DISPOSABLE_ENV_ID ausente ou inválido"):
        require_env_id({})

    with pytest.raises(UnsafeTestEnvironment, match="VIBEPONTO_DISPOSABLE_ENV_ID ausente ou inválido"):
        require_env_id({"VIBEPONTO_DISPOSABLE_ENV_ID": ""})

    with pytest.raises(UnsafeTestEnvironment, match="VIBEPONTO_DISPOSABLE_ENV_ID ausente ou inválido"):
        require_env_id({"VIBEPONTO_DISPOSABLE_ENV_ID": "too_short"})

    with pytest.raises(UnsafeTestEnvironment, match="VIBEPONTO_DISPOSABLE_ENV_ID ausente ou inválido"):
        require_env_id({"VIBEPONTO_DISPOSABLE_ENV_ID": "invalid chars!"})

    # Válido: string hex de 32 chars
    valid_id = "testenv_1234567890abcdef12345678"
    assert require_env_id({"VIBEPONTO_DISPOSABLE_ENV_ID": valid_id}) == valid_id


def test_destructive_guard_rejected_when_postgres_url_invalid():
    """OPS-04: Validação estrutural rigorosa da URL do PostgreSQL."""
    # Host não loopback
    with pytest.raises(UnsafeTestEnvironment, match="PostgreSQL: host não é loopback"):
        validate_postgres_url("postgresql+asyncpg://postgres:postgres@db.prod.company.com:54399/test_vibeponto")

    # Porta padrão 5432 negada
    with pytest.raises(UnsafeTestEnvironment, match="PostgreSQL: porta deve ser explícita e diferente da padrão"):
        validate_postgres_url("postgresql+asyncpg://postgres:postgres@localhost:5432/test_vibeponto")

    # Sem porta explícita negado
    with pytest.raises(UnsafeTestEnvironment, match="PostgreSQL: porta deve ser explícita e diferente da padrão"):
        validate_postgres_url("postgresql+asyncpg://postgres:postgres@localhost/test_vibeponto")

    # Nome do banco sem prefixo test_
    with pytest.raises(UnsafeTestEnvironment, match="PostgreSQL: nome do banco deve seguir o padrão test_<nome>"):
        validate_postgres_url("postgresql+asyncpg://postgres:postgres@localhost:54399/vibeponto_production")

    # Parâmetros de query string (que poderiam tentar redirecionar host) negados
    with pytest.raises(UnsafeTestEnvironment, match="PostgreSQL: parâmetros na URL não são permitidos"):
        validate_postgres_url("postgresql+asyncpg://postgres:postgres@localhost:54399/test_vibeponto?host=remote")

    # Válido
    assert validate_postgres_url("postgresql+asyncpg://postgres:postgres@localhost:54399/test_vibeponto") == "test_vibeponto"


def test_destructive_guard_rejected_when_redis_url_invalid():
    """OPS-04: Validação estrutural rigorosa da URL do Redis."""
    # Host não loopback
    with pytest.raises(UnsafeTestEnvironment, match="Redis: host não é loopback"):
        validate_redis_url("redis://redis.prod.company.com:56379/0")

    # Porta padrão 6379 negada
    with pytest.raises(UnsafeTestEnvironment, match="Redis: porta deve ser explícita e diferente da padrão"):
        validate_redis_url("redis://localhost:6379/0")

    # Parâmetros na URL negados
    with pytest.raises(UnsafeTestEnvironment, match="Redis: parâmetros na URL não são permitidos"):
        validate_redis_url("redis://localhost:56379/0?db=1")

    # Válido
    assert validate_redis_url("redis://localhost:56379/0") == 0


def test_destructive_guard_rejected_when_markers_mismatched():
    """OPS-04: Marcadores no banco e no Redis devem corresponder exatamente ao env_id."""
    env_id = "testenv_1234567890abcdef12345678"

    # PostgreSQL ausente
    with pytest.raises(UnsafeTestEnvironment, match="PostgreSQL: marcador de ambiente descartável ausente ou divergente"):
        check_markers(env_id, None, env_id)

    # PostgreSQL divergente
    with pytest.raises(UnsafeTestEnvironment, match="PostgreSQL: marcador de ambiente descartável ausente ou divergente"):
        check_markers(env_id, "vibeponto-disposable-test-env:other_id", env_id)

    # Redis ausente
    with pytest.raises(UnsafeTestEnvironment, match="Redis: marcador de ambiente descartável ausente ou divergente"):
        check_markers(env_id, f"vibeponto-disposable-test-env:{env_id}", None)

    # Redis divergente
    with pytest.raises(UnsafeTestEnvironment, match="Redis: marcador de ambiente descartável ausente ou divergente"):
        check_markers(env_id, f"vibeponto-disposable-test-env:{env_id}", "other_redis_id")

    # Ambos corretos -> nenhuma exceção
    check_markers(env_id, f"vibeponto-disposable-test-env:{env_id}", env_id)


def test_destructive_guard_rejected_when_app_environment_production_or_staging():
    """OPS-04: Impede testes destrutivos se ENVIRONMENT for production ou staging."""
    valid_pg = "postgresql+asyncpg://postgres:postgres@localhost:54399/test_vibeponto"
    valid_redis = "redis://localhost:56379/0"
    valid_id = "testenv_1234567890abcdef12345678"

    with pytest.raises(UnsafeTestEnvironment, match="ENVIRONMENT indica ambiente não descartável"):
        check_static(valid_pg, valid_redis, {"VIBEPONTO_DISPOSABLE_ENV_ID": valid_id, "ENVIRONMENT": "production"})

    with pytest.raises(UnsafeTestEnvironment, match="ENVIRONMENT indica ambiente não descartável"):
        check_static(valid_pg, valid_redis, {"VIBEPONTO_DISPOSABLE_ENV_ID": valid_id, "ENVIRONMENT": "staging"})
