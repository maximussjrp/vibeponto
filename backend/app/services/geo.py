"""Serviço de geolocalização e geofencing."""

from dataclasses import dataclass
from decimal import Decimal
from math import atan2, cos, radians, sin, sqrt
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Perimetro, Usuario


@dataclass
class GeoPoint:
    """Representa um ponto geográfico."""
    
    latitude: Decimal
    longitude: Decimal
    accuracy_metros: Optional[float] = None


@dataclass
class GeoValidationResult:
    """Resultado de validação geográfica."""
    
    valido: bool
    perimetro_id: Optional[UUID] = None
    perimetro_nome: Optional[str] = None
    distancia_metros: Optional[float] = None
    dentro_tolerancia: bool = False
    mensagem: str = ""


class GeoService:
    """Serviço de geolocalização."""
    
    # Raio da Terra em metros
    EARTH_RADIUS_METERS = 6_371_000
    
    def calcular_distancia_haversine(
        self,
        ponto1: GeoPoint,
        ponto2: GeoPoint,
    ) -> float:
        """
        Calcula distância entre dois pontos usando fórmula de Haversine.
        
        Retorna distância em metros.
        """
        lat1 = radians(float(ponto1.latitude))
        lat2 = radians(float(ponto2.latitude))
        delta_lat = radians(float(ponto2.latitude) - float(ponto1.latitude))
        delta_lon = radians(float(ponto2.longitude) - float(ponto1.longitude))
        
        a = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return self.EARTH_RADIUS_METERS * c
    
    def ponto_dentro_circulo(
        self,
        ponto: GeoPoint,
        centro: GeoPoint,
        raio_metros: float,
        tolerancia_metros: float = 0,
    ) -> tuple[bool, float]:
        """
        Verifica se ponto está dentro de um círculo (com tolerância).
        
        Returns:
            tuple: (dentro, distancia_metros)
        """
        distancia = self.calcular_distancia_haversine(ponto, centro)
        raio_efetivo = raio_metros + tolerancia_metros
        
        # Considerar accuracy do GPS
        if ponto.accuracy_metros:
            raio_efetivo += ponto.accuracy_metros
        
        return distancia <= raio_efetivo, distancia
    
    def ponto_dentro_poligono(
        self,
        ponto: GeoPoint,
        vertices: list[GeoPoint],
    ) -> bool:
        """
        Verifica se ponto está dentro de um polígono usando Ray Casting.
        """
        n = len(vertices)
        if n < 3:
            return False
        
        x = float(ponto.longitude)
        y = float(ponto.latitude)
        
        inside = False
        j = n - 1
        
        for i in range(n):
            xi = float(vertices[i].longitude)
            yi = float(vertices[i].latitude)
            xj = float(vertices[j].longitude)
            yj = float(vertices[j].latitude)
            
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            
            j = i
        
        return inside
    
    async def validar_localizacao(
        self,
        db: AsyncSession,
        ponto: GeoPoint,
        usuario_id: UUID,
        tenant_id: UUID,
        perimetro_id: Optional[UUID] = None,
    ) -> GeoValidationResult:
        """
        Valida localização do usuário contra perímetros cadastrados.
        
        Se perimetro_id for fornecido, valida apenas contra esse perímetro.
        Senão, valida contra todos os perímetros ativos do usuário.
        """
        # Buscar equipe do usuário
        result = await db.execute(
            select(Usuario.equipe_id).where(Usuario.id == usuario_id)
        )
        equipe_id = result.scalar_one_or_none()
        
        # Construir query de perímetros
        query = select(Perimetro).where(
            Perimetro.tenant_id == tenant_id,
            Perimetro.ativo == True,
        )
        
        if perimetro_id:
            query = query.where(Perimetro.id == perimetro_id)
        else:
            # Perímetros do usuário ou da equipe
            query = query.where(
                (Perimetro.usuario_id == usuario_id) |
                (Perimetro.equipe_id == equipe_id)
            )
        
        result = await db.execute(query)
        perimetros = result.scalars().all()
        
        if not perimetros:
            return GeoValidationResult(
                valido=True,
                mensagem="Nenhum perímetro configurado - marcação livre",
            )
        
        # Verificar cada perímetro
        melhor_match: Optional[tuple[Perimetro, float, bool]] = None
        
        for perimetro in perimetros:
            if perimetro.centro_lat is not None and perimetro.centro_lng is not None:
                # Validação circular
                centro = GeoPoint(
                    latitude=perimetro.centro_lat,
                    longitude=perimetro.centro_lng,
                )
                raio = perimetro.raio_metros or 100
                tolerancia = perimetro.tolerancia_metros or 0
                
                dentro, distancia = self.ponto_dentro_circulo(
                    ponto=ponto,
                    centro=centro,
                    raio_metros=raio,
                    tolerancia_metros=tolerancia,
                )
                
                if dentro:
                    return GeoValidationResult(
                        valido=True,
                        perimetro_id=perimetro.id,
                        perimetro_nome=perimetro.nome,
                        distancia_metros=distancia,
                        dentro_tolerancia=distancia > raio,
                        mensagem=f"Dentro do perímetro '{perimetro.nome}'",
                    )
                
                # Guardar melhor match para mensagem de erro
                if melhor_match is None or distancia < melhor_match[1]:
                    melhor_match = (perimetro, distancia, False)
            
        # Nenhum perímetro válido
        if melhor_match:
            perimetro, distancia, _ = melhor_match
            excesso = distancia - (perimetro.raio_metros or 100) - (perimetro.tolerancia_metros or 0)
            return GeoValidationResult(
                valido=False,
                perimetro_id=perimetro.id,
                perimetro_nome=perimetro.nome,
                distancia_metros=distancia,
                mensagem=f"Fora do perímetro '{perimetro.nome}' por {excesso:.0f}m",
            )
        
        return GeoValidationResult(
            valido=False,
            mensagem="Fora de todos os perímetros configurados",
        )
    
    def detectar_teletransporte(
        self,
        ponto_anterior: GeoPoint,
        ponto_atual: GeoPoint,
        intervalo_segundos: float,
        velocidade_maxima_kmh: float = 150,
    ) -> tuple[bool, float]:
        """
        Detecta se houve "teletransporte" (velocidade impossível).
        
        Velocidade máxima padrão: 150 km/h (considerando transporte rápido)
        
        Returns:
            tuple: (suspeito, velocidade_calculada_kmh)
        """
        if intervalo_segundos <= 0:
            return True, float("inf")
        
        distancia_metros = self.calcular_distancia_haversine(ponto_anterior, ponto_atual)
        velocidade_ms = distancia_metros / intervalo_segundos
        velocidade_kmh = velocidade_ms * 3.6
        
        suspeito = velocidade_kmh > velocidade_maxima_kmh
        
        return suspeito, velocidade_kmh
    
    def calcular_centro_poligono(self, vertices: list[GeoPoint]) -> GeoPoint:
        """Calcula centróide de um polígono."""
        if not vertices:
            raise ValueError("Lista de vértices vazia")
        
        sum_lat = sum(float(v.latitude) for v in vertices)
        sum_lng = sum(float(v.longitude) for v in vertices)
        n = len(vertices)
        
        return GeoPoint(
            latitude=Decimal(str(sum_lat / n)),
            longitude=Decimal(str(sum_lng / n)),
        )


# Singleton
geo_service = GeoService()
