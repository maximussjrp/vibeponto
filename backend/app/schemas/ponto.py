"""Schemas de ponto e marcações."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.models import (
    AuditoriaDecisao,
    MarcacaoEvento,
    MarcacaoStatus,
    MarcacaoTipo,
)
from app.schemas.base import BaseSchema, GeoPoint, TimestampSchema


# ============================================================================
# MARCAÇÃO DE PONTO
# ============================================================================

class MarcacaoBase(BaseSchema):
    """Schema base de marcação."""
    
    tipo: MarcacaoTipo
    evento: MarcacaoEvento
    timestamp_local: datetime
    timezone: str = "America/Sao_Paulo"


class MarcacaoCreate(MarcacaoBase):
    """Schema para criar marcação."""
    
    # Localização
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180)
    accuracy_metros: Optional[int] = Field(None, ge=0)
    
    # Dispositivo
    dispositivo_id: Optional[UUID] = None
    device_info: Optional[dict] = None
    
    # Evidências
    foto_base64: Optional[str] = None
    liveness_data: Optional[dict] = None
    
    # Modo
    modo: str = Field(default="online", pattern="^(online|offline)$")
    
    # Sync offline
    sync_id: Optional[str] = None  # ID local para sync


class MarcacaoOfflineSync(BaseSchema):
    """Schema para sync de marcações offline."""
    
    marcacoes: list[MarcacaoCreate]


class MarcacaoUpdate(BaseSchema):
    """Schema para atualizar marcação (correção)."""
    
    correcao_motivo: str = Field(..., min_length=10, max_length=500)
    correcao_novo_horario: datetime


class MarcacaoRead(MarcacaoBase, TimestampSchema):
    """Schema de leitura de marcação."""
    
    id: UUID
    tenant_id: UUID
    usuario_id: UUID
    dispositivo_id: Optional[UUID] = None
    perimetro_id: Optional[UUID] = None
    
    timestamp_servidor: datetime
    
    # Localização
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    accuracy_metros: Optional[int] = None
    
    # Status
    modo: str
    status: MarcacaoStatus
    suspeita: bool
    
    # Evidências
    foto_url: Optional[str] = None
    
    # Comprovante
    comprovante_hash: Optional[str] = None
    
    # Correção
    correcao_solicitada: bool
    correcao_motivo: Optional[str] = None
    correcao_novo_horario: Optional[datetime] = None
    correcao_aprovada_por: Optional[UUID] = None
    correcao_aprovada_em: Optional[datetime] = None


class MarcacaoWithAuditoria(MarcacaoRead):
    """Schema de marcação com auditoria."""
    
    auditoria: Optional["AuditoriaRead"] = None


# ============================================================================
# AUDITORIA
# ============================================================================

class AuditoriaRead(TimestampSchema):
    """Schema de leitura de auditoria."""
    
    id: UUID
    marcacao_id: UUID
    
    score: Decimal
    decisao: AuditoriaDecisao
    motivos: list[str]
    
    liveness_passed: bool
    liveness_score: Optional[Decimal] = None
    
    revisado_por: Optional[UUID] = None
    revisado_em: Optional[datetime] = None
    decisao_revisao: Optional[str] = None
    observacao_revisao: Optional[str] = None


class AuditoriaRevisao(BaseSchema):
    """Schema para revisão de auditoria."""
    
    decisao: AuditoriaDecisao
    observacao: str = Field(..., min_length=10, max_length=500)


# ============================================================================
# COMPROVANTE
# ============================================================================

class Comprovante(BaseSchema):
    """Schema de comprovante de ponto."""
    
    id: UUID
    marcacao_id: UUID
    usuario_nome: str
    usuario_matricula: str
    empresa_nome: str
    empresa_cnpj: str
    
    evento: MarcacaoEvento
    timestamp_local: datetime
    timezone: str
    
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    endereco: Optional[str] = None
    
    hash: str
    assinatura: str
    
    qr_code_url: Optional[str] = None


# ============================================================================
# ESPELHO DE PONTO
# ============================================================================

class EspelhoDia(BaseSchema):
    """Schema de um dia do espelho."""
    
    data: datetime
    marcacoes: list[MarcacaoRead]
    horas_trabalhadas: Optional[str] = None  # "08:30"
    horas_extras: Optional[str] = None
    horas_falta: Optional[str] = None
    observacoes: list[str] = []


class EspelhoPonto(BaseSchema):
    """Schema de espelho de ponto."""
    
    usuario_id: UUID
    usuario_nome: str
    usuario_matricula: str
    
    periodo_inicio: datetime
    periodo_fim: datetime
    
    dias: list[EspelhoDia]
    
    # Totais
    total_dias_trabalhados: int
    total_horas_trabalhadas: str
    total_horas_extras: str
    total_horas_falta: str
    total_atrasos: int
    total_faltas: int
    
    # Assinatura
    assinado_funcionario: bool = False
    assinado_funcionario_em: Optional[datetime] = None
    assinado_gestor: bool = False
    assinado_gestor_em: Optional[datetime] = None


class EspelhoFilter(BaseSchema):
    """Filtro para espelho de ponto."""
    
    usuario_id: Optional[UUID] = None
    equipe_id: Optional[UUID] = None
    periodo_inicio: datetime
    periodo_fim: datetime


# ============================================================================
# AEJ (Arquivo Eletrônico de Jornada)
# ============================================================================

class AEJExportRequest(BaseSchema):
    """Request para exportar AEJ."""
    
    periodo_inicio: datetime
    periodo_fim: datetime
    usuarios_ids: Optional[list[UUID]] = None
    equipe_id: Optional[UUID] = None
    formato: str = Field(default="txt", pattern="^(txt|xml|json)$")


class AEJExportResponse(BaseSchema):
    """Response da exportação AEJ."""
    
    arquivo_url: str
    arquivo_nome: str
    periodo_inicio: datetime
    periodo_fim: datetime
    total_registros: int
    hash: str
    gerado_em: datetime


# ============================================================================
# CORREÇÃO
# ============================================================================

class CorrecaoRequest(BaseSchema):
    """Request de correção de ponto."""
    
    marcacao_id: UUID
    motivo: str = Field(..., min_length=10, max_length=500)
    novo_horario: datetime
    evidencia_url: Optional[str] = None


class CorrecaoAprovacao(BaseSchema):
    """Schema para aprovação de correção."""
    
    aprovado: bool
    observacao: Optional[str] = Field(None, max_length=500)


class CorrecaoRead(BaseSchema):
    """Schema de leitura de correção."""
    
    marcacao_id: UUID
    motivo: str
    horario_original: datetime
    horario_solicitado: datetime
    
    status: str  # pendente, aprovado, rejeitado
    
    solicitado_por: UUID
    solicitado_em: datetime
    
    aprovado_por: Optional[UUID] = None
    aprovado_em: Optional[datetime] = None
    observacao_aprovador: Optional[str] = None


# Circular import resolution
MarcacaoWithAuditoria.model_rebuild()
