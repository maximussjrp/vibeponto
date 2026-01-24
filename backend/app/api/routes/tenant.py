"""Router de tenant (empresa) e configurações."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
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
from app.models import Tenant, Usuario, Equipe, MarcacaoPonto


router = APIRouter(tags=["Empresa"])


# ============================================================================
# SCHEMAS
# ============================================================================

class TenantRead(BaseModel):
    """Schema de leitura do tenant."""
    id: UUID
    nome: str
    cnpj: str
    email: str
    telefone: Optional[str] = None
    endereco: Optional[dict] = None
    config: Optional[dict] = None
    ativo: bool

    class Config:
        from_attributes = True


class TenantUpdate(BaseModel):
    """Schema de atualização do tenant."""
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[str] = None
    telefone: Optional[str] = None
    endereco: Optional[dict] = None


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


class ConfiguracoesIntegracoes(BaseModel):
    """Configurações de integrações."""
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    api_folha_ativa: bool = False
    api_folha_url: Optional[str] = None
    api_folha_token: Optional[str] = None


# ============================================================================
# ROTAS - TENANT
# ============================================================================

@router.get("/tenant", response_model=TenantRead)
async def get_tenant(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Buscar dados do tenant atual."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_obj = result.scalar_one_or_none()
    
    if not tenant_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant não encontrado",
        )
    
    return TenantRead.model_validate(tenant_obj)


@router.patch("/tenant", response_model=TenantRead)
async def update_tenant(
    data: TenantUpdate,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualizar dados do tenant."""
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
    for field, value in update_data.items():
        setattr(tenant_obj, field, value)
    
    await db.commit()
    await db.refresh(tenant_obj)
    
    return TenantRead.model_validate(tenant_obj)


@router.get("/tenant/estatisticas", response_model=TenantEstatisticas)
async def get_estatisticas(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Buscar estatísticas do tenant."""
    from datetime import datetime, date
    
    # Total usuários
    total_usuarios = await db.execute(
        select(func.count(Usuario.id)).where(Usuario.tenant_id == tenant.tenant_id)
    )
    
    # Usuários ativos
    usuarios_ativos = await db.execute(
        select(func.count(Usuario.id)).where(
            Usuario.tenant_id == tenant.tenant_id,
            Usuario.status == "ativo",
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
        alertas_pendentes=0,  # TODO: Implementar contador de alertas
    )


# ============================================================================
# ROTAS - CONFIGURAÇÕES
# ============================================================================

def get_config_section(config: dict, section: str, default_model) -> dict:
    """Extrair seção de configuração com valores padrão."""
    section_data = config.get(section, {})
    default_data = default_model().model_dump()
    return {**default_data, **section_data}


def update_config_section(config: dict, section: str, data: dict) -> dict:
    """Atualizar seção de configuração."""
    if config is None:
        config = {}
    config[section] = {**config.get(section, {}), **data}
    return config


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


@router.get("/configuracoes/integracoes", response_model=ConfiguracoesIntegracoes)
async def get_configuracoes_integracoes(
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Buscar configurações de integrações."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_obj = result.scalar_one_or_none()
    
    config = tenant_obj.config or {} if tenant_obj else {}
    return ConfiguracoesIntegracoes(**get_config_section(config, "integracoes", ConfiguracoesIntegracoes))


@router.patch("/configuracoes/integracoes", response_model=ConfiguracoesIntegracoes)
async def update_configuracoes_integracoes(
    data: ConfiguracoesIntegracoes,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualizar configurações de integrações."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_obj = result.scalar_one_or_none()
    
    if not tenant_obj:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    
    tenant_obj.config = update_config_section(
        tenant_obj.config or {}, 
        "integracoes", 
        data.model_dump()
    )
    
    await db.commit()
    await db.refresh(tenant_obj)
    
    return data


@router.post("/configuracoes/integracoes/testar-webhook")
async def testar_webhook(
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Testar configuração de webhook."""
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
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json={"evento": "teste", "tenant_id": str(tenant.tenant_id)},
                timeout=10.0,
            )
            if response.is_success:
                return {"sucesso": True, "mensagem": f"Webhook respondeu com status {response.status_code}"}
            else:
                return {"sucesso": False, "mensagem": f"Webhook retornou status {response.status_code}"}
    except Exception as e:
        return {"sucesso": False, "mensagem": f"Erro ao conectar: {str(e)}"}
