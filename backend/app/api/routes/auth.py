"""Router de autenticação."""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_db
from app.core.config import settings
from app.core.sessions import (
    COOKIE_NAME, check_cookie_origin, clear_refresh_cookie, cookie_mode, digest,
    issue_tokens, set_refresh_cookie, unauthorized, validate_session,
)
from app.core.rate_limit import auth_rate_limit
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_totp_secret,
    get_totp_uri,
    hash_password,
    verify_password,
    verify_totp,
)
from app.models import Usuario, UserStatus, Tenant, UserRole
from app.schemas import (
    LoginRequest,
    LoginResponse,
    MFADisableRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RegisterTenantRequest,
    RegisterTenantResponse,
    SuccessResponse,
    TokenResponse,
    UsuarioRead,
)


router = APIRouter(prefix="/auth", tags=["Autenticação"], dependencies=[Depends(auth_rate_limit)])


def generate_slug(nome: str) -> str:
    """Gerar slug a partir do nome da empresa."""
    import re
    import unicodedata
    
    # Normalizar e remover acentos
    slug = unicodedata.normalize('NFKD', nome.lower())
    slug = slug.encode('ASCII', 'ignore').decode('ASCII')
    # Remover caracteres especiais
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    # Remover hífens do início e fim
    slug = slug.strip('-')
    return slug[:50]  # Limitar tamanho


