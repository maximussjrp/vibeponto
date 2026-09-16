"""Schemas de autenticação."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.models import UserRole, UserStatus
from app.schemas.base import BaseSchema, TimestampSchema


# ============================================================================
# AUTH
# ============================================================================

class LoginRequest(BaseSchema):
    """Request de login."""
    
    email: EmailStr
    tenant_id: Optional[UUID] = None
    password: str = Field(..., min_length=8)
    mfa_code: Optional[str] = Field(None, min_length=6, max_length=6)
    device_id: Optional[str] = None
    device_info: Optional[dict] = None


class LoginResponse(BaseSchema):
    """Response de login."""
    
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int
    user: "UsuarioRead"
    requires_mfa: bool = False


class RefreshTokenRequest(BaseSchema):
    """Request de refresh token."""
    
    refresh_token: Optional[str] = None


class TokenResponse(BaseSchema):
    """Response de token."""
    
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int


class PasswordChangeRequest(BaseSchema):
    """Request de troca de senha."""
    
    current_password: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)
    
    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("As senhas não conferem")
        return v


class PasswordResetRequest(BaseSchema):
    """Request de reset de senha."""
    
    email: EmailStr
    tenant_id: Optional[UUID] = None


class PasswordResetConfirm(BaseSchema):
    """Confirmação de reset de senha."""
    
    token: str
    new_password: str = Field(..., min_length=8)


# ============================================================================
# MFA
# ============================================================================

class MFASetupResponse(BaseSchema):
    """Response de setup MFA."""
    
    secret: str
    qr_code_uri: str
    backup_codes: list[str]


class MFAVerifyRequest(BaseSchema):
    """Request de verificação MFA."""
    
    code: str = Field(..., min_length=6, max_length=6)


class MFADisableRequest(BaseSchema):
    """Request para desabilitar MFA."""
    
    password: str
    code: str = Field(..., min_length=6, max_length=6)


# ============================================================================
# USUÁRIO
# ============================================================================

class UsuarioBase(BaseSchema):
    """Schema base de usuário."""
    
    nome: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    cpf: str = Field(..., min_length=11, max_length=14)
    telefone: Optional[str] = Field(None, max_length=20)
    matricula: str = Field(..., min_length=1, max_length=50)


class UsuarioCreate(UsuarioBase):
    """Schema para criar usuário."""
    
    password: str = Field(..., min_length=8)
    papel: UserRole = UserRole.COLABORADOR
    equipe_id: Optional[UUID] = None


class UsuarioUpdate(BaseSchema):
    """Schema para atualizar usuário."""
    
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    telefone: Optional[str] = Field(None, max_length=20)
    equipe_id: Optional[UUID] = None
    papel: Optional[UserRole] = None
    status: Optional[UserStatus] = None


class UsuarioRead(UsuarioBase, TimestampSchema):
    """Schema de leitura de usuário."""
    
    id: UUID
    tenant_id: UUID
    papel: UserRole
    status: UserStatus
    mfa_enabled: bool
    foto_base_url: Optional[str] = None
    equipe_id: Optional[UUID] = None
    ultimo_login: Optional[datetime] = None


class UsuarioMinimal(BaseSchema):
    """Schema mínimo de usuário (para listas)."""
    
    id: UUID
    nome: str
    email: EmailStr
    matricula: str
    papel: UserRole
    status: UserStatus


# ============================================================================
# TENANT
# ============================================================================

class TenantBase(BaseSchema):
    """Schema base de tenant."""
    
    nome: str = Field(..., min_length=2, max_length=255)
    cnpj: str = Field(..., min_length=14, max_length=18)
    email: EmailStr
    telefone: Optional[str] = Field(None, max_length=20)


class TenantCreate(TenantBase):
    """Schema para criar tenant."""
    
    endereco: Optional[dict] = None
    config: Optional[dict] = None
    
    # Admin inicial
    admin_nome: str = Field(..., min_length=2, max_length=255)
    admin_email: EmailStr
    admin_cpf: str = Field(..., min_length=11, max_length=14)
    admin_password: str = Field(..., min_length=8)


class TenantUpdate(BaseSchema):
    """Schema para atualizar tenant."""
    
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    telefone: Optional[str] = Field(None, max_length=20)
    endereco: Optional[dict] = None
    config: Optional[dict] = None


class TenantRead(TenantBase, TimestampSchema):
    """Schema de leitura de tenant."""
    
    id: UUID
    ativo: bool
    endereco: Optional[dict] = None
    config: Optional[dict] = None


class RegisterTenantRequest(BaseSchema):
    """Request de registro de novo tenant (SaaS)."""
    
    # Empresa
    empresa_nome: str = Field(..., min_length=3, max_length=255)
    empresa_cnpj: str = Field(..., min_length=14, max_length=14)
    empresa_email: EmailStr
    empresa_telefone: Optional[str] = Field(None, max_length=20)
    
    # Admin
    admin_nome: str = Field(..., min_length=3, max_length=255)
    admin_email: EmailStr
    admin_senha: str = Field(..., min_length=8)
    
    # Plano
    plano: str = Field(default="professional")


class RegisterTenantResponse(BaseSchema):
    """Response de registro de tenant."""
    
    tenant_id: UUID
    tenant_slug: str
    admin_id: UUID
    message: str


# ============================================================================
# EQUIPE
# ============================================================================

class EquipeBase(BaseSchema):
    """Schema base de equipe."""
    
    nome: str = Field(..., min_length=2, max_length=255)
    descricao: Optional[str] = None


class EquipeCreate(EquipeBase):
    """Schema para criar equipe."""
    
    lider_id: Optional[UUID] = None
    config: Optional[dict] = None


class EquipeUpdate(BaseSchema):
    """Schema para atualizar equipe."""
    
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    descricao: Optional[str] = None
    lider_id: Optional[UUID] = None
    config: Optional[dict] = None
    ativa: Optional[bool] = None


class EquipeRead(EquipeBase, TimestampSchema):
    """Schema de leitura de equipe."""
    
    id: UUID
    tenant_id: UUID
    lider_id: Optional[UUID] = None
    config: Optional[dict] = None
    ativa: bool


class EquipeWithMembers(EquipeRead):
    """Schema de equipe com membros."""
    
    membros: list[UsuarioMinimal] = []


# Circular import resolution
LoginResponse.model_rebuild()
