"""Router de autenticação."""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_db
from app.core.config import settings
from app.core.observability import record_auth_attempt
from app.core.rate_limit import auth_rate_limit
from app.core.redis import RedisClient, get_redis
from app.core.security import (
    encrypt_totp_secret,
    generate_totp_secret,
    get_totp_uri,
    hash_password,
    verify_password,
)
from app.core.sessions import (
    COOKIE_NAME,
    check_cookie_origin,
    clear_refresh_cookie,
    cookie_mode,
    digest,
    issue_tokens,
    set_refresh_cookie,
    unauthorized,
    validate_session,
)
from app.models import MFABackupCode, Tenant, UserRole, UserStatus, Usuario
from app.schemas import (
    LoginRequest,
    LoginResponse,
    MFADisableRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetVerifyRequest,

    RefreshTokenRequest,
    RegisterTenantRequest,
    RegisterTenantResponse,
    SuccessResponse,
    TokenResponse,
    UsuarioRead,
    UsuarioSelfUpdate,
)
from app.services.mfa import generate_backup_codes, replace_backup_codes, verify_mfa_code
from app.services.password_reset import execute_password_reset_request, PasswordResetEmailError


router = APIRouter(prefix="/auth", tags=["Autenticação"], dependencies=[Depends(auth_rate_limit)])
logger = logging.getLogger(__name__)


def usuario_to_read(usuario: Usuario) -> UsuarioRead:
    """Build a response schema from already-loaded user attributes."""
    return UsuarioRead.model_validate({
        "id": usuario.id,
        "tenant_id": usuario.tenant_id,
        "nome": usuario.nome,
        "email": usuario.email,
        "cpf": usuario.cpf,
        "telefone": usuario.telefone,
        "matricula": usuario.matricula,
        "papel": usuario.papel,
        "status": usuario.status,
        "mfa_enabled": usuario.mfa_enabled,
        "foto_base_url": usuario.foto_base_url,
        "equipe_id": usuario.equipe_id,
        "ultimo_login": usuario.ultimo_login,
        "created_at": usuario.created_at,
        "updated_at": usuario.updated_at,
    })


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
        razao_social=request.empresa_nome,
        cnpj=request.empresa_cnpj,
        email=request.empresa_email,
        telefone=request.empresa_telefone,
        ativo=True,
        config={
            "slug": slug,
            "plano": request.plano,
            "ponto": {
                "jornada_diaria": 8,
                "jornada_semanal": 44,
                "tolerancia_minutos": 10,
                "intervalo_minimo": 60,
                "hora_extra_automatica": True,
                "banco_horas_ativo": False,
                "banco_horas_limite": 40,
                "exigir_foto": True,
                "exigir_geolocalizacao": True,
                "permitir_offline": True,
                "notificar_atraso": True,
                "notificar_hora_extra": True,
            },
            "notificacoes": {
                "email_ativo": True,
                "push_ativo": True,
                "notificar_marcacao": True,
                "notificar_aprovacao": True,
                "notificar_documento": True,
                "notificar_alerta": True,
                "horario_lembrete_entrada": None,
                "horario_lembrete_saida": None,
            },
            "seguranca": {
                "mfa_obrigatorio": False,
                "sessao_unica": False,
                "tempo_sessao": 480,
                "tentativas_login": 5,
                "bloquear_dispositivo": False,
                "ips_permitidos": None,
            },
            "integracoes": {
                "webhook_url": None,
                "webhook_secret": None,
                "api_folha_ativa": False,
                "api_folha_url": None,
                "api_folha_token": None,
            },
        },
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
        cpf=None,  # CPF nulo - admin pode atualizar depois
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
        select(Usuario)
        .where(Usuario.email == request.email,
               *([Usuario.tenant_id == request.tenant_id] if request.tenant_id else []))
        .limit(2)
    )
    rows = result.scalars().all()
    usuario = rows[0] if len(rows) == 1 else None

    if not usuario:
        record_auth_attempt("invalid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )

    # Extrair dados do row
    user_id = usuario.id
    tenant_id = usuario.tenant_id
    user_status = usuario.status
    mfa_enabled = usuario.mfa_enabled
    papel = usuario.papel

    # Verificar senha
    if not verify_password(request.password, usuario.password_hash):
        record_auth_attempt("invalid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )

    # Verificar status
    if user_status == UserStatus.PENDING or user_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cadastro pendente de ativação.",
        )

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
            user_data = usuario_to_read(usuario)
            return LoginResponse(
                access_token="",
                refresh_token="",
                expires_in=0,
                user=user_data,
                requires_mfa=True,
            )

        # Validar código MFA
        if not await verify_mfa_code(db, usuario, request.mfa_code, http_request):
            record_auth_attempt("invalid")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Código MFA inválido",
            )

    # Gerar tokens
    papel_value = papel.value if hasattr(papel, 'value') else papel
    access_token, refresh_token_str, expires = await issue_tokens(user_id, tenant_id, papel_value)
    if web:
        set_refresh_cookie(response, refresh_token_str, expires)

    # Atualizar último login no próprio objeto sem expirar atributos necessários à resposta
    usuario.ultimo_login = datetime.utcnow()
    user_data = usuario_to_read(usuario)
    await db.commit()
    record_auth_attempt("success")

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
    from redis.exceptions import RedisError

    from app.core.redis import get_redis

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
    redis: Annotated[RedisClient, Depends(get_redis)],
):
    """
    Solicitar reset de senha.

    Envia email com link/token para reset.
    Sempre retorna resposta genérica para evitar enumeração de usuários.
    """
    # Buscar usuário
    result = await db.execute(
        select(Usuario).where(Usuario.email == request.email,
                              *([Usuario.tenant_id == request.tenant_id] if request.tenant_id else []))
        .limit(2)
    )
    users = result.scalars().all()
    usuario = users[0] if len(users) == 1 else None

    if usuario:
        try:
            await execute_password_reset_request(
                user_id=str(usuario.id),
                email=usuario.email,
                nome=usuario.nome,
                redis=redis,
            )
        except PasswordResetEmailError:
            # Em erro no envio de e-mail no fluxo público, o token é invalidado
            # pelo helper e mantemos a resposta genérica por proteção contra enumeração.
            pass

    return SuccessResponse(
        message="Se o email existir no sistema, um link de recuperação será enviado"
    )


