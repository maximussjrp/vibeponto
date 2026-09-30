"""Router de tenant (empresa) e configurações."""

import logging
from typing import Annotated, Any, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUser,
    RequireAdmin,
    TenantContext,
    get_current_user,
    get_db,
    get_tenant_context,
)
from app.core.security_webhook import validate_webhook_url
from app.models import Tenant, Usuario, Equipe, MarcacaoPonto, UserStatus


logger = logging.getLogger("app.api.tenant")

router = APIRouter(tags=["Empresa"])


# ============================================================================
# SCHEMAS
# ============================================================================

class EnderecoSchema(BaseModel):
    """Schema de endereço corporativo estruturado."""
    cep: Optional[str] = None
    logradouro: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    uf: Optional[str] = None
    pais: Optional[str] = "Brasil"


class TenantRead(BaseModel):
    """Schema de leitura do tenant (dados corporativos não sensíveis)."""
    id: UUID
    nome: str
    razao_social: Optional[str] = None
    cnpj: str
    email: str
    telefone: Optional[str] = None
    endereco: Optional[EnderecoSchema] = None
    slug: Optional[str] = None
    plano: Optional[str] = None
    ativo: bool

    class Config:
        from_attributes = True


class TenantUpdate(BaseModel):
    """Schema de atualização dos dados corporativos do tenant."""
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    razao_social: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    telefone: Optional[str] = None
    endereco: Optional[Union[EnderecoSchema, dict, str]] = None


class TenantEstatisticas(BaseModel):
    """Estatísticas do tenant."""
    total_usuarios: int
    usuarios_ativos: int
    total_equipes: int
    marcacoes_hoje: int
    alertas_pendentes: int


class ConfiguracoesPonto(BaseModel):
    """Configurações de ponto."""
    tolerancia_minutos: int = 10
    intervalo_minimo: int = 60
    jornada_diaria: int = 8
    jornada_semanal: int = 44
    hora_extra_automatica: bool = False
    banco_horas_ativo: bool = False
    banco_horas_limite: int = 40
    exigir_foto: bool = True
    exigir_geolocalizacao: bool = True
    permitir_offline: bool = True
    notificar_atraso: bool = True
    notificar_hora_extra: bool = True


class ConfiguracoesNotificacoes(BaseModel):
    """Configurações de notificações."""
    email_ativo: bool = True
    push_ativo: bool = True
    notificar_marcacao: bool = True
    notificar_aprovacao: bool = True
    notificar_documento: bool = True
    notificar_alerta: bool = True
    horario_lembrete_entrada: Optional[str] = None
    horario_lembrete_saida: Optional[str] = None


class ConfiguracoesSeguranca(BaseModel):
    """Configurações de segurança."""
    mfa_obrigatorio: bool = False
    sessao_unica: bool = False
    tempo_sessao: int = 480
    tentativas_login: int = 5
    bloquear_dispositivo: bool = False
    ips_permitidos: Optional[list[str]] = None


class ConfiguracoesIntegracoesRead(BaseModel):
    """Configurações de integrações para leitura (sem segredos)."""
    webhook_url: Optional[str] = None
    webhook_secret_configurado: bool = False
    api_folha_ativa: bool = False
    api_folha_url: Optional[str] = None
    api_folha_token_configurado: bool = False


class ConfiguracoesIntegracoesUpdate(BaseModel):
    """Configurações de integrações para atualização (escrita apenas)."""
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None  # Write-only
    api_folha_ativa: Optional[bool] = None
    api_folha_url: Optional[str] = None
    api_folha_token: Optional[str] = None  # Write-only


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_endereco_dict(raw_endereco: Any) -> Optional[dict]:
    """Parse address input into a clean dictionary for EnderecoSchema."""
    if not raw_endereco:
        return None
    if isinstance(raw_endereco, str):
        return {"logradouro": raw_endereco, "pais": "Brasil"}
    if isinstance(raw_endereco, dict):
        d = dict(raw_endereco)
        if "cidade" in d and "municipio" not in d:
            d["municipio"] = d["cidade"]
        if "estado" in d and "uf" not in d:
            d["uf"] = d["estado"]
        return d
    if isinstance(raw_endereco, EnderecoSchema):
        return raw_endereco.model_dump()
    return None


