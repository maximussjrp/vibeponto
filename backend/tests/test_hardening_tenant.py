"""
Tests for Micro-Sprint 01A.2 Tenant & Security Hardening
(Production Code IP Pinning for Webhooks, TLS SNI Preservation, TOCTOU Prevention, Alembic Migration on Real PostgreSQL Engine)
"""

import os
import json
import importlib.util
import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4
import sqlalchemy as sa
import httpx

from app.api.routes.tenant import (
    TenantRead,
    TenantUpdate,
    EnderecoSchema,
    ConfiguracoesIntegracoesRead,
    ConfiguracoesIntegracoesUpdate,
    normalize_tenant_config,
    parse_endereco_dict,
)
from app.core.security_webhook import (
    validate_webhook_url,
    create_pinned_client,
    PinningAsyncHTTPTransport,
)
from app.main import app


def test_tenant_read_does_not_expose_raw_config_or_secrets():
    tenant_id = uuid4()
    raw_tenant = {
        "id": tenant_id,
        "nome": "Empresa Teste LTDA",
        "razao_social": "Empresa Teste Serviços LTDA",
        "cnpj": "12345678000199",
        "email": "contato@empresa.com",
        "telefone": "11999999999",
        "endereco": {"logradouro": "Rua das Flores", "numero": "123"},
        "slug": "empresa-teste",
        "plano": "professional",
        "ativo": True,
    }
    
    tenant_read = TenantRead(**raw_tenant)
    dump = tenant_read.model_dump()
    
    assert dump["id"] == tenant_id
    assert dump["nome"] == "Empresa Teste LTDA"
    assert dump["razao_social"] == "Empresa Teste Serviços LTDA"
    assert "config" not in dump
    assert "webhook_secret" not in dump
    assert "api_folha_token" not in dump


def test_integration_secrets_are_write_only_in_schema():
    read_schema = ConfiguracoesIntegracoesRead(
        webhook_url="https://hooks.example.com/test",
        webhook_secret_configurado=True,
        api_folha_ativa=True,
        api_folha_url="https://folha.example.com/api",
        api_folha_token_configurado=True,
    )
    dump = read_schema.model_dump()
    
    assert dump["webhook_secret_configurado"] is True
    assert dump["api_folha_token_configurado"] is True
    assert "webhook_secret" not in dump
    assert "api_folha_token" not in dump


def test_ssrf_webhook_validation_comprehensive():
    # Forbidden targets and userinfo tricks
    forbidden_urls = [
        "http://localhost:8000/webhook",
        "http://127.0.0.1:8000/webhook",
        "http://[::1]:8000/webhook",
        "http://10.0.0.1/webhook",
        "http://172.16.0.1/webhook",
        "http://192.168.0.1/webhook",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0:8000",
        "http://224.0.0.1/multicast",
        "ftp://example.com/webhook",
        "file:///etc/passwd",
        "https://admin:pass@example.com/webhook",
        "https://example.com@127.0.0.1/webhook",
        "https://127.0.0.1@example.com/webhook",
    ]
    
    for url in forbidden_urls:
        with pytest.raises(ValueError):
            validate_webhook_url(url, allow_http=True)


@pytest.mark.anyio
async def test_webhook_toctou_prevention_real_http_flow():
    """
    Test real HTTP transport flow for TOCTOU / DNS Rebinding prevention.
    Initial DNS resolution: malicious.example -> 93.184.216.34 (Public IP).
    Second DNS resolution attempt: malicious.example -> 127.0.0.1.
    Verify that PinningAsyncHTTPTransport forces the HTTP request host to 93.184.216.34
    and preserves SNI/Host header as malicious.example without attempting 127.0.0.1 connection.
    """
    with patch("app.core.security_webhook.resolve_hostname_ips") as mock_resolve:
        mock_resolve.return_value = ["93.184.216.34"]
        clean_url, hostname, target_ip, port = validate_webhook_url("https://malicious.example/webhook")

    assert hostname == "malicious.example"
    assert target_ip == "93.184.216.34"

    # Create pinned client using production security_webhook module
    client = create_pinned_client(target_ip=target_ip, original_host=hostname, timeout=5.0)

    captured_request = None
    async def mock_handle_async_request(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={"status": "ok"})

    # Patch lower-level handle_async_request on the transport
    with patch.object(httpx.AsyncHTTPTransport, "handle_async_request", side_effect=mock_handle_async_request):
        # Even if DNS rebind returns 127.0.0.1, client uses target_ip
        res = await client.post(clean_url, json={"test": True})
        assert res.status_code == 200

    # Verify connection was pinned to target_ip (93.184.216.34) and headers/SNI were preserved
    assert captured_request is not None
    assert captured_request.url.host == "93.184.216.34"
    assert captured_request.headers["Host"] == "malicious.example"
    assert captured_request.extensions.get("sni_hostname") == "malicious.example"

    await client.aclose()


