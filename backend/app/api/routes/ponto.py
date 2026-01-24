"""Router de marcações de ponto."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    CurrentUser,
    RequireGestor,
    TenantContext,
    get_current_user,
    get_db,
    get_tenant_context,
)
from app.models import (
    Auditoria,
    AuditoriaDecisao,
    MarcacaoPonto,
    MarcacaoStatus,
    Perimetro,
    Usuario,
    UserRole,
)
from app.schemas import (
    AuditoriaRead,
    AuditoriaRevisao,
    Comprovante,
    CorrecaoAprovacao,
    CorrecaoRead,
    CorrecaoRequest,
    MarcacaoCreate,
    MarcacaoOfflineSync,
    MarcacaoRead,
    MarcacaoUpdate,
    MarcacaoWithAuditoria,
    PaginatedResponse,
    SuccessResponse,
)
from app.schemas.base import BaseSchema


router = APIRouter(prefix="/ponto", tags=["Ponto"])


@router.post("/marcacoes", response_model=MarcacaoRead, status_code=status.HTTP_201_CREATED)
async def registrar_marcacao(
    data: MarcacaoCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Registrar marcação de ponto.
    
    - Valida geolocalização (se configurado)
    - Processa foto e liveness (async)
    - Gera comprovante com hash
    """
    import hashlib
    from app.services.geo import geo_service, GeoPoint
    
    # Verificar perímetro (geofencing)
    perimetro_id = None
    suspeita = False
    geo_valido = True
    
    if data.latitude and data.longitude:
        # Validar localização usando serviço de geo
        ponto = GeoPoint(
            latitude=data.latitude,
            longitude=data.longitude,
            accuracy_metros=float(data.accuracy_metros) if data.accuracy_metros else None,
        )
        
        resultado_geo = await geo_service.validar_localizacao(
            db=db,
            ponto=ponto,
            usuario_id=current_user.id,
            tenant_id=tenant.tenant_id,
        )
        
        geo_valido = resultado_geo.valido
        perimetro_id = resultado_geo.perimetro_id
        suspeita = not geo_valido
    
    # Verificar última marcação para detectar teletransporte
    result = await db.execute(
        select(MarcacaoPonto)
        .where(
            MarcacaoPonto.usuario_id == current_user.id,
            MarcacaoPonto.tenant_id == tenant.tenant_id,
        )
        .order_by(MarcacaoPonto.timestamp_local.desc())
        .limit(1)
    )
    ultima_marcacao = result.scalar_one_or_none()
    
    if ultima_marcacao and data.latitude and data.longitude and ultima_marcacao.latitude and ultima_marcacao.longitude:
        ponto_anterior = GeoPoint(
            latitude=ultima_marcacao.latitude,
            longitude=ultima_marcacao.longitude,
        )
        ponto_atual = GeoPoint(
            latitude=data.latitude,
            longitude=data.longitude,
        )
        intervalo = (data.timestamp_local - ultima_marcacao.timestamp_local).total_seconds()
        
        if intervalo > 0:
            teletransporte, velocidade = geo_service.detectar_teletransporte(
                ponto_anterior=ponto_anterior,
                ponto_atual=ponto_atual,
                intervalo_segundos=intervalo,
            )
            if teletransporte:
                suspeita = True
    
    # Criar marcação
    marcacao = MarcacaoPonto(
        tenant_id=tenant.tenant_id,
        usuario_id=current_user.id,
        dispositivo_id=data.dispositivo_id,
        perimetro_id=perimetro_id,
        tipo=data.tipo,
        evento=data.evento,
        timestamp_local=data.timestamp_local,
        timezone=data.timezone,
        latitude=data.latitude,
        longitude=data.longitude,
        accuracy_metros=data.accuracy_metros,
        modo=data.modo,
        status=MarcacaoStatus.PENDENTE,
        suspeita=suspeita,
        evidencias=data.liveness_data,
    )
    
    # Gerar hash do comprovante
    comprovante_data = f"{current_user.id}|{data.evento}|{data.timestamp_local.isoformat()}"
    marcacao.comprovante_hash = hashlib.sha256(comprovante_data.encode()).hexdigest()
    
    db.add(marcacao)
    await db.commit()
    await db.refresh(marcacao)
    
    # Disparar task async para processar auditoria
    from app.tasks.auditoria import processar_auditoria_marcacao
    processar_auditoria_marcacao.delay(
        marcacao_id=str(marcacao.id),
        tenant_id=str(tenant.tenant_id),
    )
    
    return MarcacaoRead.model_validate(marcacao)


