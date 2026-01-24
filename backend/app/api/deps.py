"""Dependências e utilidades de autenticação."""

from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models import Usuario, UserRole, UserStatus


security = HTTPBearer()


class CurrentUser:
    """Dados do usuário autenticado."""
    
    def __init__(
        self,
        id: UUID,
        tenant_id: UUID,
        email: str,
        nome: str,
        papel: UserRole,
        status: UserStatus,
    ):
        self.id = id
        self.tenant_id = tenant_id
        self.email = email
        self.nome = nome
        self.papel = papel
        self.status = status
    
    def is_admin(self) -> bool:
        return self.papel == UserRole.ADMIN_DP
    
    def is_gestor(self) -> bool:
        return self.papel in (UserRole.ADMIN_DP, UserRole.GESTOR)
    
    def has_role(self, *roles: UserRole) -> bool:
        return self.papel in roles


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """Obtém o usuário atual a partir do token JWT."""
    
    token = credentials.credentials
    
    try:
        payload = decode_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )
    
    # Buscar usuário
    result = await db.execute(
        select(Usuario).where(Usuario.id == UUID(user_id))
    )
    usuario = result.scalar_one_or_none()
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
        )
    
    if usuario.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo ou suspenso",
        )
    
    return CurrentUser(
        id=usuario.id,
        tenant_id=usuario.tenant_id,
        email=usuario.email,
        nome=usuario.nome,
        papel=usuario.papel,
        status=usuario.status,
    )


async def get_current_active_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Garante que o usuário está ativo."""
    if current_user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo",
        )
    return current_user


def require_roles(*allowed_roles: UserRole):
    """Decorator para exigir papéis específicos."""
    
    async def role_checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current_user.papel not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Papéis permitidos: {', '.join(r.value for r in allowed_roles)}",
            )
        return current_user
    
    return role_checker


# Dependências prontas para uso
RequireAdmin = Annotated[CurrentUser, Depends(require_roles(UserRole.ADMIN_DP))]
RequireGestor = Annotated[CurrentUser, Depends(require_roles(UserRole.ADMIN_DP, UserRole.GESTOR))]
RequireAuditor = Annotated[CurrentUser, Depends(require_roles(UserRole.ADMIN_DP, UserRole.AUDITOR))]
RequireFinanceiro = Annotated[CurrentUser, Depends(require_roles(UserRole.ADMIN_DP, UserRole.FINANCEIRO))]


class TenantContext:
    """Contexto do tenant para queries multi-tenant."""
    
    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
    
    def filter_query(self, query, model):
        """Adiciona filtro de tenant à query."""
        if hasattr(model, "tenant_id"):
            return query.where(model.tenant_id == self.tenant_id)
        return query


async def get_tenant_context(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> TenantContext:
    """Obtém contexto do tenant do usuário atual."""
    return TenantContext(current_user.tenant_id)
