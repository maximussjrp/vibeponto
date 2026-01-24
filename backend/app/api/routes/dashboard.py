"""Router de dashboard com estatísticas."""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_db,
    get_tenant_context,
    CurrentUser,
    TenantContext,
)
from app.models import Usuario, MarcacaoPonto, Equipe
from app.models.models import UserStatus, UserRole, MarcacaoEvento
from app.schemas.base import BaseSchema


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ============================================================================
# SCHEMAS
# ============================================================================

class ColaboradoresStats(BaseSchema):
    total: int
    ativos: int
    inativos: int
    novos_mes: int


class PontoStats(BaseSchema):
    marcacoes_hoje: int
    pendentes_aprovacao: int
    atrasos_hoje: int
    faltas_hoje: int


class HorasStats(BaseSchema):
    trabalhadas_mes: int  # em minutos
    extras_mes: int
    banco_horas_total: int


class AuditoriaStats(BaseSchema):
    alertas_pendentes: int
    alertas_criticos: int
    taxa_conformidade: float


class DashboardStatsResponse(BaseSchema):
    colaboradores: ColaboradoresStats
    ponto: PontoStats
    horas: HorasStats
    auditoria: AuditoriaStats


class GraficoMarcacoes(BaseSchema):
    data: str
    entradas: int
    saidas: int
    atrasos: int


class GraficoHorasExtras(BaseSchema):
    semana: str
    horas: int


class GraficoDistribuicao(BaseSchema):
    equipe: str
    total: int


class AtividadeRecente(BaseSchema):
    id: str
    tipo: str
    descricao: str
    usuario: str
    timestamp: datetime


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Obter estatísticas do dashboard."""
    
    hoje = datetime.utcnow().date()
    inicio_mes = hoje.replace(day=1)
    inicio_hoje = datetime.combine(hoje, datetime.min.time())
    fim_hoje = datetime.combine(hoje, datetime.max.time())
    
    # Estatísticas de colaboradores
    usuarios_query = select(func.count(Usuario.id)).where(
        Usuario.tenant_id == tenant.tenant_id
    )
    total_result = await db.execute(usuarios_query)
    total_usuarios = total_result.scalar_one()
    
    ativos_query = select(func.count(Usuario.id)).where(
        Usuario.tenant_id == tenant.tenant_id,
        Usuario.status == UserStatus.ACTIVE,
    )
    ativos_result = await db.execute(ativos_query)
    usuarios_ativos = ativos_result.scalar_one()
    
    novos_query = select(func.count(Usuario.id)).where(
        Usuario.tenant_id == tenant.tenant_id,
        Usuario.created_at >= inicio_mes,
    )
    novos_result = await db.execute(novos_query)
    novos_mes = novos_result.scalar_one()
    
    # Estatísticas de ponto
    marcacoes_hoje_query = select(func.count(MarcacaoPonto.id)).where(
        MarcacaoPonto.tenant_id == tenant.tenant_id,
        MarcacaoPonto.timestamp_local >= inicio_hoje,
        MarcacaoPonto.timestamp_local <= fim_hoje,
    )
    marcacoes_result = await db.execute(marcacoes_hoje_query)
    marcacoes_hoje = marcacoes_result.scalar_one()
    
    # Pendentes de aprovação (correções)
    pendentes_query = select(func.count(MarcacaoPonto.id)).where(
        MarcacaoPonto.tenant_id == tenant.tenant_id,
        MarcacaoPonto.correcao_solicitada == True,
        MarcacaoPonto.correcao_aprovada_por.is_(None),
    )
    pendentes_result = await db.execute(pendentes_query)
    pendentes_aprovacao = pendentes_result.scalar_one()
    
    # Entradas do dia para calcular atrasos
    entradas_query = select(func.count(MarcacaoPonto.id)).where(
        MarcacaoPonto.tenant_id == tenant.tenant_id,
        MarcacaoPonto.timestamp_local >= inicio_hoje,
        MarcacaoPonto.timestamp_local <= fim_hoje,
        MarcacaoPonto.evento == MarcacaoEvento.ENTRADA,
    )
    entradas_result = await db.execute(entradas_query)
    entradas_hoje = entradas_result.scalar_one()
    
    # Calcular faltas (usuários ativos sem entrada hoje)
    # Simplificado: consideramos falta se é dia útil e não há entrada
    faltas_hoje = max(0, usuarios_ativos - entradas_hoje) if hoje.weekday() < 5 else 0
    
    # Atrasos (simplificado: assumindo que atrasou se entrou após 08:10)
    atrasos_query = select(func.count(MarcacaoPonto.id)).where(
        MarcacaoPonto.tenant_id == tenant.tenant_id,
        MarcacaoPonto.timestamp_local >= inicio_hoje,
        MarcacaoPonto.timestamp_local <= fim_hoje,
        MarcacaoPonto.evento == MarcacaoEvento.ENTRADA,
        func.extract('hour', MarcacaoPonto.timestamp_local) >= 8,
        func.extract('minute', MarcacaoPonto.timestamp_local) > 10,
    )
    atrasos_result = await db.execute(atrasos_query)
    atrasos_hoje = atrasos_result.scalar_one()
    
    return DashboardStatsResponse(
        colaboradores=ColaboradoresStats(
            total=total_usuarios,
            ativos=usuarios_ativos,
            inativos=total_usuarios - usuarios_ativos,
            novos_mes=novos_mes,
        ),
        ponto=PontoStats(
            marcacoes_hoje=marcacoes_hoje,
            pendentes_aprovacao=pendentes_aprovacao,
            atrasos_hoje=atrasos_hoje,
            faltas_hoje=faltas_hoje,
        ),
        horas=HorasStats(
            trabalhadas_mes=0,  # TODO: calcular
            extras_mes=0,
            banco_horas_total=0,
        ),
        auditoria=AuditoriaStats(
            alertas_pendentes=0,
            alertas_criticos=0,
            taxa_conformidade=100.0,
        ),
    )


@router.get("/graficos/marcacoes-semana", response_model=list[GraficoMarcacoes])
async def get_marcacoes_semana(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Gráfico de marcações dos últimos 7 dias."""
    
    hoje = datetime.utcnow().date()
    resultados = []
    
    for i in range(6, -1, -1):
        dia = hoje - timedelta(days=i)
        inicio_dia = datetime.combine(dia, datetime.min.time())
        fim_dia = datetime.combine(dia, datetime.max.time())
        
        # Entradas
        entradas_query = select(func.count(MarcacaoPonto.id)).where(
            MarcacaoPonto.tenant_id == tenant.tenant_id,
            MarcacaoPonto.timestamp_local >= inicio_dia,
            MarcacaoPonto.timestamp_local <= fim_dia,
            MarcacaoPonto.evento == MarcacaoEvento.ENTRADA,
        )
        entradas_result = await db.execute(entradas_query)
        entradas = entradas_result.scalar_one()
        
        # Saídas
        saidas_query = select(func.count(MarcacaoPonto.id)).where(
            MarcacaoPonto.tenant_id == tenant.tenant_id,
            MarcacaoPonto.timestamp_local >= inicio_dia,
            MarcacaoPonto.timestamp_local <= fim_dia,
            MarcacaoPonto.evento == MarcacaoEvento.SAIDA,
        )
        saidas_result = await db.execute(saidas_query)
        saidas = saidas_result.scalar_one()
        
        resultados.append(GraficoMarcacoes(
            data=dia.strftime("%d/%m"),
            entradas=entradas,
            saidas=saidas,
            atrasos=0,
        ))
    
    return resultados