@router.post("/marcacoes/sync", response_model=list[MarcacaoRead])
async def sync_marcacoes_offline(
    data: MarcacaoOfflineSync,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Sincronizar marcações offline.
    
    Recebe lote de marcações feitas offline e processa.
    """
    marcacoes_criadas = []
    
    for marcacao_data in data.marcacoes:
        # Verificar duplicata pelo sync_id
        if marcacao_data.sync_id:
            result = await db.execute(
                select(MarcacaoPonto).where(
                    MarcacaoPonto.tenant_id == tenant.tenant_id,
                    MarcacaoPonto.usuario_id == current_user.id,
                    MarcacaoPonto.evidencias.contains({"sync_id": marcacao_data.sync_id}),
                )
            )
            if result.scalar_one_or_none():
                continue  # Já sincronizado
        
        marcacao = MarcacaoPonto(
            tenant_id=tenant.tenant_id,
            usuario_id=current_user.id,
            dispositivo_id=marcacao_data.dispositivo_id,
            tipo=marcacao_data.tipo,
            evento=marcacao_data.evento,
            timestamp_local=marcacao_data.timestamp_local,
            timezone=marcacao_data.timezone,
            latitude=marcacao_data.latitude,
            longitude=marcacao_data.longitude,
            accuracy_metros=marcacao_data.accuracy_metros,
            modo="offline",
            status=MarcacaoStatus.PENDENTE,
            evidencias={"sync_id": marcacao_data.sync_id} if marcacao_data.sync_id else None,
        )
        
        db.add(marcacao)
        marcacoes_criadas.append(marcacao)
    
    await db.commit()
    
    for m in marcacoes_criadas:
        await db.refresh(m)
    
    return [MarcacaoRead.model_validate(m) for m in marcacoes_criadas]


@router.get("/marcacoes", response_model=PaginatedResponse[MarcacaoRead])
async def listar_marcacoes(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    usuario_id: Optional[UUID] = None,
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
    status_filter: Optional[MarcacaoStatus] = Query(default=None, alias="status"),
    suspeita: Optional[bool] = None,
):
    """
    Listar marcações.
    
    - Colaborador vê apenas suas marcações
    - Gestor vê da sua equipe
    - Admin vê todas do tenant
    """
    query = select(MarcacaoPonto).where(MarcacaoPonto.tenant_id == tenant.tenant_id)
    count_query = select(func.count(MarcacaoPonto.id)).where(
        MarcacaoPonto.tenant_id == tenant.tenant_id
    )
    
    # Filtro por permissão
    if current_user.papel == UserRole.COLABORADOR:
        query = query.where(MarcacaoPonto.usuario_id == current_user.id)
        count_query = count_query.where(MarcacaoPonto.usuario_id == current_user.id)
    elif current_user.papel == UserRole.GESTOR:
        # Buscar equipe do gestor
        result = await db.execute(
            select(Usuario.equipe_id).where(Usuario.id == current_user.id)
        )
        equipe_id = result.scalar_one_or_none()
        
        if equipe_id:
            # Buscar usuários da equipe
            result = await db.execute(
                select(Usuario.id).where(Usuario.equipe_id == equipe_id)
            )
            equipe_usuarios = [r[0] for r in result.all()]
            
            query = query.where(MarcacaoPonto.usuario_id.in_(equipe_usuarios))
            count_query = count_query.where(MarcacaoPonto.usuario_id.in_(equipe_usuarios))
    
    # Filtros específicos
    if usuario_id:
        query = query.where(MarcacaoPonto.usuario_id == usuario_id)
        count_query = count_query.where(MarcacaoPonto.usuario_id == usuario_id)
    
    if data_inicio:
        query = query.where(MarcacaoPonto.timestamp_servidor >= data_inicio)
        count_query = count_query.where(MarcacaoPonto.timestamp_servidor >= data_inicio)
    
    if data_fim:
        query = query.where(MarcacaoPonto.timestamp_servidor <= data_fim)
        count_query = count_query.where(MarcacaoPonto.timestamp_servidor <= data_fim)
    
    if status_filter:
        query = query.where(MarcacaoPonto.status == status_filter)
        count_query = count_query.where(MarcacaoPonto.status == status_filter)
    
    if suspeita is not None:
        query = query.where(MarcacaoPonto.suspeita == suspeita)
        count_query = count_query.where(MarcacaoPonto.suspeita == suspeita)
    
    # Total
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # Paginação e ordenação
    query = query.order_by(MarcacaoPonto.timestamp_servidor.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    marcacoes = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[MarcacaoRead.model_validate(m) for m in marcacoes],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/marcacoes/{marcacao_id}", response_model=MarcacaoWithAuditoria)
async def get_marcacao(
    marcacao_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Obter marcação com detalhes de auditoria."""
    
    result = await db.execute(
        select(MarcacaoPonto)
        .options(selectinload(MarcacaoPonto.auditoria))
        .where(
            MarcacaoPonto.id == marcacao_id,
            MarcacaoPonto.tenant_id == tenant.tenant_id,
        )
    )
    marcacao = result.scalar_one_or_none()
    
    if not marcacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marcação não encontrada",
        )
    
    # Verificar permissão
    if current_user.papel == UserRole.COLABORADOR and marcacao.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado",
        )
    
    response = MarcacaoWithAuditoria.model_validate(marcacao)
    if marcacao.auditoria:
        response.auditoria = AuditoriaRead.model_validate(marcacao.auditoria)
    
    return response


