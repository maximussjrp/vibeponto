"""Schemas de geofencing, escalas e dispositivos."""

from datetime import datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import Field

from app.models import DispositivoTipo, EscalaRegime
from app.schemas.base import BaseSchema, GeoPoint, GeoPolygon, TimestampSchema


# ============================================================================
# PERÍMETRO (Geofencing)
# ============================================================================

class PerimetroBase(BaseSchema):
    """Schema base de perímetro."""
    
    nome: str = Field(..., min_length=2, max_length=255)
    descricao: Optional[str] = None


class PerimetroCreateCircle(PerimetroBase):
    """Schema para criar perímetro circular."""
    
    centro_lat: Decimal = Field(..., ge=-90, le=90)
    centro_lng: Decimal = Field(..., ge=-180, le=180)
    raio_metros: int = Field(..., ge=10, le=10000)
    
    tolerancia_metros: int = Field(default=50, ge=0, le=1000)
    tolerancia_minutos: int = Field(default=5, ge=0, le=60)
    
    usuario_id: Optional[UUID] = None
    equipe_id: Optional[UUID] = None


class PerimetroCreatePolygon(PerimetroBase):
    """Schema para criar perímetro poligonal."""
    
    polygon: GeoPolygon
    
    tolerancia_metros: int = Field(default=50, ge=0, le=1000)
    tolerancia_minutos: int = Field(default=5, ge=0, le=60)
    
    usuario_id: Optional[UUID] = None
    equipe_id: Optional[UUID] = None


class PerimetroUpdate(BaseSchema):
    """Schema para atualizar perímetro."""
    
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    descricao: Optional[str] = None
    
    centro_lat: Optional[Decimal] = Field(None, ge=-90, le=90)
    centro_lng: Optional[Decimal] = Field(None, ge=-180, le=180)
    raio_metros: Optional[int] = Field(None, ge=10, le=10000)
    
    tolerancia_metros: Optional[int] = Field(None, ge=0, le=1000)
    tolerancia_minutos: Optional[int] = Field(None, ge=0, le=60)
    
    ativo: Optional[bool] = None


class PerimetroRead(PerimetroBase, TimestampSchema):
    """Schema de leitura de perímetro."""
    
    id: UUID
    tenant_id: UUID
    
    usuario_id: Optional[UUID] = None
    equipe_id: Optional[UUID] = None
    
    # Centro (para círculos)
    centro_lat: Optional[Decimal] = None
    centro_lng: Optional[Decimal] = None
    raio_metros: Optional[int] = None
    
    # Polígono (coordenadas)
    polygon_coordinates: Optional[list[list[float]]] = None
    
    tolerancia_metros: int
    tolerancia_minutos: int
    
    ativo: bool


class PerimetroValidateRequest(BaseSchema):
    """Request para validar posição dentro de perímetro."""
    
    latitude: Decimal = Field(..., ge=-90, le=90)
    longitude: Decimal = Field(..., ge=-180, le=180)
    perimetro_id: Optional[UUID] = None  # Se None, valida contra todos ativos


class PerimetroValidateResponse(BaseSchema):
    """Response de validação de perímetro."""
    
    dentro: bool
    perimetro_id: Optional[UUID] = None
    perimetro_nome: Optional[str] = None
    distancia_metros: Optional[int] = None
    tolerancia_excedida: bool = False


# ============================================================================
# ESCALA
# ============================================================================

class JanelaHorario(BaseSchema):
    """Schema de janela de horário."""
    
    entrada: str = Field(..., pattern=r"^\d{2}:\d{2}$")  # "08:00"
    saida: str = Field(..., pattern=r"^\d{2}:\d{2}$")    # "17:00"
    pausa_minutos: int = Field(default=60, ge=0)


class EscalaBase(BaseSchema):
    """Schema base de escala."""
    
    nome: str = Field(..., min_length=2, max_length=255)
    regime: EscalaRegime = EscalaRegime.FIXO


class EscalaCreate(EscalaBase):
    """Schema para criar escala."""
    
    usuario_id: Optional[UUID] = None
    equipe_id: Optional[UUID] = None
    
    # Janelas por dia da semana
    janelas: dict[str, JanelaHorario] = Field(
        default_factory=dict,
        description="Janelas por dia (seg, ter, qua, qui, sex, sab, dom)"
    )
    
    # Pausas remuneradas
    pausas_remuneradas: Optional[dict] = None
    
    # Regras
    regras_he: Optional[dict] = None
    regras_banco_horas: Optional[dict] = None
    
    # Tolerâncias
    tolerancia_entrada_min: int = Field(default=10, ge=0, le=60)
    tolerancia_saida_min: int = Field(default=10, ge=0, le=60)
    
    # Vigência
    vigencia_inicio: Optional[datetime] = None
    vigencia_fim: Optional[datetime] = None


class EscalaUpdate(BaseSchema):
    """Schema para atualizar escala."""
    
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    regime: Optional[EscalaRegime] = None
    
    janelas: Optional[dict[str, JanelaHorario]] = None
    pausas_remuneradas: Optional[dict] = None
    regras_he: Optional[dict] = None
    regras_banco_horas: Optional[dict] = None
    
    tolerancia_entrada_min: Optional[int] = Field(None, ge=0, le=60)
    tolerancia_saida_min: Optional[int] = Field(None, ge=0, le=60)
    
    vigencia_inicio: Optional[datetime] = None
    vigencia_fim: Optional[datetime] = None
    
    ativa: Optional[bool] = None


class EscalaRead(EscalaBase, TimestampSchema):
    """Schema de leitura de escala."""
    
    id: UUID
    tenant_id: UUID
    
    usuario_id: Optional[UUID] = None
    equipe_id: Optional[UUID] = None
    
    janelas: dict
    pausas_remuneradas: Optional[dict] = None
    regras_he: Optional[dict] = None
    regras_banco_horas: Optional[dict] = None
    
    tolerancia_entrada_min: int
    tolerancia_saida_min: int
    
    vigencia_inicio: Optional[datetime] = None
    vigencia_fim: Optional[datetime] = None
    
    ativa: bool


# ============================================================================
# DISPOSITIVO
# ============================================================================

class DispositivoBase(BaseSchema):
    """Schema base de dispositivo."""
    
    tipo: DispositivoTipo
    nome: str = Field(..., min_length=2, max_length=255)


class DispositivoRegister(DispositivoBase):
    """Schema para registrar dispositivo."""
    
    device_id: str = Field(..., min_length=10, max_length=255)
    plataforma: Optional[str] = None
    versao_app: Optional[str] = None
    versao_os: Optional[str] = None
    
    push_token: Optional[str] = None
    
    # Attestation
    attestation_data: Optional[dict] = None


class DispositivoUpdate(BaseSchema):
    """Schema para atualizar dispositivo."""
    
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    push_token: Optional[str] = None
    versao_app: Optional[str] = None
    attestation_data: Optional[dict] = None
    ativo: Optional[bool] = None


class DispositivoRead(DispositivoBase, TimestampSchema):
    """Schema de leitura de dispositivo."""
    
    id: UUID
    tenant_id: UUID
    usuario_id: Optional[UUID] = None
    
    device_id: str
    plataforma: Optional[str] = None
    versao_app: Optional[str] = None
    versao_os: Optional[str] = None
    
    is_rooted: bool
    ativo: bool
    ultimo_seen: Optional[datetime] = None


class DispositivoAttestation(BaseSchema):
    """Schema de attestation de dispositivo."""
    
    is_valid: bool
    is_rooted: bool
    is_emulator: bool
    integrity_token: Optional[str] = None
    details: Optional[dict] = None
