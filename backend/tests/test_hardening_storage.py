"""Storage validation and async-wrapper regressions."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.api.routes.documentos as documentos_routes
from app.api.deps import CurrentUser, TenantContext
from app.core.database import Base
from app.core.security import hash_password
from app.models import Documento, DocumentoTipo, Tenant, UserRole, UserStatus, Usuario
from app.services.storage import StorageService

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:55432/hardening_r2"
pytestmark = pytest.mark.asyncio(loop_scope="session")


class DummyS3:
    def __init__(self):
        self.objects = {}

    def head_bucket(self, **kwargs):
        return {}

    def put_object(self, **kwargs):
        self.objects[kwargs["Key"]] = kwargs
        return {}

    def generate_presigned_url(self, operation, **kwargs):
        params = kwargs["Params"]
        expires_in = kwargs["ExpiresIn"]
        return f"https://storage.local/{operation}/{params['Key']}?exp={expires_in}"


@pytest.fixture
def storage(monkeypatch):
    dummy = DummyS3()
    monkeypatch.setattr("app.services.storage.boto3.client", lambda *args, **kwargs: dummy)
    service = StorageService()
    service.client = dummy
    return service


async def test_presigned_urls_use_public_storage_endpoint(monkeypatch):
    clients = {}

    class EndpointAwareS3(DummyS3):
        def __init__(self, endpoint_url):
            super().__init__()
            self.endpoint_url = endpoint_url

        def generate_presigned_url(self, operation, **kwargs):
            key = kwargs["Params"]["Key"]
            return f"{self.endpoint_url}/{key}"

    def create_client(*args, **kwargs):
        client = EndpointAwareS3(kwargs["endpoint_url"])
        clients[kwargs["endpoint_url"]] = client
        return client

    monkeypatch.setattr("app.services.storage.settings.storage_endpoint", "http://minio:9000")
    monkeypatch.setattr(
        "app.services.storage.settings.storage_public_endpoint",
        "https://storage.vibeponto.com.br",
    )
    monkeypatch.setattr("app.services.storage.boto3.client", create_client)

    service = StorageService()
    url = await service.get_presigned_url("tenant/documentos/contrato.pdf")

    assert service.client is clients["http://minio:9000"]
    assert service.public_client is clients["https://storage.vibeponto.com.br"]
    assert url == "https://storage.vibeponto.com.br/tenant/documentos/contrato.pdf"


@pytest.fixture
async def session_factory():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


async def test_upload_validates_type_size_and_server_key(storage, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.upload_max_size_bytes", 10)

    result = await storage.upload_file(
        uuid4(),
        "documentos",
        "../contrato.pdf",
        b"%PDF-ok",
        "application/pdf",
    )
    assert "/documentos/" in result["key"]
    assert result["key"].endswith(".pdf")
    assert result["url"] == result["key"]

    with pytest.raises(HTTPException) as too_large:
        await storage.upload_file(uuid4(), "documentos", "big.pdf", b"%PDF-too-large", "application/pdf")
    assert too_large.value.status_code == 413

    with pytest.raises(HTTPException) as wrong_ext:
        await storage.upload_file(uuid4(), "documentos", "bad.exe", b"%PDF-ok", "application/pdf")
    assert wrong_ext.value.status_code == 400

    with pytest.raises(HTTPException) as wrong_magic:
        await storage.upload_file(uuid4(), "documentos", "bad.pdf", b"not-pdf", "application/pdf")
    assert wrong_magic.value.status_code == 400


async def test_presigned_upload_uses_server_generated_key(storage):
    result = await storage.get_presigned_upload_url(
        uuid4(),
        "documentos",
        "../../holerite.pdf",
        "application/pdf",
        expires_in=300,
    )
    assert "/documentos/" in result["key"]
    assert ".." not in result["key"]
    assert result["expires_in"] == 300


async def test_document_download_presigned_url_is_tenant_scoped(session_factory, monkeypatch):
    owner_tenant_id = uuid4()
    other_tenant_id = uuid4()
    owner_user_id = uuid4()
    other_user_id = uuid4()
    documento_id = uuid4()

    async with session_factory() as session:
        session.add_all(
            [
                Tenant(id=owner_tenant_id, nome="Owner", cnpj=str(owner_tenant_id.int)[:14], email="owner@example.com"),
                Tenant(id=other_tenant_id, nome="Other", cnpj=str(other_tenant_id.int)[:14], email="other@example.com"),
                Usuario(
                    id=owner_user_id,
                    tenant_id=owner_tenant_id,
                    nome="Owner User",
                    email="owner-user@example.com",
                    cpf=str(owner_user_id.int)[:11],
                    matricula="owner001",
                    password_hash=hash_password("Password123!"),
                    papel=UserRole.COLABORADOR,
                    status=UserStatus.ACTIVE,
                ),
                Usuario(
                    id=other_user_id,
                    tenant_id=other_tenant_id,
                    nome="Other User",
                    email="other-user@example.com",
                    cpf=str(other_user_id.int)[:11],
                    matricula="other001",
                    password_hash=hash_password("Password123!"),
                    papel=UserRole.GESTOR,
                    status=UserStatus.ACTIVE,
                ),
                Documento(
                    id=documento_id,
                    tenant_id=owner_tenant_id,
                    usuario_id=owner_user_id,
                    tipo=DocumentoTipo.CONTRATO,
                    titulo="Contrato",
                    arquivo_url=f"{owner_tenant_id}/documentos/contrato.pdf",
                    arquivo_nome="contrato.pdf",
                    arquivo_tamanho=7,
                    arquivo_hash="a" * 64,
                    arquivo_mime="application/pdf",
                ),
            ]
        )
        await session.commit()

        called = False

        class ForbiddenStorage:
            async def get_presigned_url(self, *args, **kwargs):
                nonlocal called
                called = True
                return "should-not-be-called"

        monkeypatch.setattr(documentos_routes, "get_storage_service", lambda: ForbiddenStorage())
        current_user = CurrentUser(
            id=other_user_id,
            tenant_id=other_tenant_id,
            email="other-user@example.com",
            nome="Other User",
            papel=UserRole.GESTOR,
            status=UserStatus.ACTIVE,
        )

        with pytest.raises(HTTPException) as exc:
            await documentos_routes.download_documento(
                documento_id=documento_id,
                current_user=current_user,
                tenant=TenantContext(other_tenant_id),
                db=session,
            )

    assert exc.value.status_code == 404
    assert called is False