@router.get("/marcacoes/{marcacao_id}/comprovante", response_model=Comprovante)
async def get_comprovante(
    marcacao_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Obter comprovante de marcação."""
    
    result = await db.execute(
        select(MarcacaoPonto)
        .options(selectinload(MarcacaoPonto.usuario))
        .where(
            MarcacaoPonto.id == marcacao_id,
            MarcacaoPonto.tenant_id == tenant.tenant_id,
        )
    )
    marcacao = result.scalar_one_or_none()
    
    if not marcacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marcação não encontrada",
        )
    
    # Verificar permissão
    if current_user.papel == UserRole.COLABORADOR and marcacao.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado",
        )
    
    # Buscar dados do tenant
    from app.models import Tenant
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_data = result.scalar_one()
    
    return Comprovante(
        id=marcacao.id,
        marcacao_id=marcacao.id,
        usuario_nome=marcacao.usuario.nome,
        usuario_matricula=marcacao.usuario.matricula,
        empresa_nome=tenant_data.nome,
        empresa_cnpj=tenant_data.cnpj,
        evento=marcacao.evento,
        timestamp_local=marcacao.timestamp_local,
        timezone=marcacao.timezone,
        latitude=marcacao.latitude,
        longitude=marcacao.longitude,
        hash=marcacao.comprovante_hash or "",
        assinatura=marcacao.comprovante_assinatura or "",
    )


# ============================================================================
# CORREÇÕES
# ============================================================================

@router.post("/correcoes", response_model=CorrecaoRead, status_code=status.HTTP_201_CREATED)
async def solicitar_correcao(
    data: CorrecaoRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Solicitar correção de marcação."""
    
    result = await db.execute(
        select(MarcacaoPonto).where(
            MarcacaoPonto.id == data.marcacao_id,
            MarcacaoPonto.tenant_id == tenant.tenant_id,
        )
    )
    marcacao = result.scalar_one_or_none()
    
    if not marcacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marcação não encontrada",
        )
    
    # Colaborador só pode corrigir próprias marcações
    if current_user.papel == UserRole.COLABORADOR and marcacao.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado",
        )
    
    # Verificar se já tem correção pendente
    if marcacao.correcao_solicitada:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Já existe uma correção pendente para esta marcação",
        )
    
    # Registrar correção
    await db.execute(
        update(MarcacaoPonto)
        .where(MarcacaoPonto.id == data.marcacao_id)
        .values(
            correcao_solicitada=True,
            correcao_motivo=data.motivo,
            correcao_novo_horario=data.novo_horario,
            status=MarcacaoStatus.PENDENTE,
        )
    )
    await db.commit()
    
    return CorrecaoRead(
        marcacao_id=marcacao.id,
        motivo=data.motivo,
        horario_original=marcacao.timestamp_local,
        horario_solicitado=data.novo_horario,
        status="pendente",
        solicitado_por=current_user.id,
        solicitado_em=datetime.utcnow(),
    )