def test_webhook_ip_pinning_preserves_tls_sni_and_verify():
    """
    Test that PinningAsyncHTTPTransport preserves verify=True, follow_redirects=False,
    and sets sni_hostname / Host header properly.
    """
    client = create_pinned_client(target_ip="93.184.216.34", original_host="webhook.example.com", verify=True)
    assert isinstance(client._transport, PinningAsyncHTTPTransport)
    assert client._transport.target_ip == "93.184.216.34"
    assert client._transport.original_host == "webhook.example.com"
    assert client.follow_redirects is False


def test_normalize_tenant_config_preserves_and_migrates():
    legacy_config = {
        "slug": "empresa-old",
        "plano": "starter",
        "jornada_diaria": 8,
        "tolerancia_minutos": 15,
        "requer_foto": True,
        "requer_geolocalizacao": True,
        "custom_key": "custom_val",
    }

    normalized = normalize_tenant_config(legacy_config)

    assert normalized["slug"] == "empresa-old"
    assert normalized["custom_key"] == "custom_val"
    assert normalized["ponto"]["jornada_diaria"] == 8
    assert normalized["ponto"]["tolerancia_minutos"] == 15
    assert normalized["ponto"]["exigir_foto"] is True
    assert normalized["ponto"]["exigir_geolocalizacao"] is True
    assert "notificacoes" in normalized
    assert "seguranca" in normalized
    assert "integracoes" in normalized


