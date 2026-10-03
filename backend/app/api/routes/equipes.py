"""Router de equipes."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    CurrentUser,
    RequireAdmin,
    RequireGestor,
    TenantContext,
    get_current_user,
    get_db,
    get_tenant_context,
)
from app.models import Equipe, Usuario, UserRole, UserStatus
from app.schemas import (
    EquipeCreate,
    EquipeRead,
    EquipeUpdate,
    EquipeWithMembers,
    PaginatedResponse,
    SuccessResponse,
    UsuarioMinimal,
    EquipeMembroMinimal,
)


router = APIRouter(prefix="/equipes", tags=["Equipes"])


@router.get("", response_model=PaginatedResponse[EquipeRead])
async def list_equipes(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    ativa: Optional[bool] = None,
    q: Optional[str] = Query(default=None, max_length=100),
):
    """Listar equipes do tenant."""

    query = select(Equipe).where(Equipe.tenant_id == tenant.tenant_id)
    count_query = select(func.count(Equipe.id)).where(Equipe.tenant_id == tenant.tenant_id)

    if ativa is not None:
        query = query.where(Equipe.ativa == ativa)
        count_query = count_query.where(Equipe.ativa == ativa)

    if q:
        search = f"%{q}%"
        query = query.where(Equipe.nome.ilike(search))
        count_query = count_query.where(Equipe.nome.ilike(search))

    # Total
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Paginação
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.order_by(Equipe.nome)

    result = await db.execute(query)
    equipes = result.scalars().all()

    return PaginatedResponse.create(
        items=[EquipeRead.model_validate(e) for e in equipes],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=EquipeRead, status_code=status.HTTP_201_CREATED)
async def create_equipe(
    data: EquipeCreate,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Criar nova equipe (apenas Admin)."""

    # Verificar líder existe e é elegível (ativo, gestor/admin_dp, mesmo tenant)
    if data.lider_id:
        result = await db.execute(
            select(Usuario).where(
                Usuario.id == data.lider_id,
                Usuario.tenant_id == tenant.tenant_id,
            )
        )
        lider = result.scalar_one_or_none()
        if not lider or lider.status != UserStatus.ACTIVE or lider.papel not in (UserRole.GESTOR, UserRole.ADMIN_DP):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Líder inelegível ou de outro tenant",
            )

    equipe = Equipe(
        tenant_id=tenant.tenant_id,
        nome=data.nome,
        descricao=data.descricao,
        lider_id=data.lider_id,
        config=data.config or {},
    )

    db.add(equipe)
    await db.commit()
    await db.refresh(equipe)

    return EquipeRead.model_validate(equipe)


@router.get("/{equipe_id}", response_model=EquipeWithMembers)
async def get_equipe(
    equipe_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Obter equipe com membros."""

    result = await db.execute(
        select(Equipe)
        .options(selectinload(Equipe.membros))
        .where(
            Equipe.id == equipe_id,
            Equipe.tenant_id == tenant.tenant_id,
        )
    )
    equipe = result.scalar_one_or_none()

    if not equipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipe não encontrada",
        )

    if current_user.papel == UserRole.COLABORADOR and current_user.equipe_id != equipe_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado a membros de outras equipes",
        )

    response = EquipeWithMembers.model_validate(equipe)
    if current_user.papel == UserRole.ADMIN_DP or (current_user.papel == UserRole.GESTOR and equipe.lider_id == current_user.id):
        response.membros = [UsuarioMinimal.model_validate(m) for m in equipe.membros]
    else:
        response.membros = [EquipeMembroMinimal.model_validate(m) for m in equipe.membros]

    return response


@router.patch("/{equipe_id}", response_model=EquipeRead)
async def update_equipe(
    equipe_id: UUID,
    data: EquipeUpdate,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualizar equipe."""

    result = await db.execute(
        select(Equipe).where(
            Equipe.id == equipe_id,
            Equipe.tenant_id == tenant.tenant_id,
        )
    )
    equipe = result.scalar_one_or_none()

    if not equipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipe não encontrada",
        )

    if current_user.papel == UserRole.GESTOR:
        if equipe.lider_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gestor só pode atualizar equipes lideradas por ele",
            )
        if "lider_id" in data.model_fields_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas Admin pode alterar a liderança da equipe",
            )
        if "ativa" in data.model_fields_set or "config" in data.model_fields_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas Admin pode alterar o estado ou configurações da equipe",
            )

    # Verificar líder existe e é elegível (para Admin DP alterando lider_id)
    if "lider_id" in data.model_fields_set and data.lider_id is not None:
        result = await db.execute(
            select(Usuario).where(
                Usuario.id == data.lider_id,
                Usuario.tenant_id == tenant.tenant_id,
            )
        )
        lider = result.scalar_one_or_none()
        if not lider or lider.status != UserStatus.ACTIVE or lider.papel not in (UserRole.GESTOR, UserRole.ADMIN_DP):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Líder inelegível ou de outro tenant",
            )

    update_data = data.model_dump(exclude_unset=True)
    if update_data:
        await db.execute(
            update(Equipe)
            .where(Equipe.id == equipe_id)
            .values(**update_data)
        )
        await db.commit()
        await db.refresh(equipe)

    return EquipeRead.model_validate(equipe)