@router.get("/correcoes", response_model=PaginatedResponse[CorrecaoRead])
async def listar_correcoes(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    """
    Listar correções.
    
    - Colaborador: vê apenas suas próprias correções
    - Gestor/Admin: vê todas as correções pendentes
    """
    
    # Base query
    base_conditions = [
        MarcacaoPonto.tenant_id == tenant.tenant_id,
        MarcacaoPonto.correcao_solicitada == True,
    ]
    
    # Colaborador só vê suas próprias correções
    if current_user.papel == UserRole.COLABORADOR:
        base_conditions.append(MarcacaoPonto.usuario_id == current_user.id)
    else:
        # Gestor/Admin vê apenas pendentes
        base_conditions.append(MarcacaoPonto.correcao_aprovada_por.is_(None))
    
    query = select(MarcacaoPonto).where(*base_conditions)
    count_query = select(func.count(MarcacaoPonto.id)).where(*base_conditions)
    
    # Total
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # Paginação
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    marcacoes = result.scalars().all()
    
    correcoes = [
        CorrecaoRead(
            marcacao_id=m.id,
            motivo=m.correcao_motivo or "",
            horario_original=m.timestamp_local,
            horario_solicitado=m.correcao_novo_horario or m.timestamp_local,
            status="pendente",
            solicitado_por=m.usuario_id,
            solicitado_em=m.updated_at,
        )
        for m in marcacoes
    ]
    
    return PaginatedResponse.create(
        items=correcoes,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/correcoes/{marcacao_id}/aprovar", response_model=SuccessResponse)
async def aprovar_correcao(
    marcacao_id: UUID,
    data: CorrecaoAprovacao,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Aprovar ou rejeitar correção."""
    
    result = await db.execute(
        select(MarcacaoPonto).where(
            MarcacaoPonto.id == marcacao_id,
            MarcacaoPonto.tenant_id == tenant.tenant_id,
            MarcacaoPonto.correcao_solicitada == True,
        )
    )
    marcacao = result.scalar_one_or_none()
    
    if not marcacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Correção não encontrada",
        )
    
    if data.aprovado:
        # Aplicar correção
        await db.execute(
            update(MarcacaoPonto)
            .where(MarcacaoPonto.id == marcacao_id)
            .values(
                timestamp_local=marcacao.correcao_novo_horario,
                status=MarcacaoStatus.CORRIGIDO,
                correcao_aprovada_por=current_user.id,
                correcao_aprovada_em=datetime.utcnow(),
            )
        )
        message = "Correção aprovada e aplicada"
    else:
        # Rejeitar correção
        await db.execute(
            update(MarcacaoPonto)
            .where(MarcacaoPonto.id == marcacao_id)
            .values(
                correcao_solicitada=False,
                correcao_motivo=None,
                correcao_novo_horario=None,
                status=MarcacaoStatus.REJEITADO,
                correcao_aprovada_por=current_user.id,
                correcao_aprovada_em=datetime.utcnow(),
            )
        )
        message = "Correção rejeitada"
    
    await db.commit()
    
    return SuccessResponse(message=message)


# ============================================================================
# AUDITORIA
# ============================================================================

@router.get("/suspeitas", response_model=PaginatedResponse[MarcacaoWithAuditoria])
async def listar_marcacoes_suspeitas(
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    """Listar marcações suspeitas para revisão."""
    
    query = (
        select(MarcacaoPonto)
        .options(selectinload(MarcacaoPonto.auditoria))
        .where(
            MarcacaoPonto.tenant_id == tenant.tenant_id,
            MarcacaoPonto.suspeita == True,
        )
    )
    count_query = select(func.count(MarcacaoPonto.id)).where(
        MarcacaoPonto.tenant_id == tenant.tenant_id,
        MarcacaoPonto.suspeita == True,
    )
    
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    query = query.order_by(MarcacaoPonto.timestamp_servidor.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    marcacoes = result.scalars().all()
    
    items = []
    for m in marcacoes:
        item = MarcacaoWithAuditoria.model_validate(m)
        if m.auditoria:
            item.auditoria = AuditoriaRead.model_validate(m.auditoria)
        items.append(item)
    
    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/auditorias/{marcacao_id}/revisar", response_model=SuccessResponse)
async def revisar_auditoria(
    marcacao_id: UUID,
    data: AuditoriaRevisao,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Revisar manualmente uma auditoria."""
    
    result = await db.execute(
        select(Auditoria)
        .join(MarcacaoPonto)
        .where(
            MarcacaoPonto.id == marcacao_id,
            MarcacaoPonto.tenant_id == tenant.tenant_id,
        )
    )
    auditoria = result.scalar_one_or_none()
    
    if not auditoria:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Auditoria não encontrada",
        )
    
    # Atualizar auditoria
    await db.execute(
        update(Auditoria)
        .where(Auditoria.id == auditoria.id)
        .values(
            revisado_por=current_user.id,
            revisado_em=datetime.utcnow(),
            decisao_revisao=data.decisao.value,
            observacao_revisao=data.observacao,
        )
    )
    
    # Atualizar marcação
    novo_status = (
        MarcacaoStatus.PROCESSADO if data.decisao == AuditoriaDecisao.APROVADA
        else MarcacaoStatus.REJEITADO
    )
    
    await db.execute(
        update(MarcacaoPonto)
        .where(MarcacaoPonto.id == marcacao_id)
        .values(
            status=novo_status,
            suspeita=False if data.decisao == AuditoriaDecisao.APROVADA else True,
        )
    )
    
    await db.commit()
    
    return SuccessResponse(message=f"Auditoria revisada: {data.decisao.value}")


# ============================================================================
# REGISTRO WEB (Simplificado para colaboradores via navegador)
# ============================================================================

class RegistroPontoWeb(BaseSchema):
    """Schema para registro de ponto via web."""
    
    evento: str  # entrada, inicio_intervalo, fim_intervalo, saida
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    precisao_gps: Optional[float] = None
    foto_base64: Optional[str] = None
    endereco: Optional[str] = None
    dispositivo: Optional[str] = None


class ValidarFaceRequest(BaseSchema):
    """Schema para validação de face."""
    
    foto_base64: str


class ValidarFaceResponse(BaseSchema):
    """Schema de resposta de validação de face."""
    
    valido: bool
    confianca: float
    mensagem: str


@router.post("/registrar", response_model=MarcacaoRead, status_code=status.HTTP_201_CREATED)
async def registrar_ponto_web(
    data: RegistroPontoWeb,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Registrar ponto via web (navegador).
    
    Endpoint completo para colaboradores registrarem ponto
    pelo navegador, com:
    - Validação de geolocalização (geofencing)
    - Reconhecimento facial
    - Armazenamento de foto no MinIO/S3
    """
    import hashlib
    import base64
    from app.models import MarcacaoEvento, MarcacaoTipo
    from app.services.geo import geo_service, GeoPoint
    from app.services.storage import StorageService
    from app.services.facial_recognition import facial_service
    
    # Mapear evento
    evento_map = {
        "entrada": MarcacaoEvento.ENTRADA,
        "inicio_intervalo": MarcacaoEvento.PAUSA_INICIO,
        "fim_intervalo": MarcacaoEvento.PAUSA_FIM,
        "saida": MarcacaoEvento.SAIDA,
    }
    
    evento = evento_map.get(data.evento)
    if not evento:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Evento inválido: {data.evento}",
        )
    
    # Verificar se já existe marcação do mesmo tipo hoje
    hoje_inicio = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    hoje_fim = hoje_inicio + timedelta(days=1)
    
    result = await db.execute(
        select(MarcacaoPonto).where(
            MarcacaoPonto.tenant_id == tenant.tenant_id,
            MarcacaoPonto.usuario_id == current_user.id,
            MarcacaoPonto.evento == evento,
            MarcacaoPonto.timestamp_local >= hoje_inicio,
            MarcacaoPonto.timestamp_local < hoje_fim,
        )
    )
    
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Você já registrou {data.evento} hoje",
        )
    
    # ===== 1. VALIDAÇÃO DE PERÍMETRO (GEOFENCING) =====
    perimetro_id = None
    geo_valido = True
    geo_mensagem = ""
    distancia_metros = None
    
    if data.latitude and data.longitude:
        ponto = GeoPoint(
            latitude=data.latitude,
            longitude=data.longitude,
            accuracy_metros=data.precisao_gps,
        )
        
        try:
            resultado_geo = await geo_service.validar_localizacao(
                db=db,
                ponto=ponto,
                usuario_id=current_user.id,
                tenant_id=tenant.tenant_id,
            )
            perimetro_id = resultado_geo.perimetro_id
            geo_valido = resultado_geo.valido
            geo_mensagem = resultado_geo.mensagem
            distancia_metros = resultado_geo.distancia_metros
        except Exception as e:
            geo_mensagem = f"Erro ao validar localização: {str(e)}"
    
    # ===== 2. PROCESSAR E SALVAR FOTO NO MINIO =====
    foto_url = None
    face_valida = True
    face_confianca = 0.0
    
    if data.foto_base64:
        try:
            # Decodificar base64
            if "," in data.foto_base64:
                foto_bytes = base64.b64decode(data.foto_base64.split(",", 1)[1])
            else:
                foto_bytes = base64.b64decode(data.foto_base64)
            
            # Validar reconhecimento facial
            detection_result = await facial_service.detect_face(foto_bytes)
            face_valida = detection_result.face_detected and detection_result.num_faces == 1
            face_confianca = detection_result.confidence
            
            if not face_valida:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=detection_result.message or "Face não detectada na foto",
                )
            
            # Comparar com foto cadastrada do usuário (se existir)
            user_result = await db.execute(
                select(Usuario.face_encoding).where(Usuario.id == current_user.id)
            )
            stored_encoding = user_result.scalar_one_or_none()
            
            if stored_encoding and hasattr(facial_service, 'compare_with_encoding'):
                comparison = await facial_service.compare_with_encoding(
                    foto_bytes, stored_encoding, threshold=0.6
                )
                if not comparison.match:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Face não corresponde ao cadastro (similaridade: {comparison.similarity:.0%})",
                    )
                face_confianca = comparison.similarity
            
            # Salvar foto no MinIO/S3
            storage = StorageService()
            agora_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"ponto_{current_user.id}_{agora_str}.jpg"
            
            upload_result = await storage.upload_file(
                tenant_id=tenant.tenant_id,
                folder="pontos",
                filename=filename,
                content=foto_bytes,
                content_type="image/jpeg",
            )
            foto_url = upload_result["key"]
            
            # Se usuário não tem encoding cadastrado, salvar
            if not stored_encoding and detection_result.face_encoding:
                await db.execute(
                    update(Usuario)
                    .where(Usuario.id == current_user.id)
                    .values(face_encoding=detection_result.face_encoding)
                )
                
        except HTTPException:
            raise
        except Exception as e:
            # Logar erro mas não falhar o registro
            import logging
            logging.error(f"Erro ao processar foto: {e}")
    
    # ===== 3. CRIAR MARCAÇÃO =====
    agora = datetime.utcnow()
    suspeita = not geo_valido or (data.foto_base64 and not face_valida)
    
    marcacao = MarcacaoPonto(
        tenant_id=tenant.tenant_id,
        usuario_id=current_user.id,
        perimetro_id=perimetro_id,
        tipo=MarcacaoTipo.WEB,
        evento=evento,
        timestamp_local=agora,
        timezone="America/Sao_Paulo",
        latitude=data.latitude,
        longitude=data.longitude,
        accuracy_metros=int(data.precisao_gps) if data.precisao_gps else None,
        modo="online",
        status=MarcacaoStatus.PENDENTE,
        suspeita=suspeita,
        evidencias={
            "origem": "web",
            "dispositivo": data.dispositivo,
            "endereco": data.endereco,
            "foto_url": foto_url,
            "face_confianca": face_confianca,
            "geo_valido": geo_valido,
            "geo_mensagem": geo_mensagem,
            "distancia_metros": distancia_metros,
        },
    )
    
    # Gerar hash do comprovante
    comprovante_data = f"{current_user.id}|{data.evento}|{agora.isoformat()}"
    marcacao.comprovante_hash = hashlib.sha256(comprovante_data.encode()).hexdigest()
    
    db.add(marcacao)
    await db.commit()
    await db.refresh(marcacao)
    
    # Disparar task async para processar auditoria
    try:
        from app.tasks.auditoria import processar_auditoria_marcacao
        processar_auditoria_marcacao.delay(
            marcacao_id=str(marcacao.id),
            tenant_id=str(tenant.tenant_id),
        )
    except Exception:
        pass  # Task de auditoria é opcional
    
    return MarcacaoRead.model_validate(marcacao)


@router.post("/validar-face", response_model=ValidarFaceResponse)
async def validar_face(
    data: ValidarFaceRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Validar reconhecimento facial.
    
    Detecta se há uma face válida na imagem.
    Se o usuário já tem face cadastrada, compara para validar identidade.
    
    Providers suportados:
    - local: face_recognition (dlib) - gratuito
    - aws: Amazon Rekognition
    - azure: Azure Face API
    """
    import base64
    from app.services.facial_recognition import facial_service
    
    try:
        # Decodificar base64
        foto_base64 = data.foto_base64
        if "," in foto_base64:
            foto_base64 = foto_base64.split(",", 1)[1]
        
        foto_bytes = base64.b64decode(foto_base64)
        
        # Verificar se é uma imagem válida (pelo tamanho mínimo)
        if len(foto_bytes) < 1000:
            return ValidarFaceResponse(
                valido=False,
                confianca=0,
                mensagem="Imagem muito pequena ou inválida",
            )
        
        # Detectar face na imagem
        detection_result = await facial_service.detect_face(foto_bytes)
        
        if not detection_result.face_detected:
            return ValidarFaceResponse(
                valido=False,
                confianca=0,
                mensagem=detection_result.message or "Nenhuma face detectada na imagem",
            )
        
        if detection_result.num_faces > 1:
            return ValidarFaceResponse(
                valido=False,
                confianca=detection_result.confidence * 100,
                mensagem=f"Múltiplas faces detectadas ({detection_result.num_faces}). Posicione apenas seu rosto.",
            )
        
        # Buscar encoding do usuário
        result = await db.execute(
            select(Usuario.face_encoding, Usuario.foto_base_url)
            .where(Usuario.id == current_user.id)
        )
        user_data = result.one_or_none()
        
        if not user_data or not user_data.face_encoding:
            # Primeiro acesso - aceitar e sugerir cadastro
            return ValidarFaceResponse(
                valido=True,
                confianca=detection_result.confidence * 100,
                mensagem="Face detectada (primeira validação - será usada como referência)",
            )
        
        # Comparar com face cadastrada
        if hasattr(facial_service, 'compare_with_encoding'):
            comparison = await facial_service.compare_with_encoding(
                foto_bytes,
                user_data.face_encoding,
                threshold=0.6,
            )
            
            return ValidarFaceResponse(
                valido=comparison.match,
                confianca=comparison.similarity * 100,
                mensagem=comparison.message,
            )
        
        # Fallback se não tiver método de comparação
        return ValidarFaceResponse(
            valido=True,
            confianca=detection_result.confidence * 100,
            mensagem="Face validada com sucesso",
        )
        
    except Exception as e:
        return ValidarFaceResponse(
            valido=False,
            confianca=0,
            mensagem=f"Erro ao processar imagem: {str(e)}",
        )

