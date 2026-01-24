"""Serviço de AuditorIA - Análise de fraude em marcações."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    Auditoria,
    AuditoriaDecisao,
    MarcacaoPonto,
    MarcacaoStatus,
    Perimetro,
    Usuario,
)


@dataclass
class AuditoriaResult:
    """Resultado da análise de auditoria."""
    
    score: Decimal
    decisao: AuditoriaDecisao
    motivos: list[str]
    liveness_passed: bool
    liveness_score: Optional[Decimal]
    liveness_hints: Optional[dict]


class AuditorIAService:
    """
    Serviço de auditoria automática de marcações.
    
    Analisa múltiplos fatores para detectar possíveis fraudes:
    - Verificação de geolocalização
    - Análise de liveness (anti-spoofing facial)
    - Detecção de padrões anômalos
    - Validação de dispositivo
    - Comparação facial (se disponível)
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.face_similarity_threshold = settings.auditoria_face_similarity_threshold
        self.geo_tolerance_meters = settings.auditoria_geo_tolerance_meters
        self.liveness_threshold = settings.auditoria_liveness_threshold
    
    async def analisar_marcacao(self, marcacao: MarcacaoPonto) -> AuditoriaResult:
        """
        Analisa uma marcação e retorna resultado de auditoria.
        
        O score vai de 0.0 (fraude certa) a 1.0 (legítimo).
        """
        motivos = []
        scores = []
        liveness_passed = True
        liveness_score = None
        liveness_hints = None
        
        # 1. Verificar geolocalização
        geo_score = await self._verificar_geolocalizacao(marcacao)
        scores.append(geo_score)
        if geo_score < 0.5:
            motivos.append("Localização fora do perímetro permitido")
        elif geo_score < 0.8:
            motivos.append("Localização próxima ao limite do perímetro")
        
        # 2. Verificar liveness (se dados disponíveis)
        if marcacao.evidencias and "liveness" in marcacao.evidencias:
            liveness_result = self._verificar_liveness(marcacao.evidencias["liveness"])
            liveness_score = liveness_result["score"]
            liveness_passed = liveness_result["passed"]
            liveness_hints = liveness_result.get("hints")
            scores.append(float(liveness_score))
            
            if not liveness_passed:
                motivos.append("Falha na verificação de liveness")
        
        # 3. Verificar padrões anômalos
        anomaly_score = await self._verificar_anomalias(marcacao)
        scores.append(anomaly_score)
        if anomaly_score < 0.5:
            motivos.append("Padrão de marcação anômalo detectado")
        
        # 4. Verificar dispositivo
        device_score = await self._verificar_dispositivo(marcacao)
        scores.append(device_score)
        if device_score < 0.5:
            motivos.append("Dispositivo não reconhecido ou suspeito")
        
        # 5. Verificar velocidade entre marcações
        velocity_score = await self._verificar_velocidade(marcacao)
        scores.append(velocity_score)
        if velocity_score < 0.5:
            motivos.append("Deslocamento impossível entre marcações")
        
        # Calcular score final (média ponderada)
        if scores:
            final_score = Decimal(str(sum(scores) / len(scores)))
        else:
            final_score = Decimal("1.0")
        
        # Determinar decisão
        if final_score >= Decimal("0.8") and liveness_passed:
            decisao = AuditoriaDecisao.APROVADA
        elif final_score >= Decimal("0.5"):
            decisao = AuditoriaDecisao.REVISAO
        else:
            decisao = AuditoriaDecisao.REPROVADA
        
        return AuditoriaResult(
            score=final_score,
            decisao=decisao,
            motivos=motivos,
            liveness_passed=liveness_passed,
            liveness_score=liveness_score,
            liveness_hints=liveness_hints,
        )
    
    async def _verificar_geolocalizacao(self, marcacao: MarcacaoPonto) -> float:
        """Verifica se a marcação está dentro do perímetro permitido."""
        
        if not marcacao.latitude or not marcacao.longitude:
            # Sem geolocalização - pode ser configuração do tenant
            return 0.7
        
        # Buscar perímetros aplicáveis
        result = await self.db.execute(
            select(Usuario.equipe_id).where(Usuario.id == marcacao.usuario_id)
        )
        equipe_id = result.scalar_one_or_none()
        
        result = await self.db.execute(
            select(Perimetro).where(
                Perimetro.tenant_id == marcacao.tenant_id,
                Perimetro.ativo == True,
                (
                    (Perimetro.usuario_id == marcacao.usuario_id) |
                    (Perimetro.equipe_id == equipe_id)
                )
            )
        )
        perimetros = result.scalars().all()
        
        if not perimetros:
            # Sem perímetros configurados
            return 1.0
        
        # Calcular distância para cada perímetro (simplificado)
        from math import radians, sin, cos, sqrt, atan2
        
        def haversine_distance(lat1, lon1, lat2, lon2):
            R = 6371000
            lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            return R * c
        
        for p in perimetros:
            if p.centro_lat and p.centro_lng and p.raio_metros:
                distancia = haversine_distance(
                    marcacao.latitude, marcacao.longitude,
                    p.centro_lat, p.centro_lng
                )
                
                raio_total = p.raio_metros + p.tolerancia_metros
                
                if distancia <= p.raio_metros:
                    return 1.0
                elif distancia <= raio_total:
                    # Dentro da tolerância
                    return 0.8
                elif distancia <= raio_total * 1.5:
                    return 0.5
        
        return 0.2
    
    def _verificar_liveness(self, liveness_data: dict) -> dict:
        """Verifica dados de liveness da foto."""
        
        # Simulação - em produção usar SDK de liveness (AWS Rekognition, etc.)
        score = liveness_data.get("score", 0.0)
        
        return {
            "score": Decimal(str(score)),
            "passed": score >= self.liveness_threshold,
            "hints": liveness_data.get("hints"),
        }
    
    async def _verificar_anomalias(self, marcacao: MarcacaoPonto) -> float:
        """Detecta padrões anômalos nas marcações."""
        
        # Buscar marcações recentes do usuário
        result = await self.db.execute(
            select(MarcacaoPonto).where(
                MarcacaoPonto.usuario_id == marcacao.usuario_id,
                MarcacaoPonto.id != marcacao.id,
                MarcacaoPonto.timestamp_servidor >= datetime.utcnow() - timedelta(days=30),
            ).order_by(MarcacaoPonto.timestamp_servidor.desc()).limit(100)
        )
        historico = result.scalars().all()
        
        if len(historico) < 5:
            # Pouco histórico - não dá para detectar anomalias
            return 0.8
        
        # Analisar horário típico
        hora_atual = marcacao.timestamp_local.hour
        horas_tipicas = [m.timestamp_local.hour for m in historico if m.evento == marcacao.evento]
        
        if horas_tipicas:
            media_hora = sum(horas_tipicas) / len(horas_tipicas)
            desvio = abs(hora_atual - media_hora)
            
            if desvio > 4:
                return 0.4
            elif desvio > 2:
                return 0.7
        
        return 1.0
    
    async def _verificar_dispositivo(self, marcacao: MarcacaoPonto) -> float:
        """Verifica se o dispositivo é confiável."""
        
        if not marcacao.dispositivo_id:
            return 0.6
        
        from app.models import Dispositivo
        
        result = await self.db.execute(
            select(Dispositivo).where(Dispositivo.id == marcacao.dispositivo_id)
        )
        dispositivo = result.scalar_one_or_none()
        
        if not dispositivo:
            return 0.4
        
        if not dispositivo.ativo:
            return 0.2
        
        if dispositivo.is_rooted:
            return 0.3
        
        # Verificar attestation
        if dispositivo.attestation_data:
            if not dispositivo.attestation_data.get("is_valid", False):
                return 0.4
        
        return 1.0
    
    async def _verificar_velocidade(self, marcacao: MarcacaoPonto) -> float:
        """
        Verifica se é fisicamente possível o deslocamento entre marcações.
        
        Detecta 'teleporte' - marcações em locais distantes em tempo curto.
        """
        
        if not marcacao.latitude or not marcacao.longitude:
            return 1.0
        
        # Buscar última marcação com geolocalização
        result = await self.db.execute(
            select(MarcacaoPonto).where(
                MarcacaoPonto.usuario_id == marcacao.usuario_id,
                MarcacaoPonto.id != marcacao.id,
                MarcacaoPonto.latitude.isnot(None),
                MarcacaoPonto.timestamp_servidor < marcacao.timestamp_servidor,
            ).order_by(MarcacaoPonto.timestamp_servidor.desc()).limit(1)
        )
        ultima = result.scalar_one_or_none()
        
        if not ultima:
            return 1.0
        
        # Calcular distância e tempo
        from math import radians, sin, cos, sqrt, atan2
        
        def haversine_distance(lat1, lon1, lat2, lon2):
            R = 6371000
            lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            return R * c
        
        distancia = haversine_distance(
            marcacao.latitude, marcacao.longitude,
            ultima.latitude, ultima.longitude
        )
        
        tempo_segundos = (marcacao.timestamp_servidor - ultima.timestamp_servidor).total_seconds()
        
        if tempo_segundos <= 0:
            return 0.5
        
        # Velocidade em km/h
        velocidade_kmh = (distancia / 1000) / (tempo_segundos / 3600)
        
        # Limites razoáveis
        if velocidade_kmh > 500:  # Mais rápido que avião comercial
            return 0.1
        elif velocidade_kmh > 150:  # Mais rápido que carro em rodovia
            return 0.4
        elif velocidade_kmh > 80:
            return 0.7
        
        return 1.0
    
    async def salvar_auditoria(
        self,
        marcacao_id: UUID,
        resultado: AuditoriaResult,
    ) -> Auditoria:
        """Salva o resultado da auditoria no banco."""
        
        auditoria = Auditoria(
            marcacao_id=marcacao_id,
            score=resultado.score,
            decisao=resultado.decisao,
            motivos=resultado.motivos,
            liveness_passed=resultado.liveness_passed,
            liveness_score=resultado.liveness_score,
            liveness_hints=resultado.liveness_hints,
        )
        
        self.db.add(auditoria)
        await self.db.commit()
        await self.db.refresh(auditoria)
        
        return auditoria
    
    async def processar_marcacao(self, marcacao: MarcacaoPonto) -> Auditoria:
        """
        Processa uma marcação completa.
        
        1. Analisa a marcação
        2. Salva resultado da auditoria
        3. Atualiza status da marcação
        """
        from sqlalchemy import update
        
        # Analisar
        resultado = await self.analisar_marcacao(marcacao)
        
        # Salvar auditoria
        auditoria = await self.salvar_auditoria(marcacao.id, resultado)
        
        # Atualizar marcação
        novo_status = MarcacaoStatus.PROCESSADO
        suspeita = False
        
        if resultado.decisao == AuditoriaDecisao.REVISAO:
            suspeita = True
        elif resultado.decisao == AuditoriaDecisao.REPROVADA:
            novo_status = MarcacaoStatus.SUSPEITA
            suspeita = True
        
        await self.db.execute(
            update(MarcacaoPonto)
            .where(MarcacaoPonto.id == marcacao.id)
            .values(status=novo_status, suspeita=suspeita)
        )
        await self.db.commit()
        
        return auditoria


async def processar_auditoria_background(
    db: AsyncSession,
    marcacao_id: UUID,
):
    """
    Task para processar auditoria em background.
    
    Chamada via Celery ou similar após criação de marcação.
    """
    result = await db.execute(
        select(MarcacaoPonto).where(MarcacaoPonto.id == marcacao_id)
    )
    marcacao = result.scalar_one_or_none()
    
    if not marcacao:
        return
    
    service = AuditorIAService(db)
    await service.processar_marcacao(marcacao)
