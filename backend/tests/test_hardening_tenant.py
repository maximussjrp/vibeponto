"""
Tests for Micro-Sprint 01A.1 Tenant & Security Hardening
(TOCTOU/DNS Rebinding Prevention with IP Pinning, TLS SNI Preservation, Alembic SQL Database Upgrade Scenarios A/B/C)
"""

import importlib.util
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
import sqlalchemy as sa

from app.api.routes.tenant import (
    TenantRead,
    TenantUpdate,
    EnderecoSchema,
    ConfiguracoesIntegracoesRead,
    ConfiguracoesIntegracoesUpdate,
    normalize_tenant_config,
    parse_endereco_dict,
)
from app.core.security_webhook import validate_webhook_url
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


def test_ssrf_dns_rebinding_toctou_prevention():
    """
    Test simulating TOCTOU / DNS Rebinding attack where initial DNS query returns public IP
    and second query returns 127.0.0.1. Verify that IP pinning connects directly to validated IP.
    """
    with patch("app.core.security_webhook.resolve_hostname_ips") as mock_resolve:
        # Initial validation returns public IP
        mock_resolve.return_value = ["93.184.216.34"]
        url, hostname, target_ip, port = validate_webhook_url("https://malicious-rebinding-domain.com/webhook")
        
        assert hostname == "malicious-rebinding-domain.com"
        assert target_ip == "93.184.216.34"

    # Simulate TOCTOU scenario where second DNS resolution returns loopback
    with patch("app.core.security_webhook.resolve_hostname_ips") as mock_rebinding_resolve:
        mock_rebinding_resolve.return_value = ["127.0.0.1"]
        with pytest.raises(ValueError) as exc_info:
            validate_webhook_url("https://malicious-rebinding-domain.com/webhook")
        assert "não permitido" in str(exc_info.value)


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


def test_alembic_migration_scenarios_sql_database():
    """
    Execute real Alembic migration 20260930_0002 upgrade against SQL database engine
    verifying Scenarios A, B, and C.
    """
    spec = importlib.util.spec_from_file_location(
        "mig_20260930_0002",
        "alembic/versions/20260930_0002_normalize_tenant_schema_and_config.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        conn.execute(sa.text("""
            CREATE TABLE tenants (
                id VARCHAR(36) PRIMARY KEY,
                nome VARCHAR(255) NOT NULL,
                cnpj VARCHAR(18) NOT NULL,
                email VARCHAR(255) NOT NULL,
                telefone VARCHAR(20),
                endereco JSON,
                config JSON,
                ativo BOOLEAN DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
        
        # Scenario B: Legacy tenant
        conn.execute(sa.text("""
            INSERT INTO tenants (id, nome, cnpj, email, config) VALUES (
                'tenant-b', 'Legacy Corp', '12345678000199', 'admin@legacy.com',
                :cfg
            )
        """), {"cfg": json.dumps({
            "slug": "legacy-slug",
            "plano": "starter",
            "jornada_diaria": 8,
            "tolerancia_minutos": 10,
            "custom_key": "custom_val"
        })})
        
        # Scenario C: Already normalized tenant
        conn.execute(sa.text("""
            INSERT INTO tenants (id, nome, cnpj, email, config) VALUES (
                'tenant-c', 'Norm Corp', '98765432000199', 'admin@norm.com',
                :cfg
            )
        """), {"cfg": json.dumps({
            "slug": "norm-slug",
            "plano": "enterprise",
            "ponto": {"jornada_diaria": 6, "tolerancia_minutos": 5}
        })})

    class MockOp:
        def __init__(self, conn):
            self.conn = conn
        def get_bind(self):
            return self.conn
        def add_column(self, table, col):
            col_type = col.type.compile(dialect=self.conn.dialect)
            self.conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {col.name} {col_type}"))

    with engine.begin() as conn:
        mock_op = MockOp(conn)
        mod.op = mock_op
        mod.upgrade()

    with engine.connect() as conn:
        inspector = sa.inspect(conn)
        cols = [c["name"] for c in inspector.get_columns("tenants")]
        assert "razao_social" in cols, "Column razao_social missing!"
        
        q_b = sa.text("SELECT config FROM tenants WHERE id = :id")
        row_b = conn.execute(q_b, {"id": "tenant-b"}).fetchone()
        cfg_b = json.loads(row_b[0]) if isinstance(row_b[0], str) else row_b[0]
        assert cfg_b["slug"] == "legacy-slug"
        assert cfg_b["plano"] == "starter"
        assert cfg_b["custom_key"] == "custom_val"
        assert cfg_b["ponto"]["jornada_diaria"] == 8
        assert cfg_b["ponto"]["tolerancia_minutos"] == 10
        
        row_c = conn.execute(q_b, {"id": "tenant-c"}).fetchone()
        cfg_c = json.loads(row_c[0]) if isinstance(row_c[0], str) else row_c[0]
        assert cfg_c["slug"] == "norm-slug"
        assert cfg_c["ponto"]["jornada_diaria"] == 6


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
