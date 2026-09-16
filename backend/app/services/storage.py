"""Serviço de armazenamento de arquivos (MinIO/S3)."""

import hashlib
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings


class StorageService:
    """
    Serviço de armazenamento compatível com S3.
    
    Usa MinIO localmente e pode ser substituído por S3 em produção.
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
        
        # Garantir que o bucket existe
        self._ensure_bucket()
    
    def _ensure_bucket(self):
        """Cria o bucket se não existir."""
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
        """Gera chave única para o arquivo."""
        if add_uuid:
            ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
            unique_name = f"{uuid4()}.{ext}" if ext else str(uuid4())
            return f"{tenant_id}/{folder}/{unique_name}"
        return f"{tenant_id}/{folder}/{filename}"
    
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
        key = self._generate_key(tenant_id, folder, filename)
        
        # Calcular hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Upload
        self.client.put_object(
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
        
        # Gerar URL (pode ser pré-assinada ou pública)
        url = self._get_url(key)
        
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
        
        # Remover prefixo data:...;base64, se presente
        if "," in base64_content:
            base64_content = base64_content.split(",", 1)[1]
        
        content = base64.b64decode(base64_content)
        return await self.upload_file(tenant_id, folder, filename, content, content_type)
    
    async def download_file(self, key: str) -> bytes:
        """Download de arquivo."""
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()
    
    async def delete_file(self, key: str) -> bool:
        """Deletar arquivo."""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False
    
    async def file_exists(self, key: str) -> bool:
        """Verifica se arquivo existe."""
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False
    
    def _get_url(self, key: str, expires_in: int = 3600) -> str:
        """Gera URL pré-assinada para acesso ao arquivo."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )
    
    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        download_filename: Optional[str] = None,
    ) -> str:
        """Gera URL pré-assinada com opção de download."""
        params = {"Bucket": self.bucket, "Key": key}
        
        if download_filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{download_filename}"'
        
        return self.client.generate_presigned_url(
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
        Gera URL pré-assinada para upload direto do cliente.
        
        Útil para uploads grandes sem passar pelo backend.
        """
        key = self._generate_key(tenant_id, folder, filename)
        
        url = self.client.generate_presigned_url(
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


# Singleton
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Obtém instância singleton do serviço de storage."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


# Também exporta como variável direta para conveniência
# Initialization is lazy: importing API/tasks must not contact object storage.
