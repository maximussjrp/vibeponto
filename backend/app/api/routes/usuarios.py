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
    UsuarioMinimalColaborador,
    UsuarioRead,
    UsuarioReadOperacional,
    UsuarioReadGestor,
    UsuarioReadAuditor,
    UsuarioUpdate,
)


from app.services.password_reset import execute_password_reset_request, PasswordResetEmailError


router = APIRouter(prefix="/usuarios", tags=["Usuários"])



@router.get("")
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
    
    # Colaboradores só veem sua equipe (ou apenas a si próprios se sem equipe)
    if current_user.papel == UserRole.COLABORADOR:
        result = await db.execute(
            select(Usuario.equipe_id).where(Usuario.id == current_user.id)
        )
        user_equipe = result.scalar_one_or_none()
        if user_equipe is not None:
            query = query.where(Usuario.equipe_id == user_equipe)
            count_query = count_query.where(Usuario.equipe_id == user_equipe)
        else:
            query = query.where(Usuario.id == current_user.id)
            count_query = count_query.where(Usuario.id == current_user.id)
    
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
    
    if current_user.papel == UserRole.COLABORADOR:
        items = [UsuarioMinimalColaborador.model_validate(u) for u in usuarios]
    elif current_user.papel in (UserRole.GESTOR, UserRole.FINANCEIRO):
        items = [UsuarioReadGestor.model_validate(u) for u in usuarios]
    elif current_user.papel == UserRole.AUDITOR:
        items = [UsuarioReadAuditor.model_validate(u) for u in usuarios]
    else:
        items = [UsuarioRead.model_validate(u) for u in usuarios]

    return PaginatedResponse.create(
        items=items,
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


@router.get("/{usuario_id}")
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
            
            if current_equipe is None or usuario.equipe_id != current_equipe:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado",
                )
    
    if current_user.papel == UserRole.COLABORADOR:
        return UsuarioMinimalColaborador.model_validate(usuario)
    elif current_user.papel in (UserRole.GESTOR, UserRole.FINANCEIRO):
        return UsuarioReadGestor.model_validate(usuario)
    elif current_user.papel == UserRole.AUDITOR:
        return UsuarioReadAuditor.model_validate(usuario)

    return UsuarioRead.model_validate(usuario)


@router.patch("/{usuario_id}", response_model=UsuarioReadOperacional)
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
    - Gestor pode alterar apenas colaboradores de sua equipe (não papel/status)
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
    
    # Se for GESTOR: apenas colaboradores, validar equipe de origem E destino (atividades ativas)
    if current_user.papel == UserRole.GESTOR:
        if usuario.papel != UserRole.COLABORADOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gestor só pode editar colaboradores",
            )
        if data.papel is not None or data.status is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas Admin pode alterar papel e status",
            )
            
        if usuario.equipe_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gestor só pode alterar usuários de sua própria equipe",
            )
            
        res_orig = await db.execute(
            select(Equipe).where(
                Equipe.id == usuario.equipe_id,
                Equipe.tenant_id == tenant.tenant_id,
            )
        )
        equipe_origem = res_orig.scalar_one_or_none()
        if not equipe_origem or equipe_origem.lider_id != current_user.id or not equipe_origem.ativa:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gestor só pode alterar usuários de sua própria equipe ativa",
            )
            
        if data.equipe_id is not None and data.equipe_id != usuario.equipe_id:
            res_dest = await db.execute(
                select(Equipe).where(
                    Equipe.id == data.equipe_id,
                    Equipe.tenant_id == tenant.tenant_id,
                )
            )
            equipe_destino = res_dest.scalar_one_or_none()
            if not equipe_destino:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Equipe de destino não encontrada",
                )
            if equipe_destino.lider_id != current_user.id or not equipe_destino.ativa:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Gestor só pode transferir usuários para equipes ativas lideradas por ele",
                )

    # Verificar equipe existe (para admin ou gestor)
    if data.equipe_id and current_user.papel != UserRole.GESTOR:
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
    
    role_changed = data.papel is not None and data.papel != usuario.papel

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
        
    if role_changed:
        from app.core.redis import get_redis
        redis = await get_redis()
        await redis.revoke_all_user_sessions(str(usuario_id))
    
    if current_user.papel == UserRole.COLABORADOR:
        return UsuarioMinimalColaborador.model_validate(usuario)
    elif current_user.papel in (UserRole.GESTOR, UserRole.FINANCEIRO):
        return UsuarioReadGestor.model_validate(usuario)
    elif current_user.papel == UserRole.AUDITOR:
        return UsuarioReadAuditor.model_validate(usuario)

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
    
    from app.core.redis import get_redis
    redis = await get_redis()
    await redis.revoke_all_user_sessions(str(usuario_id))
    
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


@router.post("/{usuario_id}/suspend", response_model=UsuarioRead)
async def suspend_usuario(
    usuario_id: UUID,
    current_user: RequireAdmin,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Suspender usuário e revogar sessões ativas (apenas Admin)."""
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
    
    if usuario.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível suspender seu próprio usuário",
        )
    
    await db.execute(
        update(Usuario)
        .where(Usuario.id == usuario_id)
        .values(status=UserStatus.SUSPENDED)
    )
    await db.commit()
    await db.refresh(usuario)
    
    from app.core.redis import get_redis
    redis = await get_redis()
    await redis.revoke_all_user_sessions(str(usuario_id))
    
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
    
    Gera token de recuperação seguro sem alterar password_hash diretamente.
    Retorna erro 502 explícito para o admin se o e-mail falhar.
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
    
    try:
        await execute_password_reset_request(
            user_id=str(usuario.id),
            email=usuario.email,
            nome=usuario.nome,
        )
    except PasswordResetEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )
    
    return SuccessResponse(
        message="Link de recuperação de senha gerado e enviado ao usuário."
    )

