"""Router de espelho de ponto e AEJ."""

from datetime import datetime, timedelta
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUser,
    RequireGestor,
    TenantContext,
    get_current_user,
    get_db,
    get_tenant_context,
)
from app.models import MarcacaoPonto, Tenant, Usuario, UserRole
from app.schemas import (
    AEJExportRequest,
    AEJExportResponse,
    EspelhoDia,
    EspelhoFilter,
    EspelhoPonto,
    SuccessResponse,
)


router = APIRouter(prefix="/ponto", tags=["Espelho de Ponto"])


@router.get("/espelho", response_model=EspelhoPonto)
async def get_espelho_ponto(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    usuario_id: Optional[UUID] = None,
    periodo_inicio: datetime = Query(...),
    periodo_fim: datetime = Query(...),
):
    """
    Obter espelho de ponto.
    
    - Colaborador vê apenas seu próprio espelho
    - Gestor/Admin pode ver de qualquer usuário
    """
    # Determinar usuário alvo
    target_user_id = usuario_id or current_user.id
    
    # Verificar permissão
    if current_user.papel == UserRole.COLABORADOR and target_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado",
        )
    
    # Buscar usuário
    result = await db.execute(
        select(Usuario).where(
            Usuario.id == target_user_id,
            Usuario.tenant_id == tenant.tenant_id,
        )
    )
    usuario = result.scalar_one_or_none()
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )
    
    # Buscar marcações do período
    result = await db.execute(
        select(MarcacaoPonto)
        .where(
            MarcacaoPonto.usuario_id == target_user_id,
            MarcacaoPonto.tenant_id == tenant.tenant_id,
            MarcacaoPonto.timestamp_local >= periodo_inicio,
            MarcacaoPonto.timestamp_local <= periodo_fim,
        )
        .order_by(MarcacaoPonto.timestamp_local)
    )
    marcacoes = result.scalars().all()
    
    # Agrupar por dia
    from collections import defaultdict
    from app.schemas import MarcacaoRead
    
    dias_dict = defaultdict(list)
    for m in marcacoes:
        dia = m.timestamp_local.date()
        dias_dict[dia].append(MarcacaoRead.model_validate(m))
    
    # Calcular totais
    total_dias = 0
    total_minutos_trabalhados = 0
    total_minutos_extras = 0
    total_minutos_falta = 0
    total_atrasos = 0
    total_faltas = 0
    
    dias = []
    current_date = periodo_inicio.date()
    end_date = periodo_fim.date()
    
    while current_date <= end_date:
        marcacoes_dia = dias_dict.get(current_date, [])
        
        # Calcular horas do dia (simplificado)
        horas_trabalhadas = None
        horas_extras = None
        horas_falta = None
        observacoes = []
        
        if marcacoes_dia:
            total_dias += 1
            
            # Cálculo simplificado: entrada/saída
            entradas = [m for m in marcacoes_dia if m.evento.value in ("entrada", "pausa_fim")]
            saidas = [m for m in marcacoes_dia if m.evento.value in ("saida", "pausa_inicio")]
            
            minutos_dia = 0
            for i in range(min(len(entradas), len(saidas))):
                entrada = entradas[i].timestamp_local
                saida = saidas[i].timestamp_local
                if saida > entrada:
                    minutos_dia += (saida - entrada).total_seconds() / 60
            
            total_minutos_trabalhados += minutos_dia
            
            horas = int(minutos_dia // 60)
            mins = int(minutos_dia % 60)
            horas_trabalhadas = f"{horas:02d}:{mins:02d}"
            
            # Verificar atrasos (simplificado - assumindo entrada às 08:00)
            if entradas:
                primeira_entrada = entradas[0].timestamp_local
                if primeira_entrada.hour > 8 or (primeira_entrada.hour == 8 and primeira_entrada.minute > 10):
                    total_atrasos += 1
                    observacoes.append("Atraso")
            
            # Verificar marcações suspeitas
            if any(m.suspeita for m in marcacoes_dia):
                observacoes.append("Marcação suspeita")
        else:
            # Verificar se é dia útil (simplificado - seg a sex)
            if current_date.weekday() < 5:
                total_faltas += 1
                observacoes.append("Falta")
        
        dias.append(EspelhoDia(
            data=datetime.combine(current_date, datetime.min.time()),
            marcacoes=marcacoes_dia,
            horas_trabalhadas=horas_trabalhadas,
            horas_extras=horas_extras,
            horas_falta=horas_falta,
            observacoes=observacoes,
        ))
        
        current_date += timedelta(days=1)
    
    # Formatar totais
    def format_minutes(minutes):
        h = int(minutes // 60)
        m = int(minutes % 60)
        return f"{h:02d}:{m:02d}"
    
    return EspelhoPonto(
        usuario_id=usuario.id,
        usuario_nome=usuario.nome,
        usuario_matricula=usuario.matricula,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        dias=dias,
        total_dias_trabalhados=total_dias,
        total_horas_trabalhadas=format_minutes(total_minutos_trabalhados),
        total_horas_extras=format_minutes(total_minutos_extras),
        total_horas_falta=format_minutes(total_minutos_falta),
        total_atrasos=total_atrasos,
        total_faltas=total_faltas,
    )


@router.post("/espelho/assinar", response_model=SuccessResponse)
async def assinar_espelho(
    filter: EspelhoFilter,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Assinar espelho de ponto.
    
    - Colaborador assina seu próprio espelho
    - Gestor/Admin assina como aprovador
    """
    import hashlib
    from app.models import Assinatura, AssinaturaMetodo, AssinaturaStatus, Documento, DocumentoTipo
    
    # Determinar usuário alvo
    target_user_id = filter.usuario_id or current_user.id
    
    # Verificar permissão
    if current_user.papel == UserRole.COLABORADOR and target_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado",
        )
    
    # Gerar hash do período assinado
    hash_content = f"{target_user_id}|{filter.periodo_inicio.isoformat()}|{filter.periodo_fim.isoformat()}"
    doc_hash = hashlib.sha256(hash_content.encode()).hexdigest()
    
    # Criar documento de espelho (se não existir)
    result = await db.execute(
        select(Documento).where(
            Documento.tenant_id == tenant.tenant_id,
            Documento.usuario_id == target_user_id,
            Documento.tipo == DocumentoTipo.ESPELHO_PONTO,
            Documento.referencia_mes == filter.periodo_inicio.month,
            Documento.referencia_ano == filter.periodo_inicio.year,
        )
    )
    documento = result.scalar_one_or_none()
    
    if not documento:
        documento = Documento(
            tenant_id=tenant.tenant_id,
            usuario_id=target_user_id,
            tipo=DocumentoTipo.ESPELHO_PONTO,
            nome=f"Espelho de Ponto - {filter.periodo_inicio.strftime('%m/%Y')}",
            referencia_mes=filter.periodo_inicio.month,
            referencia_ano=filter.periodo_inicio.year,
            hash=doc_hash,
        )
        db.add(documento)
        await db.flush()
    
    # Criar assinatura
    assinatura = Assinatura(
        tenant_id=tenant.tenant_id,
        documento_id=documento.id,
        usuario_id=current_user.id,
        metodo=AssinaturaMetodo.ESIGN,
        status=AssinaturaStatus.VALIDA,
        hash=doc_hash,
        ip_address=http_request.client.host if http_request.client else None,
        user_agent=http_request.headers.get("User-Agent"),
        assinado_em=datetime.utcnow(),
    )
    db.add(assinatura)
    await db.commit()
    
    return SuccessResponse(message="Espelho assinado com sucesso")


@router.get("/espelho/pdf")
async def download_espelho_pdf(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    usuario_id: Optional[UUID] = None,
    periodo_inicio: datetime = Query(...),
    periodo_fim: datetime = Query(...),
):
    """Download do espelho em PDF."""
    from app.services.pdf import pdf_service
    
    # Determinar usuário alvo
    target_user_id = usuario_id or current_user.id
    
    # Verificar permissão
    if current_user.papel == UserRole.COLABORADOR and target_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado",
        )
    
    # Buscar dados do usuário
    result = await db.execute(
        select(Usuario).where(
            Usuario.id == target_user_id,
            Usuario.tenant_id == tenant.tenant_id,
        )
    )
    usuario = result.scalar_one_or_none()
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )
    
    # Buscar tenant
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_data = result.scalar_one()
    
    # Buscar marcações do período
    result = await db.execute(
        select(MarcacaoPonto)
        .where(
            MarcacaoPonto.usuario_id == target_user_id,
            MarcacaoPonto.tenant_id == tenant.tenant_id,
            MarcacaoPonto.timestamp_local >= periodo_inicio,
            MarcacaoPonto.timestamp_local <= periodo_fim,
        )
        .order_by(MarcacaoPonto.timestamp_local)
    )
    marcacoes = result.scalars().all()
    
    # Agrupar por dia
    from collections import defaultdict
    
    dias_dict = defaultdict(list)
    for m in marcacoes:
        dia = m.timestamp_local.date()
        dias_dict[dia].append({
            "evento": m.evento.value,
            "hora": m.timestamp_local.strftime("%H:%M"),
        })
    
    # Construir lista de dias
    dias = []
    total_minutos = 0
    total_atrasos = 0
    total_faltas = 0
    
    current_date = periodo_inicio.date()
    end_date = periodo_fim.date()
    
    while current_date <= end_date:
        marcacoes_dia = dias_dict.get(current_date, [])
        
        horas_trabalhadas = "00:00"
        observacoes = []
        
        if marcacoes_dia:
            # Calcular horas do dia
            entradas = [m for m in marcacoes_dia if m["evento"] in ("entrada", "pausa_fim")]
            saidas = [m for m in marcacoes_dia if m["evento"] in ("saida", "pausa_inicio")]
            
            minutos_dia = 0
            for i in range(min(len(entradas), len(saidas))):
                h1, m1 = map(int, entradas[i]["hora"].split(":"))
                h2, m2 = map(int, saidas[i]["hora"].split(":"))
                minutos_dia += (h2 * 60 + m2) - (h1 * 60 + m1)
            
            total_minutos += minutos_dia
            horas_trabalhadas = f"{minutos_dia // 60:02d}:{minutos_dia % 60:02d}"
        elif current_date.weekday() < 5:
            total_faltas += 1
            observacoes.append("Falta")
        
        dias.append({
            "data": current_date.strftime("%d/%m"),
            "marcacoes": marcacoes_dia,
            "horas_trabalhadas": horas_trabalhadas,
            "observacoes": observacoes,
        })
        
        current_date += timedelta(days=1)
    
    # Gerar PDF
    pdf_bytes = pdf_service.gerar_espelho_ponto(
        usuario_nome=usuario.nome,
        usuario_matricula=usuario.matricula or "",
        usuario_cpf=usuario.cpf,
        empresa_nome=tenant_data.nome,
        empresa_cnpj=tenant_data.cnpj,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        dias=dias,
        totais={
            "dias": len([d for d in dias if d["horas_trabalhadas"] != "00:00"]),
            "horas": f"{total_minutos // 60:02d}:{total_minutos % 60:02d}",
            "extras": "00:00",
            "atrasos": total_atrasos,
            "faltas": total_faltas,
            "banco": "00:00",
        },
    )
    
    # Retornar como stream
    from io import BytesIO
    
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=espelho_{usuario.matricula}_{periodo_inicio.strftime('%Y%m')}.pdf"
        },
    )


# ============================================================================
# AEJ - Arquivo Eletrônico de Jornada
# ============================================================================

@router.post("/aej/exportar", response_model=AEJExportResponse)
async def exportar_aej(
    data: AEJExportRequest,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Exportar AEJ (Arquivo Eletrônico de Jornada).
    
    Gera arquivo conforme Portaria 671 do MTE.
    """
    import hashlib
    
    # Buscar tenant
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant.tenant_id)
    )
    tenant_data = result.scalar_one()
    
    # Construir query de marcações
    query = select(MarcacaoPonto).where(
        MarcacaoPonto.tenant_id == tenant.tenant_id,
        MarcacaoPonto.timestamp_local >= data.periodo_inicio,
        MarcacaoPonto.timestamp_local <= data.periodo_fim,
    )
    
    if data.usuarios_ids:
        query = query.where(MarcacaoPonto.usuario_id.in_(data.usuarios_ids))
    
    if data.equipe_id:
        # Buscar usuários da equipe
        result = await db.execute(
            select(Usuario.id).where(Usuario.equipe_id == data.equipe_id)
        )
        equipe_usuarios = [r[0] for r in result.all()]
        query = query.where(MarcacaoPonto.usuario_id.in_(equipe_usuarios))
    
    query = query.order_by(MarcacaoPonto.timestamp_local)
    
    result = await db.execute(query)
    marcacoes = result.scalars().all()
    
    # Gerar conteúdo AEJ
    # Formato simplificado - em produção seguir especificação completa da Portaria 671
    lines = []
    
    # Header
    lines.append(f"00|AEJ|{tenant_data.cnpj}|{tenant_data.nome}")
    lines.append(f"01|{data.periodo_inicio.strftime('%Y%m%d')}|{data.periodo_fim.strftime('%Y%m%d')}")
    
    # Marcações
    for m in marcacoes:
        # Buscar dados do usuário
        result = await db.execute(
            select(Usuario).where(Usuario.id == m.usuario_id)
        )
        usuario = result.scalar_one()
        
        line = (
            f"02|{usuario.cpf}|{usuario.matricula}|{m.timestamp_local.strftime('%Y%m%d')}|"
            f"{m.timestamp_local.strftime('%H%M')}|{m.evento.value}|{m.tipo.value}"
        )
        lines.append(line)
    
    # Footer
    lines.append(f"99|{len(marcacoes)}")
    
    content = "\n".join(lines)
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    
    # Salvar arquivo no MinIO
    from app.services.storage import get_storage_service
    
    storage = get_storage_service()
    arquivo_nome = f"AEJ_{tenant_data.cnpj}_{data.periodo_inicio.strftime('%Y%m%d')}_{data.periodo_fim.strftime('%Y%m%d')}.txt"
    
    result = await storage.upload_file(
        tenant_id=tenant.tenant_id,
        folder="aej",
        filename=f"{content_hash}.txt",
        content=content.encode("utf-8"),
        content_type="text/plain",
    )
    
    # Gerar URL de download
    download_url = await storage.get_presigned_url(result["key"], expires_in=3600)
    
    return AEJExportResponse(
        arquivo_url=download_url or f"/api/v1/ponto/aej/download/{content_hash}",
        arquivo_nome=arquivo_nome,
        periodo_inicio=data.periodo_inicio,
        periodo_fim=data.periodo_fim,
        total_registros=len(marcacoes),
        hash=content_hash,
        gerado_em=datetime.utcnow(),
    )


@router.get("/aej/download/{file_hash}")
async def download_aej(
    file_hash: str,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
):
    """Download do arquivo AEJ."""
    from io import BytesIO
    from app.services.storage import get_storage_service
    
    storage = get_storage_service()
    
    # Buscar arquivo do MinIO
    storage_path = f"{tenant.tenant_id}/aej/{file_hash}.txt"
    
    try:
        content = await storage.download_file(storage_path)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo não encontrado",
        )
    
    return StreamingResponse(
        BytesIO(content),
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=AEJ_{file_hash[:8]}.txt"
        },
    )
