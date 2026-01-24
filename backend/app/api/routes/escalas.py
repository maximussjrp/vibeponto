"""Router de escalas de trabalho."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUser,
    RequireGestor,
    TenantContext,
    get_current_user,
    get_db,
    get_tenant_context,
)
from app.models import Escala, Usuario, Equipe
from app.schemas import (
    EscalaCreate,
    EscalaRead,
    EscalaUpdate,
    PaginatedResponse,
    SuccessResponse,
)


router = APIRouter(prefix="/escalas", tags=["Escalas"])


@router.get("", response_model=PaginatedResponse[EscalaRead])
async def listar_escalas(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    ativa: Optional[bool] = None,
    usuario_id: Optional[UUID] = None,
    equipe_id: Optional[UUID] = None,
):
    """Listar escalas."""
    
    query = select(Escala).where(Escala.tenant_id == tenant.tenant_id)
    count_query = select(func.count(Escala.id)).where(Escala.tenant_id == tenant.tenant_id)
    
    if ativa is not None:
        query = query.where(Escala.ativa == ativa)
        count_query = count_query.where(Escala.ativa == ativa)
    
    if usuario_id:
        query = query.where(Escala.usuario_id == usuario_id)
        count_query = count_query.where(Escala.usuario_id == usuario_id)
    
    if equipe_id:
        query = query.where(Escala.equipe_id == equipe_id)
        count_query = count_query.where(Escala.equipe_id == equipe_id)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.order_by(Escala.nome)
    
    result = await db.execute(query)
    escalas = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[EscalaRead.model_validate(e) for e in escalas],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=EscalaRead, status_code=status.HTTP_201_CREATED)
async def criar_escala(
    data: EscalaCreate,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Criar nova escala."""
    
    # Verificar usuário existe
    if data.usuario_id:
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
    
    # Verificar equipe existe
    if data.equipe_id:
        result = await db.execute(
            select(Equipe).where(
                Equipe.id == data.equipe_id,
                Equipe.tenant_id == tenant.tenant_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Equipe não encontrada",
            )
    
    # Converter janelas para dict
    janelas_dict = {}
    for dia, janela in data.janelas.items():
        janelas_dict[dia] = janela.model_dump()
    
    escala = Escala(
        tenant_id=tenant.tenant_id,
        nome=data.nome,
        usuario_id=data.usuario_id,
        equipe_id=data.equipe_id,
        regime=data.regime,
        janelas=janelas_dict,
        pausas_remuneradas=data.pausas_remuneradas,
        regras_he=data.regras_he,
        regras_banco_horas=data.regras_banco_horas,
        tolerancia_entrada_min=data.tolerancia_entrada_min,
        tolerancia_saida_min=data.tolerancia_saida_min,
        vigencia_inicio=data.vigencia_inicio,
        vigencia_fim=data.vigencia_fim,
    )
    
    db.add(escala)
    await db.commit()
    await db.refresh(escala)
    
    return EscalaRead.model_validate(escala)


@router.get("/{escala_id}", response_model=EscalaRead)
async def get_escala(
    escala_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Obter escala por ID."""
    
    result = await db.execute(
        select(Escala).where(
            Escala.id == escala_id,
            Escala.tenant_id == tenant.tenant_id,
        )
    )
    escala = result.scalar_one_or_none()
    
    if not escala:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escala não encontrada",
        )
    
    return EscalaRead.model_validate(escala)


@router.patch("/{escala_id}", response_model=EscalaRead)
async def update_escala(
    escala_id: UUID,
    data: EscalaUpdate,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualizar escala."""
    
    result = await db.execute(
        select(Escala).where(
            Escala.id == escala_id,
            Escala.tenant_id == tenant.tenant_id,
        )
    )
    escala = result.scalar_one_or_none()
    
    if not escala:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escala não encontrada",
        )
    
    update_data = data.model_dump(exclude_unset=True)
    
    # Converter janelas se presente
    if "janelas" in update_data and update_data["janelas"]:
        janelas_dict = {}
        for dia, janela in update_data["janelas"].items():
            janelas_dict[dia] = janela.model_dump() if hasattr(janela, 'model_dump') else janela
        update_data["janelas"] = janelas_dict
    
    if update_data:
        await db.execute(
            update(Escala)
            .where(Escala.id == escala_id)
            .values(**update_data)
        )
        await db.commit()
        await db.refresh(escala)
    
    return EscalaRead.model_validate(escala)


@router.delete("/{escala_id}", response_model=SuccessResponse)
async def delete_escala(
    escala_id: UUID,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Desativar escala."""
    
    result = await db.execute(
        select(Escala).where(
            Escala.id == escala_id,
            Escala.tenant_id == tenant.tenant_id,
        )
    )
    escala = result.scalar_one_or_none()
    
    if not escala:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escala não encontrada",
        )
    
    await db.execute(
        update(Escala)
        .where(Escala.id == escala_id)
        .values(ativa=False)
    )
    await db.commit()
    
    return SuccessResponse(message="Escala desativada")


@router.get("/usuario/{usuario_id}", response_model=EscalaRead)
async def get_escala_usuario(
    usuario_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Obter escala efetiva de um usuário.
    
    Prioridade: Escala individual > Escala da equipe
    """
    from datetime import datetime
    
    now = datetime.utcnow()
    
    # Buscar escala individual
    result = await db.execute(
        select(Escala).where(
            Escala.tenant_id == tenant.tenant_id,
            Escala.usuario_id == usuario_id,
            Escala.ativa == True,
            (Escala.vigencia_inicio.is_(None) | (Escala.vigencia_inicio <= now)),
            (Escala.vigencia_fim.is_(None) | (Escala.vigencia_fim >= now)),
        )
    )
    escala = result.scalar_one_or_none()
    
    if escala:
        return EscalaRead.model_validate(escala)
    
    # Buscar equipe do usuário
    result = await db.execute(
        select(Usuario.equipe_id).where(Usuario.id == usuario_id)
    )
    equipe_id = result.scalar_one_or_none()
    
    if equipe_id:
        # Buscar escala da equipe
        result = await db.execute(
            select(Escala).where(
                Escala.tenant_id == tenant.tenant_id,
                Escala.equipe_id == equipe_id,
                Escala.ativa == True,
                (Escala.vigencia_inicio.is_(None) | (Escala.vigencia_inicio <= now)),
                (Escala.vigencia_fim.is_(None) | (Escala.vigencia_fim >= now)),
            )
        )
        escala = result.scalar_one_or_none()
        
        if escala:
            return EscalaRead.model_validate(escala)
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Nenhuma escala encontrada para este usuário",
    )
