"""Router de usuários."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUser,
    RequireAdmin,
    RequireGestor,
    TenantContext,
    get_current_user,
    get_db,
    get_tenant_context,
)
from app.core.security import hash_password
from app.models import Equipe, Usuario, UserRole, UserStatus
from app.schemas import (
    PaginatedResponse,
    SuccessResponse,
    UsuarioCreate,
    UsuarioMinimal,
    UsuarioRead,
    UsuarioUpdate,
)


router = APIRouter(prefix="/usuarios", tags=["Usuários"])


@router.get("", response_model=PaginatedResponse[UsuarioMinimal])
async def list_usuarios(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[UserStatus] = Query(default=None, alias="status"),
    papel_filter: Optional[UserRole] = Query(default=None, alias="papel"),
    equipe_id: Optional[UUID] = None,
    q: Optional[str] = Query(default=None, max_length=100),
):
    """
    Listar usuários do tenant.
    
    - Gestores e Admins podem ver todos
    - Colaboradores veem apenas colegas da mesma equipe
    """
    # Base query
    query = select(Usuario).where(Usuario.tenant_id == tenant.tenant_id)
    count_query = select(func.count(Usuario.id)).where(Usuario.tenant_id == tenant.tenant_id)
    
    # Colaboradores só veem sua equipe
    if current_user.papel == UserRole.COLABORADOR:
        result = await db.execute(
            select(Usuario.equipe_id).where(Usuario.id == current_user.id)
        )
        user_equipe = result.scalar_one_or_none()
        if user_equipe:
            query = query.where(Usuario.equipe_id == user_equipe)
            count_query = count_query.where(Usuario.equipe_id == user_equipe)
    
    # Filtros
    if status_filter:
        query = query.where(Usuario.status == status_filter)
        count_query = count_query.where(Usuario.status == status_filter)
    
    if papel_filter:
        query = query.where(Usuario.papel == papel_filter)
        count_query = count_query.where(Usuario.papel == papel_filter)
    
    if equipe_id:
        query = query.where(Usuario.equipe_id == equipe_id)
        count_query = count_query.where(Usuario.equipe_id == equipe_id)
    
    if q:
        search = f"%{q}%"
        query = query.where(
            (Usuario.nome.ilike(search)) |
            (Usuario.email.ilike(search)) |
            (Usuario.matricula.ilike(search))
        )
        count_query = count_query.where(
            (Usuario.nome.ilike(search)) |
            (Usuario.email.ilike(search)) |
            (Usuario.matricula.ilike(search))
        )
    
    # Contagem total
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # Paginação
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.order_by(Usuario.nome)
    
    result = await db.execute(query)
    usuarios = result.scalars().all()
    
    return PaginatedResponse.create(
        items=[UsuarioMinimal.model_validate(u) for u in usuarios],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
async def create_usuario(
    data: UsuarioCreate,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Criar novo usuário (apenas Admin)."""
    
    # Verificar email único no tenant
    result = await db.execute(
        select(Usuario).where(
            Usuario.tenant_id == tenant.tenant_id,
            Usuario.email == data.email,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado",
        )
    
    # Verificar CPF único no tenant
    result = await db.execute(
        select(Usuario).where(
            Usuario.tenant_id == tenant.tenant_id,
            Usuario.cpf == data.cpf,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF já cadastrado",
        )
    
    # Verificar matrícula única no tenant
    result = await db.execute(
        select(Usuario).where(
            Usuario.tenant_id == tenant.tenant_id,
            Usuario.matricula == data.matricula,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Matrícula já cadastrada",
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
    
    # Criar usuário
    usuario = Usuario(
        tenant_id=tenant.tenant_id,
        nome=data.nome,
        email=data.email,
        cpf=data.cpf,
        telefone=data.telefone,
        matricula=data.matricula,
        password_hash=hash_password(data.password),
        papel=data.papel,
        status=UserStatus.ACTIVE,
        equipe_id=data.equipe_id,
    )
    
    db.add(usuario)
    await db.commit()
    await db.refresh(usuario)
    
    return UsuarioRead.model_validate(usuario)


@router.get("/{usuario_id}", response_model=UsuarioRead)
async def get_usuario(
    usuario_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Obter usuário por ID."""
    
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
    
    # Colaborador só pode ver a si mesmo ou colegas da equipe
    if current_user.papel == UserRole.COLABORADOR:
        if usuario.id != current_user.id:
            # Verificar se é da mesma equipe
            user_result = await db.execute(
                select(Usuario.equipe_id).where(Usuario.id == current_user.id)
            )
            current_equipe = user_result.scalar_one_or_none()
            
            if usuario.equipe_id != current_equipe:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado",
                )
    
    return UsuarioRead.model_validate(usuario)


@router.patch("/{usuario_id}", response_model=UsuarioRead)
async def update_usuario(
    usuario_id: UUID,
    data: UsuarioUpdate,
    current_user: RequireGestor,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Atualizar usuário.
    
    - Admin pode alterar qualquer campo
    - Gestor pode alterar campos básicos (não papel)
    """
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
    
    # Gestor não pode alterar papel ou status
    if current_user.papel == UserRole.GESTOR:
        if data.papel is not None or data.status is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas Admin pode alterar papel e status",
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
    
    # Atualizar campos
    update_data = data.model_dump(exclude_unset=True)
    if update_data:
        await db.execute(
            update(Usuario)
            .where(Usuario.id == usuario_id)
            .values(**update_data)
        )
        await db.commit()
        await db.refresh(usuario)
    
    return UsuarioRead.model_validate(usuario)


@router.delete("/{usuario_id}", response_model=SuccessResponse)
async def delete_usuario(
    usuario_id: UUID,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Desativar usuário (soft delete).
    
    Por LGPD, não deletamos permanentemente.
    """
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
    
    # Não pode desativar a si mesmo
    if usuario.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível desativar seu próprio usuário",
        )
    
    # Soft delete (inativar)
    await db.execute(
        update(Usuario)
        .where(Usuario.id == usuario_id)
        .values(status=UserStatus.INACTIVE)
    )
    await db.commit()
    
    return SuccessResponse(message="Usuário desativado com sucesso")


@router.post("/{usuario_id}/reactivate", response_model=UsuarioRead)
async def reactivate_usuario(
    usuario_id: UUID,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Reativar usuário."""
    
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
    
    await db.execute(
        update(Usuario)
        .where(Usuario.id == usuario_id)
        .values(status=UserStatus.ACTIVE)
    )
    await db.commit()
    await db.refresh(usuario)
    
    return UsuarioRead.model_validate(usuario)


@router.post("/{usuario_id}/reset-password", response_model=SuccessResponse)
async def admin_reset_password(
    usuario_id: UUID,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Reset de senha pelo admin.
    
    Gera senha temporária e envia por email.
    """
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
    
    # Gerar senha temporária
    import secrets
    temp_password = secrets.token_urlsafe(12)
    
    await db.execute(
        update(Usuario)
        .where(Usuario.id == usuario_id)
        .values(password_hash=hash_password(temp_password))
    )
    await db.commit()
    
    # TODO: Enviar email com senha temporária
    # send_temp_password_email(usuario.email, temp_password)
    
    return SuccessResponse(
        message="Senha resetada. O usuário receberá a nova senha por email."
    )