def normalize_tenant_config(config: Optional[dict]) -> dict:
    """Normalizar a estrutura do objeto JSON config do tenant."""
    if config is None:
        config = {}

    cfg = dict(config)
    ponto = dict(cfg.get("ponto") or {})
    notificacoes = dict(cfg.get("notificacoes") or {})
    seguranca = dict(cfg.get("seguranca") or {})
    integracoes = dict(cfg.get("integracoes") or {})

    # Migrar chaves antigas de raiz se não existirem na seção ponto
    if "jornada_diaria" in cfg and "jornada_diaria" not in ponto:
        ponto["jornada_diaria"] = cfg["jornada_diaria"]
    if "tolerancia_minutos" in cfg and "tolerancia_minutos" not in ponto:
        ponto["tolerancia_minutos"] = cfg["tolerancia_minutos"]
    if "requer_foto" in cfg and "exigir_foto" not in ponto:
        ponto["exigir_foto"] = cfg["requer_foto"]
    if "requer_geolocalizacao" in cfg and "exigir_geolocalizacao" not in ponto:
        ponto["exigir_geolocalizacao"] = cfg["requer_geolocalizacao"]
    if "permite_hora_extra" in cfg and "hora_extra_automatica" not in ponto:
        ponto["hora_extra_automatica"] = cfg["permite_hora_extra"]

    cfg["ponto"] = ponto
    cfg["notificacoes"] = notificacoes
    cfg["seguranca"] = seguranca
    cfg["integracoes"] = integracoes
    return cfg


def get_config_section(config: dict, section: str, default_model) -> dict:
    """Extrair seção de configuração com valores padrão e normalização."""
    normalized = normalize_tenant_config(config)
    section_data = normalized.get(section, {})
    default_data = default_model().model_dump()
    return {**default_data, **section_data}


def update_config_section(config: dict, section: str, data: dict) -> dict:
    """Atualizar seção de configuração preservando chaves existentes."""
    normalized = normalize_tenant_config(config)
    current_section = normalized.get(section, {})
    normalized[section] = {**current_section, **data}
    return normalized


# ============================================================================
# ROTAS - TENANT
# ============================================================================

@router.get("/tenant", response_model=TenantRead)
async def get_tenant(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Buscar dados do tenant atual (somente dados corporativos públicos/não sensíveis)."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_obj = result.scalar_one_or_none()

    if not tenant_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant não encontrado",
        )

    config = tenant_obj.config or {}
    slug = config.get("slug")
    plano = config.get("plano")
    endereco_parsed = parse_endereco_dict(tenant_obj.endereco)

    return TenantRead(
        id=tenant_obj.id,
        nome=tenant_obj.nome,
        razao_social=tenant_obj.razao_social or tenant_obj.nome,
        cnpj=tenant_obj.cnpj,
        email=tenant_obj.email,
        telefone=tenant_obj.telefone,
        endereco=EnderecoSchema(**endereco_parsed) if endereco_parsed else None,
        slug=slug,
        plano=plano,
        ativo=tenant_obj.ativo,
    )


@router.patch("/tenant", response_model=TenantRead)
async def update_tenant(
    data: TenantUpdate,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualizar dados corporativos do tenant (somente Admin DP)."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_obj = result.scalar_one_or_none()

    if not tenant_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant não encontrado",
        )

    update_data = data.model_dump(exclude_unset=True)
    if "endereco" in update_data and update_data["endereco"] is not None:
        update_data["endereco"] = parse_endereco_dict(update_data["endereco"])

    for field, value in update_data.items():
        if hasattr(tenant_obj, field):
            setattr(tenant_obj, field, value)

    await db.commit()
    await db.refresh(tenant_obj)

    config = tenant_obj.config or {}
    slug = config.get("slug")
    plano = config.get("plano")
    endereco_parsed = parse_endereco_dict(tenant_obj.endereco)

    return TenantRead(
        id=tenant_obj.id,
        nome=tenant_obj.nome,
        razao_social=tenant_obj.razao_social or tenant_obj.nome,
        cnpj=tenant_obj.cnpj,
        email=tenant_obj.email,
        telefone=tenant_obj.telefone,
        endereco=EnderecoSchema(**endereco_parsed) if endereco_parsed else None,
        slug=slug,
        plano=plano,
        ativo=tenant_obj.ativo,
    )