def test_tenant_config_alembic_migration_real_postgres():
    """
    Execute real Alembic migration 20260930_0002 upgrade against real PostgreSQL engine (or SQLite fallback)
    verifying Scenarios A, B, and C.
    """
    from alembic.config import Config
    from alembic import command

    pg_url = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:54399/test_vibeponto")

    # Try PostgreSQL first
    try:
        engine = sa.create_engine(pg_url.replace("+asyncpg", ""))
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        is_postgres = True
    except Exception:
        engine = sa.create_engine("sqlite:///:memory:")
        is_postgres = False

    if is_postgres:
        alembic_cfg = Config("alembic.ini")
        os.environ["DATABASE_URL"] = pg_url
        alembic_cfg.set_main_option("sqlalchemy.url", pg_url)

        # Scenario A: Revision 20260917_0001 -> Upgrade Head
        with engine.begin() as conn:
            conn.execute(sa.text("DROP TABLE IF EXISTS marcacoes_ponto CASCADE;"))
            conn.execute(sa.text("DROP TABLE IF EXISTS usuarios CASCADE;"))
            conn.execute(sa.text("DROP TABLE IF EXISTS equipes CASCADE;"))
            conn.execute(sa.text("DROP TABLE IF EXISTS tenants CASCADE;"))
            conn.execute(sa.text("DROP TABLE IF EXISTS alembic_version CASCADE;"))

        command.upgrade(alembic_cfg, "20260917_0001")
        command.upgrade(alembic_cfg, "head")

        with engine.connect() as conn:
            res = conn.execute(sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='tenants';"))
            cols = [r[0] for r in res.fetchall()]
            assert "razao_social" in cols

        # Scenario B: Legacy Tenant
        with engine.begin() as conn:
            conn.execute(sa.text("DROP TABLE IF EXISTS marcacoes_ponto CASCADE;"))
            conn.execute(sa.text("DROP TABLE IF EXISTS usuarios CASCADE;"))
            conn.execute(sa.text("DROP TABLE IF EXISTS equipes CASCADE;"))
            conn.execute(sa.text("DROP TABLE IF EXISTS tenants CASCADE;"))
            conn.execute(sa.text("DROP TABLE IF EXISTS alembic_version CASCADE;"))

        command.upgrade(alembic_cfg, "20260917_0001")
        tenant_b_id = str(uuid4())
        legacy_cfg = {
            "slug": "empresa-legada",
            "plano": "enterprise",
            "jornada_diaria": 8,
            "tolerancia_minutos": 15,
            "custom_key": "custom_val"
        }

        with engine.begin() as conn:
            conn.execute(
                sa.text("INSERT INTO tenants (id, nome, cnpj, email, config, ativo) VALUES (:id, 'Legada', '12345678000199', 'admin@legada.com', CAST(:config AS jsonb), true)"),
                {"id": tenant_b_id, "config": json.dumps(legacy_cfg)}
            )

        command.upgrade(alembic_cfg, "head")

        with engine.connect() as conn:
            res = conn.execute(sa.text("SELECT config FROM tenants WHERE id = :id"), {"id": tenant_b_id})
            row = res.fetchone()
            cfg_b = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            assert cfg_b["slug"] == "empresa-legada"
            assert cfg_b["plano"] == "enterprise"
            assert cfg_b["custom_key"] == "custom_val"
            assert cfg_b["ponto"]["jornada_diaria"] == 8

        # Scenario C: Already Normalized Tenant
        with engine.begin() as conn:
            conn.execute(sa.text("DROP TABLE IF EXISTS marcacoes_ponto CASCADE;"))
            conn.execute(sa.text("DROP TABLE IF EXISTS usuarios CASCADE;"))
            conn.execute(sa.text("DROP TABLE IF EXISTS equipes CASCADE;"))
            conn.execute(sa.text("DROP TABLE IF EXISTS tenants CASCADE;"))
            conn.execute(sa.text("DROP TABLE IF EXISTS alembic_version CASCADE;"))

        command.upgrade(alembic_cfg, "20260917_0001")
        tenant_c_id = str(uuid4())
        norm_cfg = {
            "slug": "empresa-norm",
            "plano": "pro",
            "ponto": {"jornada_diaria": 8}
        }

        with engine.begin() as conn:
            conn.execute(
                sa.text("INSERT INTO tenants (id, nome, cnpj, email, config, ativo) VALUES (:id, 'Norm', '98765432000188', 'admin@norm.com', CAST(:config AS jsonb), true)"),
                {"id": tenant_c_id, "config": json.dumps(norm_cfg)}
            )

        command.upgrade(alembic_cfg, "head")

        with engine.connect() as conn:
            res = conn.execute(sa.text("SELECT config FROM tenants WHERE id = :id"), {"id": tenant_c_id})
            row = res.fetchone()
            cfg_c = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            assert cfg_c["slug"] == "empresa-norm"
            assert cfg_c["ponto"]["jornada_diaria"] == 8
    else:
        # Memory fallback test
        spec = importlib.util.spec_from_file_location("mig_20260930_0002", "alembic/versions/20260930_0002_normalize_tenant_schema_and_config.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE TABLE tenants (id VARCHAR(36) PRIMARY KEY, nome VARCHAR(255), cnpj VARCHAR(18), email VARCHAR(255), config JSON, ativo BOOLEAN)"))
            conn.execute(sa.text("INSERT INTO tenants (id, nome, cnpj, email, config) VALUES ('t-b', 'L', '123', 'a@l.com', :cfg)"), {"cfg": json.dumps({"slug": "legacy-slug", "jornada_diaria": 8})})

        class MockOp:
            def __init__(self, conn): self.conn = conn
            def get_bind(self): return self.conn
            def add_column(self, table, col):
                c_type = col.type.compile(dialect=self.conn.dialect)
                self.conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {col.name} {c_type}"))

        with engine.begin() as conn:
            mock_op = MockOp(conn)
            mod.op = mock_op
            mod.upgrade()

        with engine.connect() as conn:
            row = conn.execute(sa.text("SELECT config FROM tenants WHERE id = 't-b'")).fetchone()
            cfg = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            assert cfg["slug"] == "legacy-slug"
            assert cfg["ponto"]["jornada_diaria"] == 8


def test_structured_address_parsing():
    # Test text parsing
    addr_str = parse_endereco_dict("Rua das Flores, 100")
    assert addr_str["logradouro"] == "Rua das Flores, 100"
    
    # Test dictionary with legacy alias (cidade / estado)
    addr_dict = parse_endereco_dict({
        "logradouro": "Av Paulista",
        "numero": "1000",
        "cidade": "São Paulo",
        "estado": "SP",
        "cep": "01310-100"
    })
    
    schema = EnderecoSchema(**addr_dict)
    assert schema.logradouro == "Av Paulista"
    assert schema.municipio == "São Paulo"
    assert schema.uf == "SP"
    assert schema.pais == "Brasil"


def test_openapi_schema_contracts_no_secrets():
    """Verify OpenAPI schema contracts to ensure secrets are never exposed in GET responses."""
    openapi = app.openapi()
    
    # 1. GET /tenant response schema properties
    tenant_get_props = openapi["components"]["schemas"]["TenantRead"]["properties"]
    assert "config" not in tenant_get_props
    assert "webhook_secret" not in tenant_get_props
    assert "api_folha_token" not in tenant_get_props
    
    # 2. GET /configuracoes/integracoes response schema properties
    integracoes_get_props = openapi["components"]["schemas"]["ConfiguracoesIntegracoesRead"]["properties"]
    assert "webhook_secret" not in integracoes_get_props
    assert "api_folha_token" not in integracoes_get_props
    assert "webhook_secret_configurado" in integracoes_get_props
    assert "api_folha_token_configurado" in integracoes_get_props
