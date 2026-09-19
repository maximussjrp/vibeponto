"""Servico de armazenamento de arquivos (MinIO/S3)."""

import hashlib
from datetime import datetime
from pathlib import PurePath
from uuid import UUID, uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.observability import storage_timer

ALLOWED_UPLOADS = {
    "application/pdf": {".pdf": b"%PDF"},
    "image/jpeg": {".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff"},
    "image/png": {".png": b"\x89PNG\r\n\x1a\n"},
}


class StorageService:
    """
    Servico de armazenamento compativel com S3.

    Usa MinIO localmente e pode ser substituido por S3 em producao.
    """

    def __init__(self):
        self.endpoint_url = settings.storage_endpoint
        self.access_key = settings.storage_access_key
        self.secret_key = settings.storage_secret_key
        self.bucket = settings.storage_bucket
        self.region = settings.storage_region

        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=Config(signature_version="s3v4"),
        )

        self._bucket_checked = False

    def _ensure_bucket(self):
        """Cria o bucket se nao existir."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)

    def _generate_key(
        self,
        tenant_id: UUID,
        folder: str,
        filename: str,
        add_uuid: bool = True,
    ) -> str:
        """Gera chave unica para o arquivo."""
        if add_uuid:
            safe_name = PurePath(filename).name
            ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
            unique_name = f"{uuid4()}.{ext}" if ext else str(uuid4())
            return f"{tenant_id}/{folder}/{unique_name}"
        return f"{tenant_id}/{folder}/{PurePath(filename).name}"

    async def _ensure_bucket_async(self):
        if not self._bucket_checked:
            await run_in_threadpool(self._ensure_bucket)
            self._bucket_checked = True

    def _validate_upload(self, filename: str, content: bytes, content_type: str, folder: str) -> str:
        safe_name = PurePath(filename).name
        ext = f".{safe_name.rsplit('.', 1)[-1].lower()}" if "." in safe_name else ""
        max_size = settings.upload_image_max_size_bytes if folder == "pontos" else settings.upload_max_size_bytes
        if len(content) > max_size:
            raise HTTPException(status_code=413, detail="Arquivo excede o tamanho maximo permitido")
        signatures = ALLOWED_UPLOADS.get(content_type)
        if not signatures or ext not in signatures:
            raise HTTPException(status_code=400, detail="Tipo de arquivo nao permitido")
        if not content.startswith(signatures[ext]):
            raise HTTPException(status_code=400, detail="Conteudo do arquivo nao corresponde ao tipo declarado")
        return safe_name

    def _validate_declared_type(self, filename: str, content_type: str) -> str:
        safe_name = PurePath(filename).name
        ext = f".{safe_name.rsplit('.', 1)[-1].lower()}" if "." in safe_name else ""
        signatures = ALLOWED_UPLOADS.get(content_type)
        if not signatures or ext not in signatures:
            raise HTTPException(status_code=400, detail="Tipo de arquivo nao permitido")
        return safe_name

    async def upload_file(
        self,
        tenant_id: UUID,
        folder: str,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> dict:
        """
        Upload de arquivo.

        Retorna dict com url, key, hash e tamanho.
        """
        with storage_timer("upload"):
            filename = self._validate_upload(filename, content, content_type, folder)
            key = self._generate_key(tenant_id, folder, filename)

            file_hash = hashlib.sha256(content).hexdigest()

            await self._ensure_bucket_async()
            await run_in_threadpool(
                self.client.put_object,
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
                Metadata={
                    "hash": file_hash,
                    "original_filename": filename,
                    "uploaded_at": datetime.utcnow().isoformat(),
                },
            )

            url = key

            return {
                "key": key,
                "url": url,
                "hash": file_hash,
                "size": len(content),
                "content_type": content_type,
            }

    async def upload_base64(
        self,
        tenant_id: UUID,
        folder: str,
        filename: str,
        base64_content: str,
        content_type: str = "application/octet-stream",
    ) -> dict:
        """Upload de arquivo em base64."""
        import base64

        if "," in base64_content:
            base64_content = base64_content.split(",", 1)[1]

        content = base64.b64decode(base64_content)
        return await self.upload_file(tenant_id, folder, filename, content, content_type)

    async def download_file(self, key: str) -> bytes:
        """Download de arquivo."""
        with storage_timer("download"):
            response = await run_in_threadpool(self.client.get_object, Bucket=self.bucket, Key=key)
            return await run_in_threadpool(response["Body"].read)

    async def delete_file(self, key: str) -> bool:
        """Deletar arquivo."""
        with storage_timer("delete") as timer:
            try:
                await run_in_threadpool(self.client.delete_object, Bucket=self.bucket, Key=key)
                return True
            except ClientError:
                timer.result = "error"
                return False

    async def file_exists(self, key: str) -> bool:
        """Verifica se arquivo existe."""
        try:
            await run_in_threadpool(self.client.head_object, Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        download_filename: str | None = None,
    ) -> str:
        """Gera URL pre-assinada com opcao de download."""
        with storage_timer("presign"):
            params = {"Bucket": self.bucket, "Key": key}

            if download_filename:
                params["ResponseContentDisposition"] = f'attachment; filename="{download_filename}"'

            return await run_in_threadpool(
                self.client.generate_presigned_url,
                "get_object",
                Params=params,
                ExpiresIn=expires_in,
            )

    async def get_presigned_upload_url(
        self,
        tenant_id: UUID,
        folder: str,
        filename: str,
        content_type: str = "application/octet-stream",
        expires_in: int = 3600,
    ) -> dict:
        """
        Gera URL pre-assinada para upload direto do cliente.

        Util para uploads grandes sem passar pelo backend.
        """
        with storage_timer("presign"):
            filename = self._validate_declared_type(filename, content_type)
            key = self._generate_key(tenant_id, folder, filename)
            url = await run_in_threadpool(
                self.client.generate_presigned_url,
                "put_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )

            return {
                "upload_url": url,
                "key": key,
                "expires_in": expires_in,
            }


_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """Obtem instancia singleton do servico de storage."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


# Initialization is lazy: importing API/tasks must not contact object storage.
