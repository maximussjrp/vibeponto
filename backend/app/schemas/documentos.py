"""Schemas de documentos e assinaturas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from app.models import AssinaturaMetodo, AssinaturaStatus, DocumentoTipo
from app.schemas.base import BaseSchema, TimestampSchema


# ============================================================================
# DOCUMENTO
# ============================================================================

class DocumentoBase(BaseSchema):
    """Schema base de documento."""
    
    tipo: DocumentoTipo
    titulo: str = Field(..., min_length=2, max_length=255)
    descricao: Optional[str] = None


class DocumentoCreate(DocumentoBase):
    """Schema para criar documento."""
    
    usuario_id: UUID
    periodo_referencia: Optional[str] = None  # "2026-01"
    requer_assinatura: bool = True
    metadata: Optional[dict] = None


class DocumentoUpload(BaseSchema):
    """Schema para upload de documento."""
    
    arquivo_base64: str
    arquivo_nome: str = Field(..., min_length=1, max_length=255)
    arquivo_mime: str = Field(..., pattern=r"^[\w\-]+/[\w\-\.]+$")


class DocumentoUpdate(BaseSchema):
    """Schema para atualizar documento."""
    
    titulo: Optional[str] = Field(None, min_length=2, max_length=255)
    descricao: Optional[str] = None
    periodo_referencia: Optional[str] = None
    metadata: Optional[dict] = None


class DocumentoRead(DocumentoBase, TimestampSchema):
    """Schema de leitura de documento."""
    
    id: UUID
    tenant_id: UUID
    usuario_id: UUID
    
    periodo_referencia: Optional[str] = None
    
    arquivo_url: str
    arquivo_nome: str
    arquivo_tamanho: int
    arquivo_hash: str
    arquivo_mime: str
    
    requer_assinatura: bool
    assinatura_status: AssinaturaStatus
    
    metadata: Optional[dict] = None


class DocumentoWithAssinaturas(DocumentoRead):
    """Schema de documento com assinaturas."""
    
    assinaturas: list["AssinaturaRead"] = []


# ============================================================================
# ASSINATURA
# ============================================================================

class AssinaturaRequest(BaseSchema):
    """Request para assinar documento."""
    
    metodo: AssinaturaMetodo = AssinaturaMetodo.ESIGN
    
    # Para ICP-Brasil
    certificado_data: Optional[str] = None
    
    # Trilha de auditoria
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    geoloc: Optional[dict] = None


class AssinaturaRead(TimestampSchema):
    """Schema de leitura de assinatura."""
    
    id: UUID
    documento_id: UUID
    usuario_id: UUID
    
    metodo: AssinaturaMetodo
    status: AssinaturaStatus
    
    documento_hash: str
    
    assinado_em: Optional[datetime] = None
    expira_em: Optional[datetime] = None


class AssinaturaVerify(BaseSchema):
    """Response de verificação de assinatura."""
    
    valida: bool
    documento_hash: str
    assinatura_hash: str
    assinado_em: Optional[datetime] = None
    usuario_nome: Optional[str] = None
    certificado_info: Optional[dict] = None  # Para ICP-Brasil


# ============================================================================
# LOTE DE DOCUMENTOS
# ============================================================================

class LoteDocumentosCreate(BaseSchema):
    """Schema para criar lote de documentos."""
    
    tipo: DocumentoTipo
    titulo_template: str = Field(..., min_length=2, max_length=255)
    periodo_referencia: Optional[str] = None
    usuarios_ids: list[UUID]
    requer_assinatura: bool = True


class LoteDocumentosUpload(BaseSchema):
    """Schema para upload em lote."""
    
    arquivos: list[DocumentoUpload]
    usuario_arquivo_map: dict[str, UUID]  # arquivo_nome -> usuario_id


class LoteDocumentosStatus(BaseSchema):
    """Status do processamento de lote."""
    
    lote_id: UUID
    total: int
    processados: int
    sucesso: int
    falha: int
    status: str  # pendente, processando, concluido, falha
    erros: list[dict] = []


# ============================================================================
# HOLERITE
# ============================================================================

class HoleriteImport(BaseSchema):
    """Schema para importar holerites."""
    
    periodo_referencia: str = Field(..., pattern=r"^\d{4}-\d{2}$")  # "2026-01"
    arquivo_base64: str
    formato: str = Field(default="pdf", pattern="^(pdf|xml)$")
    
    # Mapeamento (se não automático)
    mapeamento: Optional[dict] = None


class HoleriteRead(BaseSchema):
    """Schema de leitura de holerite."""
    
    id: UUID
    usuario_id: UUID
    usuario_nome: str
    
    periodo_referencia: str
    
    # Valores principais (parseados do PDF/XML)
    salario_bruto: Optional[float] = None
    descontos: Optional[float] = None
    salario_liquido: Optional[float] = None
    
    documento_url: str
    assinatura_status: AssinaturaStatus


# Circular import resolution
DocumentoWithAssinaturas.model_rebuild()