@router.get("/graficos/horas-extras-mes", response_model=list[GraficoHorasExtras])
async def get_horas_extras_mes(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Gráfico de horas extras do mês."""
    
    # Retorna dados vazios por enquanto
    return [
        GraficoHorasExtras(semana="Semana 1", horas=0),
        GraficoHorasExtras(semana="Semana 2", horas=0),
        GraficoHorasExtras(semana="Semana 3", horas=0),
        GraficoHorasExtras(semana="Semana 4", horas=0),
    ]


@router.get("/graficos/distribuicao-equipes", response_model=list[GraficoDistribuicao])
async def get_distribuicao_equipes(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Distribuição de colaboradores por equipe."""
    
    # Buscar equipes com contagem de membros
    query = select(
        Equipe.nome,
        func.count(Usuario.id).label("total")
    ).outerjoin(
        Usuario, Usuario.equipe_id == Equipe.id
    ).where(
        Equipe.tenant_id == tenant.tenant_id,
    ).group_by(Equipe.id, Equipe.nome)
    
    result = await db.execute(query)
    equipes = result.all()
    
    if not equipes:
        return [GraficoDistribuicao(equipe="Sem equipe", total=0)]
    
    return [
        GraficoDistribuicao(equipe=e.nome, total=e.total)
        for e in equipes
    ]


@router.get("/atividades-recentes", response_model=list[AtividadeRecente])
async def get_atividades_recentes(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limite: int = Query(default=10, ge=1, le=50),
):
    """Atividades recentes do tenant."""
    
    # Buscar últimas marcações
    query = select(MarcacaoPonto).join(
        Usuario, MarcacaoPonto.usuario_id == Usuario.id
    ).where(
        MarcacaoPonto.tenant_id == tenant.tenant_id,
    ).order_by(MarcacaoPonto.created_at.desc()).limit(limite)
    
    result = await db.execute(query)
    marcacoes = result.scalars().all()
    
    atividades = []
    for m in marcacoes:
        # Buscar nome do usuário
        user_query = select(Usuario.nome).where(Usuario.id == m.usuario_id)
        user_result = await db.execute(user_query)
        usuario_nome = user_result.scalar_one_or_none() or "Usuário"
        
        atividades.append(AtividadeRecente(
            id=str(m.id),
            tipo="marcacao",
            descricao=f"Registrou {m.evento.value}",
            usuario=usuario_nome,
            timestamp=m.created_at,
        ))
    
    return atividades
