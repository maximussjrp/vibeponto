"""Script de população de dados sintéticos para o ambiente de Staging (STG.1-PLAN-01, OPS-04)."""

import asyncio
import os
import sys
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.models.models import Tenant, UserRole, UserStatus, Usuario
from tests.destructive_guard import UnsafeTestEnvironment, verify_disposable_environment


async def seed_staging() -> None:
    db_url = os.getenv("STAGING_DATABASE_URL", "").strip()
    redis_url = os.getenv("STAGING_REDIS_URL", "").strip()

    if not db_url or not redis_url:
        raise RuntimeError("Configuração ausente: STAGING_DATABASE_URL e STAGING_REDIS_URL são obrigatórias.")

    # 1. Guarda OPS-04: comprova positivamente o ambiente descartável no PostgreSQL e Redis
    try:
        env_id = await verify_disposable_environment(db_url, redis_url, os.environ)
    except UnsafeTestEnvironment as err:
        raise RuntimeError(f"OPS-04: Impossível realizar seed. {err}") from err

    # 2. Exigir credenciais sintéticas via variáveis de ambiente
    admin_email = os.getenv("STAGING_ADMIN_EMAIL", "").strip()
    admin_password = os.getenv("STAGING_ADMIN_PASSWORD", "").strip()
    user_email = os.getenv("STAGING_USER_EMAIL", "").strip()
    user_password = os.getenv("STAGING_USER_PASSWORD", "").strip()

    if not admin_email or not admin_password or not user_email or not user_password:
        raise RuntimeError(
            "Configuração ausente: STAGING_ADMIN_EMAIL, STAGING_ADMIN_PASSWORD, "
            "STAGING_USER_EMAIL e STAGING_USER_PASSWORD são obrigatórias."
        )

    engine = create_async_engine(db_url, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        # 3. Idempotência: verificar/incluir Tenant de Staging
        tenant_stmt = select(Tenant).where(Tenant.cnpj == "99887766000155")
        tenant = (await session.execute(tenant_stmt)).scalar_one_or_none()

        if not tenant:
            tenant_id = uuid4()
            tenant = Tenant(
                id=tenant_id,
                nome="Empresa Staging E2E",
                razao_social="Empresa Staging E2E LTDA",
                cnpj="99887766000155",
                email="contato@staging.vibeponto.com",
                ativo=True,
                config={
                    "slug": "empresa-staging-e2e",
                    "plano": "enterprise",
                },
            )
            session.add(tenant)
            await session.flush()
        else:
            tenant_id = tenant.id

        # 4. Idempotência: verificar/incluir Usuário Admin Sintético
        admin_stmt = select(Usuario).where(Usuario.email == admin_email)
        admin_user = (await session.execute(admin_stmt)).scalar_one_or_none()

        if not admin_user:
            admin_user = Usuario(
                id=uuid4(),
                tenant_id=tenant_id,
                nome="Admin Sintético Staging",
                email=admin_email,
                cpf="52998224725",
                matricula="STG-ADM-001",
                password_hash=hash_password(admin_password),
                papel=UserRole.ADMIN_DP,
                status=UserStatus.ACTIVE,
            )
            session.add(admin_user)
        else:
            admin_user.password_hash = hash_password(admin_password)

        # 5. Idempotência: verificar/incluir Usuário Colaborador Sintético
        user_stmt = select(Usuario).where(Usuario.email == user_email)
        colab_user = (await session.execute(user_stmt)).scalar_one_or_none()

        if not colab_user:
            colab_user = Usuario(
                id=uuid4(),
                tenant_id=tenant_id,
                nome="Colaborador Sintético Staging",
                email=user_email,
                cpf="98765432100",
                matricula="STG-COL-001",
                password_hash=hash_password(user_password),
                papel=UserRole.COLABORADOR,
                status=UserStatus.ACTIVE,
            )
            session.add(colab_user)
        else:
            colab_user.password_hash = hash_password(user_password)

        await session.commit()
        print(f"Dados sintéticos de staging sincronizados com sucesso (Ambiente: {env_id})")

    await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(seed_staging())
    except Exception as exc:
        print(f"Erro no seed de staging: {exc}", file=sys.stderr)
        sys.exit(1)
