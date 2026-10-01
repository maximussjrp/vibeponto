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
    mfa_code: Optional[str] = Field(None, min_length=6, max_length=32)
    device_id: Optional[str] = None
    device_info: Optional[dict] = None

    @field_validator("email")
    @classmethod
    def normalize_login_email(cls, v: str) -> str:
        return v.strip().lower() if v else v


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

    @field_validator("email")
    @classmethod
    def normalize_reset_email(cls, v: str) -> str:
        return v.strip().lower() if v else v


class PasswordResetConfirm(BaseSchema):
    """Confirmação de reset de senha."""
    
    token: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)

    @field_validator("confirm_password")
    @classmethod
    def confirm_password_matches(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("As senhas não conferem")
        return v


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
    code: str = Field(..., min_length=6, max_length=32)


# ============================================================================
# USUÁRIO
# ============================================================================

def sanitize_and_validate_cpf(v: Optional[str]) -> Optional[str]:
    """Sanitizar e validar dígitos de CPF pelo algoritmo Módulo 11."""
    if not v:
        return None
    digits = [int(c) for c in v if c.isdigit()]
    if len(digits) == 0:
        return None
    if len(digits) != 11:
        raise ValueError("CPF deve conter exatamente 11 dígitos numéricos")
    if len(set(digits)) == 1:
        raise ValueError("CPF inválido (sequência repetida)")
    s1 = sum(d * w for d, w in zip(digits[:9], range(10, 1, -1)))
    r1 = (s1 * 10) % 11
    if r1 == 10:
        r1 = 0
    if r1 != digits[9]:
        raise ValueError("CPF inválido (dígito verificador incorreto)")
    s2 = sum(d * w for d, w in zip(digits[:10], range(11, 1, -1)))
    r2 = (s2 * 10) % 11
    if r2 == 10:
        r2 = 0
    if r2 != digits[10]:
        raise ValueError("CPF inválido (dígito verificador incorreto)")
    return "".join(str(d) for d in digits)


class UsuarioBase(BaseSchema):
    """Schema base de usuário."""
    
    nome: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    cpf: Optional[str] = Field(None, max_length=14)
    telefone: Optional[str] = Field(None, max_length=20)
    matricula: str = Field(..., min_length=1, max_length=50)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower() if v else v

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_and_validate_cpf(v)


class UsuarioCreate(UsuarioBase):
    """Schema para criar usuário."""
    
    cpf: str = Field(..., min_length=11, max_length=14)
    password: str = Field(..., min_length=8)
    papel: UserRole = UserRole.COLABORADOR
    equipe_id: Optional[UUID] = None

    @field_validator("cpf")
    @classmethod
    def validate_cpf_required(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("CPF é obrigatório para cadastro de usuário")
        res = sanitize_and_validate_cpf(v)
        if not res:
            raise ValueError("CPF é obrigatório para cadastro de usuário")
        return res



class UsuarioUpdate(BaseSchema):
    """Schema para atualizar usuário."""
    
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    telefone: Optional[str] = Field(None, max_length=20)
    equipe_id: Optional[UUID] = None
    papel: Optional[UserRole] = None
    status: Optional[UserStatus] = None


class UsuarioSelfUpdate(BaseSchema):
    """Schema de auto-serviço (próprio colaborador)."""
    
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    telefone: Optional[str] = Field(None, max_length=20)


class UsuarioRead(UsuarioBase, TimestampSchema):
    """Schema de leitura administrativa completa de usuário."""
    
    id: UUID
    tenant_id: UUID
    papel: UserRole
    status: UserStatus
    mfa_enabled: bool
    foto_base_url: Optional[str] = None
    equipe_id: Optional[UUID] = None
    ultimo_login: Optional[datetime] = None


class UsuarioMinimal(BaseSchema):
    """Schema mínimo de usuário (para listas gerais)."""
    
    id: UUID
    nome: str
    email: EmailStr
    matricula: str
    papel: UserRole
    status: UserStatus
    equipe_id: Optional[UUID] = None


class UsuarioMinimalColaborador(BaseSchema):
    """Schema mínimo sanitizado para colaboradores (sem PII de contato/documentos)."""
    
    id: UUID
    nome: str
    papel: UserRole
    status: UserStatus
    equipe_id: Optional[UUID] = None


class UsuarioReadGestor(BaseSchema):
    """Schema de leitura operacional para Gestores (sem CPF, MFA, telefone, ultimo_login)."""
    
    id: UUID
    tenant_id: UUID
    nome: str
    email: EmailStr
    matricula: str
    papel: UserRole
    status: UserStatus
    foto_base_url: Optional[str] = None
    equipe_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class UsuarioReadAuditor(BaseSchema):
    """Schema de leitura para Auditores (CPF mascarado, sem segredos/MFA)."""
    
    id: UUID
    tenant_id: UUID
    nome: str
    email: EmailStr
    matricula: str
    cpf: Optional[str] = None
    papel: UserRole
    status: UserStatus
    equipe_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("cpf")
    @classmethod
    def mask_cpf_for_auditor(cls, v: Optional[str]) -> Optional[str]:
        if not v or len(v) < 11:
            return None
        clean = "".join(filter(str.isdigit, v))
        return f"***.***.{clean[6:9]}-{clean[9:11]}"


class EquipeMembroMinimal(BaseSchema):
    """Schema mínimo para membros de equipe (sem PII sensível)."""

    id: UUID
    nome: str
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

    @field_validator("email")
    @classmethod
    def normalize_tenant_email(cls, v: str) -> str:
        return v.strip().lower() if v else v


class TenantCreate(TenantBase):
    """Schema para criar tenant."""
    
    endereco: Optional[dict] = None
    config: Optional[dict] = None
    
    # Admin inicial
    admin_nome: str = Field(..., min_length=2, max_length=255)
    admin_email: EmailStr
    admin_cpf: Optional[str] = Field(None, max_length=14)
    admin_password: str = Field(..., min_length=8)

    @field_validator("admin_email")
    @classmethod
    def normalize_admin_email(cls, v: str) -> str:
        return v.strip().lower() if v else v

    @field_validator("admin_cpf")
    @classmethod
    def validate_admin_cpf(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_and_validate_cpf(v)


class TenantUpdate(BaseSchema):
    """Schema para atualizar tenant."""
    
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    telefone: Optional[str] = Field(None, max_length=20)
    endereco: Optional[dict] = None
    config: Optional[dict] = None

    @field_validator("email")
    @classmethod
    def normalize_tenant_update_email(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if v else v


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

    @field_validator("empresa_email", "admin_email")
    @classmethod
    def normalize_reg_emails(cls, v: str) -> str:
        return v.strip().lower() if v else v


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


from typing import Union

class EquipeWithMembers(EquipeRead):
    """Schema de equipe com membros."""
    
    membros: list[Union[UsuarioMinimal, EquipeMembroMinimal, UsuarioMinimalColaborador]] = []


# Circular import resolution
LoginResponse.model_rebuild()
