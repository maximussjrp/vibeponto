"""Script de população de dados sintéticos para o ambiente de Staging (E2E-02, E2E-05)."""

import asyncio
import os
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.security import hash_password
from app.models.models import Tenant, UserRole, UserStatus, Usuario

STAGING_DATABASE_URL = os.getenv(
    "STAGING_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:54399/test_vibeponto_staging")
)


STAGING_ADMIN_EMAIL = os.getenv("STAGING_ADMIN_EMAIL", "staging_admin_e2e@staging.vibeponto.com")
STAGING_ADMIN_PASSWORD = os.getenv("STAGING_ADMIN_PASSWORD", "StagingAdminPassword123!")

STAGING_USER_EMAIL = os.getenv("STAGING_USER_EMAIL", "staging_user_e2e@staging.vibeponto.com")
STAGING_USER_PASSWORD = os.getenv("STAGING_USER_PASSWORD", "StagingUserPassword123!")


async def create_db_if_not_exists(url: str):
    from sqlalchemy.engine.url import make_url
    parsed = make_url(url)
    target_db = parsed.database
    base_url = f"{parsed.drivername}://{parsed.username}:{parsed.password}@{parsed.host}:{parsed.port}/postgres"
    
    engine = create_async_engine(base_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        res = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{target_db}'"))
        if not res.scalar():
            await conn.execute(text(f'CREATE DATABASE "{target_db}"'))
            print(f"Banco de dados '{target_db}' criado com sucesso.")
    await engine.dispose()


async def seed_staging():
    await create_db_if_not_exists(STAGING_DATABASE_URL)
    engine = create_async_engine(STAGING_DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as session:
        # 1. Tenant de Staging
        tenant_id = uuid4()
        tenant = Tenant(
            id=tenant_id,
            nome="Empresa Staging E2E",
            razao_social="Empresa Staging E2E LTDA",
            cnpj="99887766000155",
            email="contato@staging.vibeponto.local",
            ativo=True,
            config={
                "slug": "empresa-staging-e2e",
                "plano": "enterprise",
            }
        )
        session.add(tenant)

        # 2. Usuário Admin Sintético
        admin_user = Usuario(
            id=uuid4(),
            tenant_id=tenant_id,
            nome="Admin Sintético Staging",
            email=STAGING_ADMIN_EMAIL,
            cpf="52998224725",
            matricula="STG-ADM-001",
            password_hash=hash_password(STAGING_ADMIN_PASSWORD),
            papel=UserRole.ADMIN_DP,
            status=UserStatus.ACTIVE,
        )
        session.add(admin_user)

        # 3. Usuário Colaborador Sintético
        colab_user = Usuario(
            id=uuid4(),
            tenant_id=tenant_id,
            nome="Colaborador Sintético Staging",
            email=STAGING_USER_EMAIL,
            cpf="98765432100",
            matricula="STG-COL-001",
            password_hash=hash_password(STAGING_USER_PASSWORD),
            papel=UserRole.COLABORADOR,
            status=UserStatus.ACTIVE,
        )
        session.add(colab_user)

        await session.commit()
        print(f"Dados sintéticos de staging criados com sucesso:")
        print(f"  Admin: {STAGING_ADMIN_EMAIL}")
        print(f"  User:  {STAGING_USER_EMAIL}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_staging())
