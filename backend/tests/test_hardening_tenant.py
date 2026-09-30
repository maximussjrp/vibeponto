"""
Tests for Sprint 01A Tenant & Security Hardening
"""

import pytest
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


def test_ssrf_webhook_validation():
    # Forbidden targets
    forbidden_urls = [
        "http://localhost:8000/webhook",
        "http://127.0.0.1:8000/webhook",
        "http://[::1]:8000/webhook",
        "http://10.0.0.1/webhook",
        "http://172.16.0.1/webhook",
        "http://192.168.0.1/webhook",
        "http://169.254.169.254/latest/meta-data/",
        "ftp://example.com/webhook",
    ]
    
    for url in forbidden_urls:
        with pytest.raises(ValueError):
            validate_webhook_url(url, allow_http=True)


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