@router.post("/register-tenant", response_model=RegisterTenantResponse)
async def register_tenant(
    request: RegisterTenantRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Registrar nova empresa (tenant) no sistema SaaS.
    
    - Cria o tenant com os dados da empresa
    - Cria o usuário administrador inicial
    - Retorna os IDs criados
    """
    from uuid import uuid4
    
    # Verificar se CNPJ já existe
    existing_tenant = await db.execute(
        select(Tenant.id).where(Tenant.cnpj == request.empresa_cnpj)
    )
    if existing_tenant.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CNPJ já cadastrado no sistema",
        )
    
    # Verificar se email do admin já existe
    existing_user = await db.execute(
        select(Usuario.id).where(Usuario.email == request.admin_email)
    )
    if existing_user.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado no sistema",
        )
    
    # Gerar slug único
    base_slug = generate_slug(request.empresa_nome)
    slug = base_slug
    counter = 1
    while True:
        existing_slug = await db.execute(
            select(Tenant.id).where(Tenant.config["slug"].astext == slug)
        )
        if not existing_slug.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    # Criar Tenant
    tenant_id = uuid4()
    tenant = Tenant(
        id=tenant_id,
        nome=request.empresa_nome,
        cnpj=request.empresa_cnpj,
        email=request.empresa_email,
        telefone=request.empresa_telefone,
        ativo=True,
        config={
            "slug": slug,
            "plano": request.plano,
            "jornada_diaria": 8,
            "tolerancia_minutos": 10,
            "permite_hora_extra": True,
            "requer_foto": True,
            "requer_geolocalizacao": True,
        }
    )
    db.add(tenant)
    
    # Criar usuário admin
    admin_id = uuid4()
    # Gerar matrícula simples para admin
    matricula = f"ADM{str(admin_id)[:8].upper()}"
    
    admin = Usuario(
        id=admin_id,
        tenant_id=tenant_id,
        nome=request.admin_nome,
        email=request.admin_email,
        cpf="00000000000",  # CPF temporário - admin pode atualizar depois
        telefone=None,
        matricula=matricula,
        password_hash=hash_password(request.admin_senha),
        papel=UserRole.ADMIN_DP,
        status=UserStatus.ACTIVE,
        mfa_enabled=False,
    )
    db.add(admin)
    
    await db.commit()
    
    return RegisterTenantResponse(
        tenant_id=tenant_id,
        tenant_slug=slug,
        admin_id=admin_id,
        message="Empresa cadastrada com sucesso! Você já pode fazer login.",
    )


@router.get("/check-cnpj/{cnpj}")
async def check_cnpj_availability(
    cnpj: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Verificar se CNPJ está disponível."""
    # Limpar CNPJ
    cnpj_clean = ''.join(filter(str.isdigit, cnpj))
    
    result = await db.execute(
        select(Tenant.id, Tenant.nome).where(Tenant.cnpj == cnpj_clean)
    )
    row = result.one_or_none()
    
    return {
        "available": row is None,
        "empresa_nome": row.nome if row else None,
    }


@router.get("/check-slug/{slug}")
async def check_slug_availability(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Verificar se slug está disponível."""
    result = await db.execute(
        select(Tenant.id).where(Tenant.config["slug"].astext == slug)
    )
    
    return {"available": result.scalar_one_or_none() is None}


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
    response: Response,
):
    """
    Autenticar usuário.
    
    - Se MFA habilitado e código não fornecido, retorna requires_mfa=true
    - Se MFA habilitado e código fornecido, valida e retorna tokens
    """
    web = cookie_mode(http_request)
    if web:
        check_cookie_origin(http_request)
    response.headers["Cache-Control"] = "no-store"
    # Email is unique per tenant. Never pick one of multiple matching accounts.
    result = await db.execute(
        select(
            Usuario.id,
            Usuario.tenant_id,
            Usuario.nome,
            Usuario.email,
            Usuario.cpf,
            Usuario.telefone,
            Usuario.matricula,
            Usuario.papel,
            Usuario.status,
            Usuario.password_hash,
            Usuario.mfa_enabled,
            Usuario.mfa_secret,
            Usuario.foto_base_url,
            Usuario.equipe_id,
            Usuario.ultimo_login,
            Usuario.created_at,
            Usuario.updated_at,
        ).where(Usuario.email == request.email,
                *([Usuario.tenant_id == request.tenant_id] if request.tenant_id else []))
        .limit(2)
    )
    rows = result.all()
    row = rows[0] if len(rows) == 1 else None
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )
    
    # Extrair dados do row
    user_id = row.id
    tenant_id = row.tenant_id
    password_hash = row.password_hash
    user_status = row.status
    mfa_enabled = row.mfa_enabled
    mfa_secret = row.mfa_secret
    papel = row.papel
    
    # Verificar senha
    if not verify_password(request.password, password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )
    
    # Verificar status
    if user_status == UserStatus.SUSPENDED or user_status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário suspenso. Contate o administrador.",
        )
    
    if user_status == UserStatus.INACTIVE or user_status == "inactive":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo.",
        )
    
    # Verificar MFA
    if mfa_enabled:
        if not request.mfa_code:
            # Retorna flag para frontend solicitar código
            user_data = UsuarioRead(
                id=row.id,
                tenant_id=row.tenant_id,
                nome=row.nome,
                email=row.email,
                cpf=row.cpf,
                telefone=row.telefone,
                matricula=row.matricula,
                papel=papel,
                status=user_status,
                mfa_enabled=mfa_enabled,
                foto_base_url=row.foto_base_url,
                equipe_id=row.equipe_id,
                ultimo_login=row.ultimo_login,
                created_at=row.created_at or datetime.utcnow(),
                updated_at=row.updated_at or datetime.utcnow(),
            )
            return LoginResponse(
                access_token="",
                refresh_token="",
                expires_in=0,
                user=user_data,
                requires_mfa=True,
            )
        
        # Validar código MFA
        if not mfa_secret or not verify_totp(mfa_secret, request.mfa_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Código MFA inválido",
            )
    
    # Gerar tokens
    papel_value = papel.value if hasattr(papel, 'value') else papel
    access_token, refresh_token_str, expires = await issue_tokens(user_id, tenant_id, papel_value)
    if web:
        set_refresh_cookie(response, refresh_token_str, expires)

    # Atualizar último login
    await db.execute(
        update(Usuario)
        .where(Usuario.id == user_id)
        .values(ultimo_login=datetime.utcnow())
    )
    await db.commit()
    
    # Construir resposta do usuário com dados do row
    user_data = UsuarioRead(
        id=row.id,
        tenant_id=row.tenant_id,
        nome=row.nome,
        email=row.email,
        cpf=row.cpf,
        telefone=row.telefone,
        matricula=row.matricula,
        papel=papel,
        status=user_status,
        mfa_enabled=mfa_enabled,
        foto_base_url=row.foto_base_url,
        equipe_id=row.equipe_id,
        ultimo_login=row.ultimo_login,
        created_at=row.created_at or datetime.utcnow(),
        updated_at=row.updated_at or datetime.utcnow(),
    )
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=None if web else refresh_token_str,
        expires_in=settings.access_token_expire_minutes * 60,
        user=user_data,
        requires_mfa=False,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    http_request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: RefreshTokenRequest | None = None,
):
    web = cookie_mode(http_request)
    if web:
        check_cookie_origin(http_request)
        token = http_request.cookies.get(COOKIE_NAME)
    else:
        token = request.refresh_token if request else None
    if not token:
        raise unauthorized()
    payload = await validate_session(token, "refresh")
    result = await db.execute(select(Usuario).where(Usuario.id == UUID(payload["sub"])))
    usuario = result.scalar_one_or_none()
    if not usuario or usuario.status != UserStatus.ACTIVE:
        raise unauthorized()
    payload["refresh_digest"] = digest(token)
    papel = usuario.papel.value if hasattr(usuario.papel, "value") else usuario.papel
    access, refresh, expires = await issue_tokens(usuario.id, usuario.tenant_id, papel, payload)
    response.headers["Cache-Control"] = "no-store"
    if web:
        set_refresh_cookie(response, refresh, expires)
    return TokenResponse(access_token=access, refresh_token=None if web else refresh,
                         expires_in=settings.access_token_expire_minutes * 60)


@router.post("/logout", response_model=SuccessResponse)
async def logout(http_request: Request, response: Response):
    from app.core.redis import get_redis
    from redis.exceptions import RedisError

    web = cookie_mode(http_request)
    if web:
        check_cookie_origin(http_request)
    cookie = http_request.cookies.get(COOKIE_NAME) if web else None
    bearer = http_request.headers.get("Authorization", "")
    token = cookie or (bearer[7:] if bearer.lower().startswith("bearer ") else None)
    if token:
        try:
            payload = await validate_session(token, "refresh" if cookie else "access")
        except HTTPException as exc:
            if exc.status_code != 401:
                raise
        else:
            try:
                redis = await get_redis()
                await redis.revoke_user_session(payload["sub"], payload["sid"])
            except RedisError:
                raise HTTPException(503, "Serviço de autenticação indisponível") from None
    clear_refresh_cookie(response)
    return SuccessResponse(message="Logout realizado com sucesso")


@router.post("/password/change", response_model=SuccessResponse)
async def change_password(
    request: PasswordChangeRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Alterar senha do usuário autenticado."""
    
    # Buscar usuário
    result = await db.execute(
        select(Usuario).where(Usuario.id == current_user.id)
    )
    usuario = result.scalar_one_or_none()
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )
    
    # Verificar senha atual
    if not verify_password(request.current_password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta",
        )
    
    # Atualizar senha
    await db.execute(
        update(Usuario)
        .where(Usuario.id == current_user.id)
        .values(password_hash=hash_password(request.new_password))
    )
    await db.commit()
    
    from app.core.redis import get_redis
    redis = await get_redis()
    await redis.revoke_all_user_sessions(str(current_user.id))
    return SuccessResponse(message="Senha alterada com sucesso")


@router.post("/password/reset", response_model=SuccessResponse)
async def request_password_reset(
    request: PasswordResetRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Solicitar reset de senha.
    
    Envia email com link/token para reset.
    """
    from app.core.redis import get_redis
    from app.core.email import email_service
    import secrets
    
    # Buscar usuário
    result = await db.execute(
        select(Usuario).where(Usuario.email == request.email,
                              *([Usuario.tenant_id == request.tenant_id] if request.tenant_id else []))
        .limit(2)
    )
    users = result.scalars().all()
    usuario = users[0] if len(users) == 1 else None
    
    # Sempre retorna sucesso para não expor se email existe
    if usuario:
        # Gerar token de reset
        token = secrets.token_urlsafe(32)
        
        # Salvar no Redis (1 hora de validade)
        redis = await get_redis()
        await redis.store_password_reset_token(
            user_id=str(usuario.id),
            token=token,
            ttl_seconds=3600,
        )
        
        # Enviar email
        await email_service.send_password_reset(
            email=usuario.email,
            token=token,
            nome=usuario.nome,
        )
    
    return SuccessResponse(
        message="Se o email existir no sistema, um link de recuperação será enviado"
    )


@router.post("/password/reset/confirm", response_model=SuccessResponse)
async def confirm_password_reset(
    request: PasswordResetConfirm,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Confirmar reset de senha com token."""
    from app.core.redis import get_redis
    
    # Verificar token no Redis
    redis = await get_redis()
    user_id = await redis.get_password_reset_user(request.token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido ou expirado",
        )
    
    # Atualizar senha
    await db.execute(
        update(Usuario)
        .where(Usuario.id == UUID(user_id))
        .values(password_hash=hash_password(request.new_password))
    )
    await db.commit()
    
    # Invalidar token usado
    await redis.invalidate_password_reset_token(request.token)
    
    # Revogar todas as sessões do usuário
    await redis.revoke_all_user_sessions(user_id)
    
    return SuccessResponse(message="Senha redefinida com sucesso")


# ============================================================================
# MFA
# ============================================================================

@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Configurar MFA para o usuário.
    
    Retorna secret e QR code para configurar no app autenticador.
    """
    result = await db.execute(select(Usuario).where(Usuario.id == current_user.id))
    usuario = result.scalar_one_or_none()
    if not usuario or usuario.mfa_enabled:
        raise HTTPException(409, "Desative o MFA atual antes de configurar outro")
    # Gerar novo secret
    secret = generate_totp_secret()
    
    # Gerar URI para QR Code
    qr_uri = get_totp_uri(secret, current_user.email)
    
    # Gerar códigos de backup
    backup_codes = []  # Recovery codes are not implemented; do not issue unusable codes.
    
    # Salvar secret (ainda não habilitado)
    await db.execute(
        update(Usuario)
        .where(Usuario.id == current_user.id)
        .values(
            mfa_secret=secret,
            # backup_codes seriam salvos em tabela separada ou campo JSONB
        )
    )
    await db.commit()
    
    return MFASetupResponse(
        secret=secret,
        qr_code_uri=qr_uri,
        backup_codes=backup_codes,
    )


@router.post("/mfa/verify", response_model=SuccessResponse)
async def verify_mfa_setup(
    request: MFAVerifyRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Verificar e ativar MFA.
    
    Usuário deve fornecer código do app autenticador para confirmar setup.
    """
    # Buscar usuário com secret
    result = await db.execute(
        select(Usuario).where(Usuario.id == current_user.id)
    )
    usuario = result.scalar_one_or_none()
    
    if not usuario or not usuario.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA não configurado. Execute /mfa/setup primeiro.",
        )
    
    # Verificar código
    if not verify_totp(usuario.mfa_secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código inválido",
        )
    
    # Ativar MFA
    await db.execute(
        update(Usuario)
        .where(Usuario.id == current_user.id)
        .values(mfa_enabled=True)
    )
    await db.commit()
    
    return SuccessResponse(message="MFA ativado com sucesso")


@router.post("/mfa/disable", response_model=SuccessResponse)
async def disable_mfa(
    request: MFADisableRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Desativar MFA do usuário."""
    
    # Buscar usuário
    result = await db.execute(
        select(Usuario).where(Usuario.id == current_user.id)
    )
    usuario = result.scalar_one_or_none()
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )
    
    # Verificar senha
    if not verify_password(request.password, usuario.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha incorreta",
        )
    
    # Verificar código MFA
    if usuario.mfa_secret and not verify_totp(usuario.mfa_secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código MFA inválido",
        )
    
    # Desativar MFA
    await db.execute(
        update(Usuario)
        .where(Usuario.id == current_user.id)
        .values(mfa_enabled=False, mfa_secret=None)
    )
    await db.commit()
    
    return SuccessResponse(message="MFA desativado com sucesso")


@router.get("/me", response_model=UsuarioRead)
async def get_current_user_info(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Obter informações do usuário autenticado."""
    
    result = await db.execute(
        select(Usuario).where(Usuario.id == current_user.id)
    )
    usuario = result.scalar_one_or_none()
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )
    
    return UsuarioRead.model_validate(usuario)