@router.delete("/{equipe_id}", response_model=SuccessResponse)
async def delete_equipe(
    equipe_id: UUID,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Desativar equipe."""

    result = await db.execute(
        select(Equipe).where(
            Equipe.id == equipe_id,
            Equipe.tenant_id == tenant.tenant_id,
        )
    )
    equipe = result.scalar_one_or_none()

    if not equipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipe não encontrada",
        )

    # Verificar se tem membros
    result = await db.execute(
        select(func.count(Usuario.id)).where(Usuario.equipe_id == equipe_id)
    )
    member_count = result.scalar_one()

    if member_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Equipe possui {member_count} membros. Remova-os primeiro.",
        )

    # Soft delete
    await db.execute(
        update(Equipe)
        .where(Equipe.id == equipe_id)
        .values(ativa=False)
    )
    await db.commit()

    return SuccessResponse(message="Equipe desativada com sucesso")


@router.post("/{equipe_id}/membros/{usuario_id}", response_model=SuccessResponse)
async def add_membro(
    equipe_id: UUID,
    usuario_id: UUID,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Adicionar membro à equipe."""

    # Verificar equipe
    result = await db.execute(
        select(Equipe).where(
            Equipe.id == equipe_id,
            Equipe.tenant_id == tenant.tenant_id,
        )
    )
    equipe = result.scalar_one_or_none()
    if not equipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipe não encontrada",
        )

    if current_user.papel == UserRole.GESTOR:
        if not equipe.ativa:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gestor só pode gerenciar membros em equipes ativas",
            )
        if equipe.lider_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gestor só pode adicionar membros em equipes lideradas por ele",
            )

    # Verificar usuário
    result = await db.execute(
        select(Usuario).where(
            Usuario.id == usuario_id,
            Usuario.tenant_id == tenant.tenant_id,
        )
    )
    usuario = result.scalar_one_or_none()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )

    if current_user.papel == UserRole.GESTOR:
        if usuario.papel != UserRole.COLABORADOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gestor só pode gerenciar colaboradores em equipes",
            )

    if current_user.papel == UserRole.GESTOR and usuario.equipe_id is not None and usuario.equipe_id != equipe_id:
        res_orig = await db.execute(
            select(Equipe).where(
                Equipe.id == usuario.equipe_id,
                Equipe.tenant_id == tenant.tenant_id,
            )
        )
        equipe_orig = res_orig.scalar_one_or_none()
        if not equipe_orig or equipe_orig.lider_id != current_user.id or not equipe_orig.ativa:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gestor só pode transferir membros de equipes ativas lideradas por ele",
            )

    # Atualizar equipe do usuário
    await db.execute(
        update(Usuario)
        .where(Usuario.id == usuario_id)
        .values(equipe_id=equipe_id)
    )
    await db.commit()

    return SuccessResponse(message="Membro adicionado à equipe")


@router.delete("/{equipe_id}/membros/{usuario_id}", response_model=SuccessResponse)
async def remove_membro(
    equipe_id: UUID,
    usuario_id: UUID,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Remover membro da equipe."""

    # Verificar usuário está na equipe
    result = await db.execute(
        select(Usuario).where(
            Usuario.id == usuario_id,
            Usuario.tenant_id == tenant.tenant_id,
            Usuario.equipe_id == equipe_id,
        )
    )
    usuario = result.scalar_one_or_none()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado nesta equipe",
        )

    if current_user.papel == UserRole.GESTOR:
        if usuario.papel != UserRole.COLABORADOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gestor só pode gerenciar colaboradores em equipes",
            )
        res_eq = await db.execute(
            select(Equipe).where(
                Equipe.id == equipe_id,
                Equipe.tenant_id == tenant.tenant_id,
            )
        )
        eq = res_eq.scalar_one_or_none()
        if not eq or eq.lider_id != current_user.id or not eq.ativa:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gestor só pode remover membros de equipes ativas lideradas por ele",
            )

    # Remover da equipe
    await db.execute(
        update(Usuario)
        .where(Usuario.id == usuario_id)
        .values(equipe_id=None)
    )
    await db.commit()

    return SuccessResponse(message="Membro removido da equipe")
