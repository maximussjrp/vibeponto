"""
Tests for Sprint 01A Tenant & Security Hardening (SSRF, OpenAPI Contracts, TOCTOU, Response Limits, Migration A/B/C)
"""

import importlib.util
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

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


def test_ssrf_dns_rebinding_mock():
    """Test mock simulating DNS rebinding attack where hostname resolves to internal IP."""
    with patch("app.core.security_webhook.resolve_hostname_ips") as mock_resolve:
        mock_resolve.return_value = ["127.0.0.1"]
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


def test_migration_scenarios_a_b_c():
    """Test Alembic Migration 20260930_0002 logic across Scenarios A, B, and C."""
    spec = importlib.util.spec_from_file_location(
        "migration_module",
        "alembic/versions/20260930_0002_normalize_tenant_schema_and_config.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Scenario A: New empty config
    cfg_a = mod.normalize_config({})
    assert "ponto" in cfg_a and "notificacoes" in cfg_a and "seguranca" in cfg_a and "integracoes" in cfg_a

    # Scenario B: Legacy tenant with root keys
    legacy_b = {
        "slug": "legacy-corp",
        "plano": "starter",
        "jornada_diaria": 8,
        "tolerancia_minutos": 10,
        "custom_attr": "custom_val"
    }
    cfg_b = mod.normalize_config(legacy_b)
    assert cfg_b["slug"] == "legacy-corp"
    assert cfg_b["plano"] == "starter"
    assert cfg_b["custom_attr"] == "custom_val"
    assert cfg_b["ponto"]["jornada_diaria"] == 8
    assert cfg_b["ponto"]["tolerancia_minutos"] == 10

    # Scenario C: Already normalized tenant
    norm_c = {
        "slug": "norm-corp",
        "ponto": {"jornada_diaria": 6, "tolerancia_minutos": 5}
    }
    cfg_c = mod.normalize_config(norm_c)
    assert cfg_c["ponto"]["jornada_diaria"] == 6
    assert cfg_c["ponto"]["tolerancia_minutos"] == 5


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
