"""Schemas base e utilitários."""

from datetime import datetime
from typing import Generic, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# TypeVar para paginação genérica
T = TypeVar("T")


class BaseSchema(BaseModel):
    """Schema base com configuração padrão."""
    
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class TimestampSchema(BaseSchema):
    """Schema com timestamps."""
    
    created_at: datetime
    updated_at: datetime


class PaginationParams(BaseModel):
    """Parâmetros de paginação."""
    
    page: int = Field(default=1, ge=1, description="Número da página")
    per_page: int = Field(default=20, ge=1, le=100, description="Itens por página")
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page
    
    @property
    def limit(self) -> int:
        return self.per_page


class PaginatedResponse(BaseModel, Generic[T]):
    """Resposta paginada genérica."""
    
    items: list[T]
    total: int
    page: int
    per_page: int
    pages: int
    
    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        per_page: int,
    ) -> "PaginatedResponse[T]":
        pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
        )


class ErrorResponse(BaseModel):
    """Resposta de erro padrão."""
    
    code: str
    message: str
    details: Optional[dict] = None


class SuccessResponse(BaseModel):
    """Resposta de sucesso genérica."""
    
    success: bool = True
    message: Optional[str] = None
    data: Optional[dict] = None


# ============================================================================
# FILTROS COMUNS
# ============================================================================

class DateRangeFilter(BaseModel):
    """Filtro por intervalo de datas."""
    
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class SearchFilter(BaseModel):
    """Filtro de busca."""
    
    q: Optional[str] = Field(None, min_length=1, max_length=100)


# ============================================================================
# GEO SCHEMAS
# ============================================================================

class GeoPoint(BaseModel):
    """Ponto geográfico."""
    
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_metros: Optional[int] = Field(None, ge=0)


class GeoPolygon(BaseModel):
    """Polígono geográfico."""
    
    coordinates: list[list[float]]  # Lista de [lng, lat]
    
    @property
    def is_valid(self) -> bool:
        """Verifica se o polígono é válido (mínimo 4 pontos, fechado)."""
        if len(self.coordinates) < 4:
            return False
        return self.coordinates[0] == self.coordinates[-1]
