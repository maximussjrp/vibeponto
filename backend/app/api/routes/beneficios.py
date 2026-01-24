"""Router de benefícios e carteiras."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    CurrentUser,
    RequireAdmin,
    RequireFinanceiro,
    RequireGestor,
    TenantContext,
    get_current_user,
    get_db,
    get_tenant_context,
)
from app.models import (
    BeneficioCarteira,
    BeneficioTipo,
    Cartao,
    CartaoStatus,
    Recarga,
    Transacao,
    Usuario,
    UserRole,
)
from app.schemas import (
    CartaoCreate,
    CartaoRead,
    CartaoBloqueio,
    CarteiraCreate,
    CarteiraRead,
    CarteiraUpdate,
    CarteiraWithCards,
    CarteiraSaldo,
    ExtratoResponse,
    PaginatedResponse,
    RecargaCreate,
    RecargaLote,
    RecargaLoteStatus,
    RecargaRead,
    SuccessResponse,
    TransacaoFilter,
    TransacaoRead,
)


router = APIRouter(prefix="/beneficios", tags=["Benefícios"])


# ============================================================================
# CARTEIRAS
# ============================================================================

@router.get("/carteiras", response_model=PaginatedResponse[CarteiraRead])
async def listar_carteiras(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    tipo: Optional[BeneficioTipo] = None,
    usuario_id: Optional[UUID] = None,
    ativa: Optional[bool] = None,
):
    """Listar carteiras de benefício."""
    
    query = select(BeneficioCarteira).where(
        BeneficioCarteira.tenant_id == tenant.tenant_id
    )
    count_query = select(func.count(BeneficioCarteira.id)).where(
        BeneficioCarteira.tenant_id == tenant.tenant_id
    )
    
    # Colaborador só vê suas carteiras
    if current_user.papel == UserRole.COLABORADOR:
        query = query.where(BeneficioCarteira.usuario_id == current_user.id)
        count_query = count_query.where(BeneficioCarteira.usuario_id == current_user.id)
    
    if tipo:
        query = query.where(BeneficioCarteira.tipo == tipo)
        count_query = count_query.where(BeneficioCarteira.tipo == tipo)
    
    if usuario_id:
        query = query.where(BeneficioCarteira.usuario_id == usuario_id)
        count_query = count_query.where(BeneficioCarteira.usuario_id == usuario_id)
    
    if ativa is not None:
        query = query.where(BeneficioCarteira.ativa == ativa)
        count_query = count_query.where(BeneficioCarteira.ativa == ativa)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    carteiras = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[CarteiraRead.model_validate(c) for c in carteiras],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/carteiras", response_model=CarteiraRead, status_code=status.HTTP_201_CREATED)
async def criar_carteira(
    data: CarteiraCreate,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Criar carteira de benefício para usuário."""
    
    # Verificar usuário existe
    result = await db.execute(
        select(Usuario).where(
            Usuario.id == data.usuario_id,
            Usuario.tenant_id == tenant.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário não encontrado",
        )
    
    # Verificar se já existe carteira do mesmo tipo
    result = await db.execute(
        select(BeneficioCarteira).where(
            BeneficioCarteira.usuario_id == data.usuario_id,
            BeneficioCarteira.tipo == data.tipo,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Usuário já possui carteira do tipo {data.tipo.value}",
        )
    
    carteira = BeneficioCarteira(
        tenant_id=tenant.tenant_id,
        usuario_id=data.usuario_id,
        tipo=data.tipo,
        nome=data.nome,
        politica=data.politica,
    )
    
    db.add(carteira)
    await db.commit()
    await db.refresh(carteira)
    
    return CarteiraRead.model_validate(carteira)


@router.get("/carteiras/{carteira_id}", response_model=CarteiraWithCards)
async def get_carteira(
    carteira_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Obter carteira com cartões."""
    
    result = await db.execute(
        select(BeneficioCarteira)
        .options(selectinload(BeneficioCarteira.cartoes))
        .where(
            BeneficioCarteira.id == carteira_id,
            BeneficioCarteira.tenant_id == tenant.tenant_id,
        )
    )
    carteira = result.scalar_one_or_none()
    
    if not carteira:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Carteira não encontrada",
        )
    
    # Verificar permissão
    if current_user.papel == UserRole.COLABORADOR and carteira.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado",
        )
    
    response = CarteiraWithCards.model_validate(carteira)
    response.cartoes = [CartaoRead.model_validate(c) for c in carteira.cartoes]
    
    return response


@router.get("/saldos", response_model=list[CarteiraSaldo])
async def get_meus_saldos(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Obter saldos de todas as carteiras do usuário."""
    
    result = await db.execute(
        select(BeneficioCarteira).where(
            BeneficioCarteira.usuario_id == current_user.id,
            BeneficioCarteira.tenant_id == tenant.tenant_id,
            BeneficioCarteira.ativa == True,
        )
    )
    carteiras = result.scalars().all()
    
    saldos = []
    for c in carteiras:
        # Buscar última transação
        result = await db.execute(
            select(Transacao)
            .where(Transacao.carteira_id == c.id)
            .order_by(Transacao.created_at.desc())
            .limit(1)
        )
        ultima = result.scalar_one_or_none()
        
        saldos.append(CarteiraSaldo(
            carteira_id=c.id,
            tipo=c.tipo,
            nome=c.nome,
            saldo_disponivel=c.saldo - c.saldo_bloqueado,
            saldo_bloqueado=c.saldo_bloqueado,
            ultima_transacao=ultima.created_at if ultima else None,
        ))
    
    return saldos


# ============================================================================
# CARTÕES
# ============================================================================

@router.post("/carteiras/{carteira_id}/cartoes", response_model=CartaoRead, status_code=status.HTTP_201_CREATED)
async def solicitar_cartao(
    carteira_id: UUID,
    data: CartaoCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Solicitar novo cartão para carteira."""
    
    result = await db.execute(
        select(BeneficioCarteira).where(
            BeneficioCarteira.id == carteira_id,
            BeneficioCarteira.tenant_id == tenant.tenant_id,
        )
    )
    carteira = result.scalar_one_or_none()
    
    if not carteira:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Carteira não encontrada",
        )
    
    # Verificar permissão
    if current_user.papel == UserRole.COLABORADOR and carteira.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado",
        )
    
    cartao = Cartao(
        carteira_id=carteira_id,
        emissor=data.emissor,
        numero_mascarado="**** **** **** ****",  # Será preenchido pelo emissor
        status=CartaoStatus.PENDENTE,
    )
    
    db.add(cartao)
    await db.commit()
    await db.refresh(cartao)
    
    # TODO: Integrar com API do emissor para solicitar cartão físico/virtual
    
    return CartaoRead.model_validate(cartao)


@router.post("/cartoes/{cartao_id}/bloquear", response_model=SuccessResponse)
async def bloquear_cartao(
    cartao_id: UUID,
    data: CartaoBloqueio,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Bloquear cartão."""
    
    result = await db.execute(
        select(Cartao)
        .join(BeneficioCarteira)
        .where(
            Cartao.id == cartao_id,
            BeneficioCarteira.tenant_id == tenant.tenant_id,
        )
    )
    cartao = result.scalar_one_or_none()
    
    if not cartao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cartão não encontrado",
        )
    
    await db.execute(
        update(Cartao)
        .where(Cartao.id == cartao_id)
        .values(status=CartaoStatus.BLOQUEADO)
    )
    await db.commit()
    
    return SuccessResponse(message="Cartão bloqueado")


@router.post("/cartoes/{cartao_id}/desbloquear", response_model=SuccessResponse)
async def desbloquear_cartao(
    cartao_id: UUID,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Desbloquear cartão (Gestor/Admin)."""
    
    result = await db.execute(
        select(Cartao)
        .join(BeneficioCarteira)
        .where(
            Cartao.id == cartao_id,
            BeneficioCarteira.tenant_id == tenant.tenant_id,
        )
    )
    cartao = result.scalar_one_or_none()
    
    if not cartao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cartão não encontrado",
        )
    
    await db.execute(
        update(Cartao)
        .where(Cartao.id == cartao_id)
        .values(status=CartaoStatus.ATIVO)
    )
    await db.commit()
    
    return SuccessResponse(message="Cartão desbloqueado")


# ============================================================================
# RECARGAS
# ============================================================================

@router.post("/recargas", response_model=RecargaRead, status_code=status.HTTP_201_CREATED)
async def criar_recarga(
    data: RecargaCreate,
    current_user: RequireFinanceiro,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Criar recarga individual."""
    
    result = await db.execute(
        select(BeneficioCarteira).where(
            BeneficioCarteira.id == data.carteira_id,
            BeneficioCarteira.tenant_id == tenant.tenant_id,
        )
    )
    carteira = result.scalar_one_or_none()
    
    if not carteira:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Carteira não encontrada",
        )
    
    recarga = Recarga(
        carteira_id=data.carteira_id,
        valor=data.valor,
        taxa=Decimal("0"),  # Calcular taxa baseado no emissor
        status="pendente",
    )
    
    db.add(recarga)
    await db.commit()
    await db.refresh(recarga)
    
    # TODO: Processar recarga via integração com emissor
    
    return RecargaRead.model_validate(recarga)


@router.post("/recargas/lote", response_model=RecargaLoteStatus, status_code=status.HTTP_202_ACCEPTED)
async def criar_recarga_lote(
    data: RecargaLote,
    current_user: RequireFinanceiro,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Criar recargas em lote."""
    
    from uuid import uuid4
    
    lote_id = uuid4()
    valor_total = sum(r.valor for r in data.recargas)
    
    # Criar recargas
    for recarga_data in data.recargas:
        recarga = Recarga(
            carteira_id=recarga_data.carteira_id,
            valor=recarga_data.valor,
            taxa=Decimal("0"),
            status="pendente",
            lote_id=lote_id,
            referencia=data.referencia,
        )
        db.add(recarga)
    
    await db.commit()
    
    # TODO: Processar lote em background
    
    return RecargaLoteStatus(
        lote_id=lote_id,
        total=len(data.recargas),
        processadas=0,
        sucesso=0,
        falha=0,
        valor_total=valor_total,
        taxa_total=Decimal("0"),
        status="pendente",
    )


@router.get("/recargas", response_model=PaginatedResponse[RecargaRead])
async def listar_recargas(
    current_user: RequireFinanceiro,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    carteira_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    lote_id: Optional[UUID] = None,
):
    """Listar recargas."""
    
    query = (
        select(Recarga)
        .join(BeneficioCarteira)
        .where(BeneficioCarteira.tenant_id == tenant.tenant_id)
    )
    count_query = (
        select(func.count(Recarga.id))
        .join(BeneficioCarteira)
        .where(BeneficioCarteira.tenant_id == tenant.tenant_id)
    )
    
    if carteira_id:
        query = query.where(Recarga.carteira_id == carteira_id)
        count_query = count_query.where(Recarga.carteira_id == carteira_id)
    
    if status_filter:
        query = query.where(Recarga.status == status_filter)
        count_query = count_query.where(Recarga.status == status_filter)
    
    if lote_id:
        query = query.where(Recarga.lote_id == lote_id)
        count_query = count_query.where(Recarga.lote_id == lote_id)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    query = query.order_by(Recarga.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    recargas = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[RecargaRead.model_validate(r) for r in recargas],
        total=total,
        page=page,
        per_page=per_page,
    )


# ============================================================================
# TRANSAÇÕES / EXTRATO
# ============================================================================

@router.get("/carteiras/{carteira_id}/extrato", response_model=ExtratoResponse)
async def get_extrato(
    carteira_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    data_inicio: datetime = Query(...),
    data_fim: datetime = Query(...),
):
    """Obter extrato de transações."""
    
    result = await db.execute(
        select(BeneficioCarteira).where(
            BeneficioCarteira.id == carteira_id,
            BeneficioCarteira.tenant_id == tenant.tenant_id,
        )
    )
    carteira = result.scalar_one_or_none()
    
    if not carteira:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Carteira não encontrada",
        )
    
    # Verificar permissão
    if current_user.papel == UserRole.COLABORADOR and carteira.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado",
        )
    
    # Buscar transações do período
    result = await db.execute(
        select(Transacao).where(
            Transacao.carteira_id == carteira_id,
            Transacao.created_at >= data_inicio,
            Transacao.created_at <= data_fim,
        ).order_by(Transacao.created_at)
    )
    transacoes = result.scalars().all()
    
    # Calcular totais
    total_creditos = sum(t.valor for t in transacoes if t.tipo == "credito")
    total_debitos = sum(t.valor for t in transacoes if t.tipo == "debito")
    
    # Saldo inicial (primeira transação do período ou saldo anterior)
    saldo_inicial = transacoes[0].saldo_anterior if transacoes else carteira.saldo
    saldo_final = transacoes[-1].saldo_posterior if transacoes else carteira.saldo
    
    return ExtratoResponse(
        carteira_id=carteira_id,
        tipo=carteira.tipo,
        periodo_inicio=data_inicio,
        periodo_fim=data_fim,
        saldo_inicial=saldo_inicial,
        saldo_final=saldo_final,
        total_creditos=total_creditos,
        total_debitos=total_debitos,
        transacoes=[TransacaoRead.model_validate(t) for t in transacoes],
    )


@router.get("/transacoes", response_model=PaginatedResponse[TransacaoRead])
async def listar_transacoes(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    carteira_id: Optional[UUID] = None,
    tipo: Optional[str] = None,
    categoria: Optional[str] = None,
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
):
    """Listar transações."""
    
    query = (
        select(Transacao)
        .join(BeneficioCarteira)
        .where(BeneficioCarteira.tenant_id == tenant.tenant_id)
    )
    count_query = (
        select(func.count(Transacao.id))
        .join(BeneficioCarteira)
        .where(BeneficioCarteira.tenant_id == tenant.tenant_id)
    )
    
    # Colaborador só vê suas transações
    if current_user.papel == UserRole.COLABORADOR:
        query = query.where(BeneficioCarteira.usuario_id == current_user.id)
        count_query = count_query.where(BeneficioCarteira.usuario_id == current_user.id)
    
    if carteira_id:
        query = query.where(Transacao.carteira_id == carteira_id)
        count_query = count_query.where(Transacao.carteira_id == carteira_id)
    
    if tipo:
        query = query.where(Transacao.tipo == tipo)
        count_query = count_query.where(Transacao.tipo == tipo)
    
    if categoria:
        query = query.where(Transacao.categoria == categoria)
        count_query = count_query.where(Transacao.categoria == categoria)
    
    if data_inicio:
        query = query.where(Transacao.created_at >= data_inicio)
        count_query = count_query.where(Transacao.created_at >= data_inicio)
    
    if data_fim:
        query = query.where(Transacao.created_at <= data_fim)
        count_query = count_query.where(Transacao.created_at <= data_fim)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    query = query.order_by(Transacao.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    transacoes = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[TransacaoRead.model_validate(t) for t in transacoes],
        total=total,
        page=page,
        per_page=per_page,
    )