@router.post("/password/reset/verify", response_model=SuccessResponse)
async def verify_password_reset_token(
    request: PasswordResetVerifyRequest,
    redis: Annotated[RedisClient, Depends(get_redis)],
):
    """Verificar se token de reset de senha é válido sem consumi-lo (operação não destrutiva)."""
    user_id = await redis.peek_password_reset_user(request.token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido ou expirado",
        )

    return SuccessResponse(message="Token válido")


@router.post("/password/reset/confirm", response_model=SuccessResponse)
async def confirm_password_reset(
    request: PasswordResetConfirm,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[RedisClient, Depends(get_redis)],
):
    """Confirmar reset de senha com reserva atômica de token (USR-43)."""
    # 1. Reservar token no Redis atômica e exclusivamente
    user_id, lock_id = await redis.reserve_password_reset_token(request.token)

    if not user_id or not lock_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido, expirado ou em processamento",
        )

    # 2. Atualizar a senha no banco de dados com tratamento seguro de erros
    try:
        await db.execute(
            update(Usuario)
            .where(Usuario.id == UUID(user_id))
            .values(password_hash=hash_password(request.new_password))
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        # Se a atualização do banco falhou, libera a trava sem consumir o token no Redis
        await redis.release_password_reset_lock(request.token, lock_id)
        logger.exception("Falha no banco de dados durante redefinição de senha para usuario %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar a senha no banco de dados. Tente novamente.",
        ) from exc

    # 3. Consumir o token no Redis e revogar sessões ativas após o commit no banco
    try:
        await redis.finalize_password_reset(request.token, lock_id, user_id)
    except Exception as redis_exc:
        logger.error(
            "Falha crítica no Redis ao finalizar reset ou revogar sessões para usuário %s: %s",
            user_id,
            redis_exc,
            exc_info=True,
        )
        try:
            await redis.consume_password_reset_user(request.token)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Senha redefinida no banco, porém ocorreu falha ao revogar sessões no Redis.",
        ) from redis_exc

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
    backup_codes = generate_backup_codes()

    # Salvar secret (ainda não habilitado)
    await db.execute(
        update(Usuario)
        .where(Usuario.id == current_user.id)
        .values(
            mfa_secret=encrypt_totp_secret(secret),
            mfa_last_totp_step=None,
        )
    )
    await replace_backup_codes(db, current_user.id, backup_codes)
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
    http_request: Request,
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
    if not await verify_mfa_code(db, usuario, request.code, http_request, allow_backup=False):
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
    http_request: Request,
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
    if usuario.mfa_secret and not await verify_mfa_code(db, usuario, request.code, http_request):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código MFA inválido",
        )

    # Desativar MFA
    await db.execute(
        update(Usuario)
        .where(Usuario.id == current_user.id)
        .values(mfa_enabled=False, mfa_secret=None, mfa_last_totp_step=None)
    )
    await db.execute(delete(MFABackupCode).where(MFABackupCode.usuario_id == current_user.id))
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


@router.patch("/me", response_model=UsuarioRead)
async def update_current_user_info(
    data: UsuarioSelfUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualizar informações do próprio usuário (auto-serviço: apenas nome e telefone)."""
    result = await db.execute(
        select(Usuario).where(Usuario.id == current_user.id)
    )
    usuario = result.scalar_one_or_none()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )

    update_data = data.model_dump(exclude_unset=True)
    if update_data:
        await db.execute(
            update(Usuario)
            .where(Usuario.id == current_user.id)
            .values(**update_data)
        )
        await db.commit()
        await db.refresh(usuario)

    return UsuarioRead.model_validate(usuario)

