"""Schemas de benefícios e carteiras."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import Field

from app.models import BeneficioTipo, CartaoStatus
from app.schemas.base import BaseSchema, TimestampSchema


# ============================================================================
# CARTEIRA DE BENEFÍCIO
# ============================================================================

class CarteiraBase(BaseSchema):
    """Schema base de carteira."""
    
    tipo: BeneficioTipo
    nome: str = Field(..., min_length=2, max_length=100)


class CarteiraCreate(CarteiraBase):
    """Schema para criar carteira."""
    
    usuario_id: UUID
    politica: Optional[dict] = None


class CarteiraUpdate(BaseSchema):
    """Schema para atualizar carteira."""
    
    nome: Optional[str] = Field(None, min_length=2, max_length=100)
    politica: Optional[dict] = None
    ativa: Optional[bool] = None


class CarteiraRead(CarteiraBase, TimestampSchema):
    """Schema de leitura de carteira."""
    
    id: UUID
    tenant_id: UUID
    usuario_id: UUID
    
    saldo: Decimal
    saldo_bloqueado: Decimal
    
    politica: Optional[dict] = None
    ativa: bool


class CarteiraWithCards(CarteiraRead):
    """Schema de carteira com cartões."""
    
    cartoes: list["CartaoRead"] = []


class CarteiraSaldo(BaseSchema):
    """Schema de saldo de carteira."""
    
    carteira_id: UUID
    tipo: BeneficioTipo
    nome: str
    saldo_disponivel: Decimal
    saldo_bloqueado: Decimal
    ultima_transacao: Optional[datetime] = None


# ============================================================================
# CARTÃO
# ============================================================================

class CartaoBase(BaseSchema):
    """Schema base de cartão."""
    
    emissor: str = Field(..., min_length=2, max_length=100)


class CartaoCreate(CartaoBase):
    """Schema para criar/solicitar cartão."""
    
    carteira_id: UUID


class CartaoRead(CartaoBase, TimestampSchema):
    """Schema de leitura de cartão."""
    
    id: UUID
    carteira_id: UUID
    
    numero_mascarado: str
    status: CartaoStatus
    validade: Optional[str] = None


class CartaoBloqueio(BaseSchema):
    """Schema para bloquear/desbloquear cartão."""
    
    motivo: str = Field(..., min_length=5, max_length=255)


# ============================================================================
# RECARGA
# ============================================================================

class RecargaBase(BaseSchema):
    """Schema base de recarga."""
    
    valor: Decimal = Field(..., gt=0, le=10000)


class RecargaCreate(RecargaBase):
    """Schema para criar recarga individual."""
    
    carteira_id: UUID


class RecargaLote(BaseSchema):
    """Schema para recarga em lote."""
    
    recargas: list[RecargaCreate]
    referencia: Optional[str] = Field(None, max_length=100)


class RecargaRead(RecargaBase, TimestampSchema):
    """Schema de leitura de recarga."""
    
    id: UUID
    carteira_id: UUID
    
    taxa: Decimal
    status: str
    
    lote_id: Optional[UUID] = None
    referencia: Optional[str] = None
    
    processada_em: Optional[datetime] = None
    erro_mensagem: Optional[str] = None


class RecargaLoteStatus(BaseSchema):
    """Status do lote de recargas."""
    
    lote_id: UUID
    total: int
    processadas: int
    sucesso: int
    falha: int
    valor_total: Decimal
    taxa_total: Decimal
    status: str


# ============================================================================
# TRANSAÇÃO
# ============================================================================

class TransacaoBase(BaseSchema):
    """Schema base de transação."""
    
    tipo: str  # credito, debito
    valor: Decimal
    descricao: str


class TransacaoRead(TransacaoBase, TimestampSchema):
    """Schema de leitura de transação."""
    
    id: UUID
    carteira_id: UUID
    
    saldo_anterior: Decimal
    saldo_posterior: Decimal
    
    categoria: Optional[str] = None
    estabelecimento: Optional[str] = None
    
    external_id: Optional[str] = None


class TransacaoFilter(BaseSchema):
    """Filtro de transações."""
    
    carteira_id: Optional[UUID] = None
    tipo: Optional[str] = None
    categoria: Optional[str] = None
    data_inicio: Optional[datetime] = None
    data_fim: Optional[datetime] = None


class ExtratoResponse(BaseSchema):
    """Response de extrato."""
    
    carteira_id: UUID
    tipo: BeneficioTipo
    periodo_inicio: datetime
    periodo_fim: datetime
    
    saldo_inicial: Decimal
    saldo_final: Decimal
    
    total_creditos: Decimal
    total_debitos: Decimal
    
    transacoes: list[TransacaoRead]


# ============================================================================
# POLÍTICA DE BENEFÍCIO
# ============================================================================

class PoliticaBeneficio(BaseSchema):
    """Schema de política de benefício."""
    
    limite_diario: Optional[Decimal] = None
    limite_mensal: Optional[Decimal] = None
    
    categorias_permitidas: Optional[list[str]] = None
    categorias_bloqueadas: Optional[list[str]] = None
    
    dias_permitidos: Optional[list[str]] = None  # ["seg", "ter", ...]
    horario_inicio: Optional[str] = None  # "08:00"
    horario_fim: Optional[str] = None     # "22:00"
    
    acumulo_permitido: bool = True
    validade_meses: Optional[int] = None


# Circular import resolution
CarteiraWithCards.model_rebuild()