@router.get("/tenant/estatisticas", response_model=TenantEstatisticas)
async def get_estatisticas(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Buscar estatísticas corporativas do tenant."""
    from datetime import date

    # Total usuários
    total_usuarios = await db.execute(
        select(func.count(Usuario.id)).where(Usuario.tenant_id == tenant.tenant_id)
    )

    # Usuários ativos (correção para UserStatus.ACTIVE / "active")
    usuarios_ativos = await db.execute(
        select(func.count(Usuario.id)).where(
            Usuario.tenant_id == tenant.tenant_id,
            Usuario.status == UserStatus.ACTIVE,
        )
    )

    # Total equipes
    total_equipes = await db.execute(
        select(func.count(Equipe.id)).where(Equipe.tenant_id == tenant.tenant_id)
    )

    # Marcações hoje
    hoje = date.today()
    marcacoes_hoje = await db.execute(
        select(func.count(MarcacaoPonto.id)).where(
            MarcacaoPonto.tenant_id == tenant.tenant_id,
            func.date(MarcacaoPonto.timestamp_servidor) == hoje,
        )
    )

    return TenantEstatisticas(
        total_usuarios=total_usuarios.scalar_one() or 0,
        usuarios_ativos=usuarios_ativos.scalar_one() or 0,
        total_equipes=total_equipes.scalar_one() or 0,
        marcacoes_hoje=marcacoes_hoje.scalar_one() or 0,
        alertas_pendentes=0,  # Não implementado no momento
    )


# ============================================================================
# ROTAS - CONFIGURAÇÕES
# ============================================================================

@router.get("/configuracoes/ponto", response_model=ConfiguracoesPonto)
async def get_configuracoes_ponto(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Buscar configurações de ponto."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_obj = result.scalar_one_or_none()

    config = tenant_obj.config or {} if tenant_obj else {}
    return ConfiguracoesPonto(**get_config_section(config, "ponto", ConfiguracoesPonto))


@router.patch("/configuracoes/ponto", response_model=ConfiguracoesPonto)
async def update_configuracoes_ponto(
    data: ConfiguracoesPonto,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualizar configurações de ponto."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_obj = result.scalar_one_or_none()

    if not tenant_obj:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    tenant_obj.config = update_config_section(
        tenant_obj.config or {},
        "ponto",
        data.model_dump()
    )

    await db.commit()
    await db.refresh(tenant_obj)

    return data


@router.get("/configuracoes/notificacoes", response_model=ConfiguracoesNotificacoes)
async def get_configuracoes_notificacoes(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Buscar configurações de notificações."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_obj = result.scalar_one_or_none()

    config = tenant_obj.config or {} if tenant_obj else {}
    return ConfiguracoesNotificacoes(**get_config_section(config, "notificacoes", ConfiguracoesNotificacoes))


@router.patch("/configuracoes/notificacoes", response_model=ConfiguracoesNotificacoes)
async def update_configuracoes_notificacoes(
    data: ConfiguracoesNotificacoes,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualizar configurações de notificações."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_obj = result.scalar_one_or_none()

    if not tenant_obj:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    tenant_obj.config = update_config_section(
        tenant_obj.config or {},
        "notificacoes",
        data.model_dump()
    )

    await db.commit()
    await db.refresh(tenant_obj)

    return data


@router.get("/configuracoes/seguranca", response_model=ConfiguracoesSeguranca)
async def get_configuracoes_seguranca(
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Buscar configurações de segurança."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_obj = result.scalar_one_or_none()

    config = tenant_obj.config or {} if tenant_obj else {}
    return ConfiguracoesSeguranca(**get_config_section(config, "seguranca", ConfiguracoesSeguranca))


@router.patch("/configuracoes/seguranca", response_model=ConfiguracoesSeguranca)
async def update_configuracoes_seguranca(
    data: ConfiguracoesSeguranca,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualizar configurações de segurança."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_obj = result.scalar_one_or_none()

    if not tenant_obj:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    tenant_obj.config = update_config_section(
        tenant_obj.config or {},
        "seguranca",
        data.model_dump()
    )

    await db.commit()
    await db.refresh(tenant_obj)

    return data


@router.get("/configuracoes/integracoes", response_model=ConfiguracoesIntegracoesRead)
async def get_configuracoes_integracoes(
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Buscar configurações de integrações (sem segredos)."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_obj = result.scalar_one_or_none()

    config = tenant_obj.config or {} if tenant_obj else {}
    integracoes = config.get("integracoes", {})

    return ConfiguracoesIntegracoesRead(
        webhook_url=integracoes.get("webhook_url"),
        webhook_secret_configurado=bool(integracoes.get("webhook_secret")),
        api_folha_ativa=bool(integracoes.get("api_folha_ativa", False)),
        api_folha_url=integracoes.get("api_folha_url"),
        api_folha_token_configurado=bool(integracoes.get("api_folha_token")),
    )


@router.patch("/configuracoes/integracoes", response_model=ConfiguracoesIntegracoesRead)
async def update_configuracoes_integracoes(
    data: ConfiguracoesIntegracoesUpdate,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualizar configurações de integrações (preservando segredos existentes)."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_obj = result.scalar_one_or_none()

    if not tenant_obj:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    config = normalize_tenant_config(tenant_obj.config or {})
    integracoes = dict(config.get("integracoes", {}))

    if data.webhook_url is not None:
        integracoes["webhook_url"] = data.webhook_url
    if data.webhook_secret is not None and data.webhook_secret != "":
        integracoes["webhook_secret"] = data.webhook_secret
    if data.api_folha_ativa is not None:
        integracoes["api_folha_ativa"] = data.api_folha_ativa
    if data.api_folha_url is not None:
        integracoes["api_folha_url"] = data.api_folha_url
    if data.api_folha_token is not None and data.api_folha_token != "":
        integracoes["api_folha_token"] = data.api_folha_token

    config["integracoes"] = integracoes
    tenant_obj.config = config

    await db.commit()
    await db.refresh(tenant_obj)

    return ConfiguracoesIntegracoesRead(
        webhook_url=integracoes.get("webhook_url"),
        webhook_secret_configurado=bool(integracoes.get("webhook_secret")),
        api_folha_ativa=bool(integracoes.get("api_folha_ativa", False)),
        api_folha_url=integracoes.get("api_folha_url"),
        api_folha_token_configurado=bool(integracoes.get("api_folha_token")),
    )


@router.post("/configuracoes/integracoes/testar-webhook")
async def testar_webhook(
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Testar configuração de webhook de forma segura contra SSRF."""
    import httpx

    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_obj = result.scalar_one_or_none()

    if not tenant_obj:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    config = tenant_obj.config or {}
    integracoes = config.get("integracoes", {})
    webhook_url = integracoes.get("webhook_url")

    if not webhook_url:
        return {"sucesso": False, "mensagem": "URL do webhook não configurada"}

    try:
        validate_webhook_url(webhook_url)
    except ValueError as val_err:
        logger.warning(f"Teste de webhook bloqueado por validação de segurança: {str(val_err)}")
        return {"sucesso": False, "mensagem": "URL de webhook inválida ou não permitida"}

    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=5.0) as client:
            async with client.stream(
                "POST",
                webhook_url,
                json={"evento": "teste", "tenant_id": str(tenant.tenant_id)},
            ) as response:
                status_code = response.status_code

                content_length = response.headers.get("content-length")
                if content_length and content_length.isdigit() and int(content_length) > 10240:
                    return {"sucesso": False, "mensagem": "Resposta do webhook excede o tamanho limite permitido"}

                total_bytes = 0
                async for chunk in response.aiter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > 10240:
                        return {"sucesso": False, "mensagem": "Resposta do webhook excede o tamanho limite permitido"}

                if response.is_success:
                    return {"sucesso": True, "mensagem": f"Webhook respondeu com status {status_code}"}
                else:
                    return {"sucesso": False, "mensagem": f"Webhook retornou status {status_code}"}
    except Exception as e:
        logger.error(f"Erro ao disparar webhook de teste: {type(e).__name__}")
        return {"sucesso": False, "mensagem": "Falha ao conectar com o webhook"}
