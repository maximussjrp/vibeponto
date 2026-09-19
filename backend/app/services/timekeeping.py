"""Domain service for timekeeping records."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability import record_offline_sync, record_time_entry
from app.models import MarcacaoPonto, MarcacaoStatus
from app.schemas import MarcacaoCreate
from app.services.geo import GeoPoint, geo_service


@dataclass(slots=True)
class MarcacaoContext:
    tenant_id: UUID
    usuario_id: UUID
    ip_address: str | None = None
    user_agent: str | None = None
    origem: str = "api"


def has_coordinates(latitude: Decimal | float | None, longitude: Decimal | float | None) -> bool:
    return latitude is not None and longitude is not None


def point_geom(latitude: Decimal | float | None, longitude: Decimal | float | None):
    if not has_coordinates(latitude, longitude):
        return None
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def comprovante_hash(usuario_id: UUID, evento: Any, timestamp_local: datetime, sync_id: str | None = None) -> str:
    data = f"{usuario_id}|{evento}|{timestamp_local.isoformat()}|{sync_id or ''}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


async def build_marcacao_values(
    db: AsyncSession,
    data: MarcacaoCreate,
    context: MarcacaoContext,
    modo: str,
) -> dict[str, Any]:
    perimetro_id = None
    suspeita = False
    geo_valido = True
    geo_evidence: dict[str, Any] = {}

    if has_coordinates(data.latitude, data.longitude):
        ponto = GeoPoint(
            latitude=data.latitude,
            longitude=data.longitude,
            accuracy_metros=float(data.accuracy_metros) if data.accuracy_metros is not None else None,
        )
        resultado_geo = await geo_service.validar_localizacao(
            db=db,
            ponto=ponto,
            usuario_id=context.usuario_id,
            tenant_id=context.tenant_id,
        )
        geo_valido = resultado_geo.valido
        perimetro_id = resultado_geo.perimetro_id
        suspeita = not geo_valido
        geo_evidence = {
            "geo_valido": resultado_geo.valido,
            "geo_mensagem": resultado_geo.mensagem,
            "distancia_metros": resultado_geo.distancia_metros,
        }

    result = await db.execute(
        select(MarcacaoPonto)
        .where(
            MarcacaoPonto.usuario_id == context.usuario_id,
            MarcacaoPonto.tenant_id == context.tenant_id,
        )
        .order_by(MarcacaoPonto.timestamp_local.desc())
        .limit(1)
    )
    ultima_marcacao = result.scalar_one_or_none()

    if (
        ultima_marcacao
        and has_coordinates(data.latitude, data.longitude)
        and has_coordinates(ultima_marcacao.latitude, ultima_marcacao.longitude)
    ):
        intervalo = (data.timestamp_local - ultima_marcacao.timestamp_local).total_seconds()
        if intervalo > 0:
            teletransporte, velocidade = geo_service.detectar_teletransporte(
                ponto_anterior=GeoPoint(latitude=ultima_marcacao.latitude, longitude=ultima_marcacao.longitude),
                ponto_atual=GeoPoint(latitude=data.latitude, longitude=data.longitude),
                intervalo_segundos=intervalo,
            )
            if teletransporte:
                suspeita = True
                geo_evidence["teletransporte"] = True
                geo_evidence["velocidade_kmh"] = velocidade

    evidencias = {
        "origem": context.origem,
        "modo": modo,
        "ip_address": context.ip_address,
        "user_agent": context.user_agent,
        "device_info": data.device_info,
        "liveness": data.liveness_data,
        **geo_evidence,
    }
    if data.sync_id:
        evidencias["sync_id"] = data.sync_id

    return {
        "tenant_id": context.tenant_id,
        "usuario_id": context.usuario_id,
        "dispositivo_id": data.dispositivo_id,
        "perimetro_id": perimetro_id,
        "tipo": data.tipo,
        "evento": data.evento,
        "timestamp_local": data.timestamp_local,
        "timezone": data.timezone,
        "geom": point_geom(data.latitude, data.longitude),
        "latitude": data.latitude,
        "longitude": data.longitude,
        "accuracy_metros": data.accuracy_metros,
        "sync_id": data.sync_id,
        "modo": modo,
        "status": MarcacaoStatus.PENDENTE,
        "suspeita": suspeita,
        "evidencias": evidencias,
        "comprovante_hash": comprovante_hash(context.usuario_id, data.evento, data.timestamp_local, data.sync_id),
    }


async def create_marcacao(
    db: AsyncSession,
    data: MarcacaoCreate,
    context: MarcacaoContext,
    modo: str = "online",
) -> MarcacaoPonto:
    try:
        values = await build_marcacao_values(db, data, context, modo)
        marcacao = MarcacaoPonto(**values)
        db.add(marcacao)
        await db.flush()
        await db.refresh(marcacao)
        record_time_entry(modo, "success")
        return marcacao
    except Exception:
        record_time_entry(modo, "error")
        raise


async def create_offline_marcacao_idempotent(
    db: AsyncSession,
    data: MarcacaoCreate,
    context: MarcacaoContext,
) -> MarcacaoPonto:
    if not data.sync_id:
        try:
            marcacao = await create_marcacao(db, data, context, modo="offline")
            record_offline_sync("success")
            return marcacao
        except Exception:
            record_offline_sync("error")
            raise

    try:
        values = await build_marcacao_values(db, data, context, "offline")
        stmt = (
            insert(MarcacaoPonto)
            .values(**values)
            .on_conflict_do_nothing(
                index_elements=["tenant_id", "usuario_id", "sync_id"],
                index_where=MarcacaoPonto.sync_id.isnot(None),
            )
            .returning(MarcacaoPonto.id)
        )
        inserted_id = (await db.execute(stmt)).scalar_one_or_none()
        marcacao_id = inserted_id
        if marcacao_id is None:
            result = await db.execute(
                select(MarcacaoPonto.id).where(
                    MarcacaoPonto.tenant_id == context.tenant_id,
                    MarcacaoPonto.usuario_id == context.usuario_id,
                    MarcacaoPonto.sync_id == data.sync_id,
                )
            )
            marcacao_id = result.scalar_one()
            record_offline_sync("duplicate")
        else:
            record_offline_sync("success")
            record_time_entry("offline", "success")

        result = await db.execute(select(MarcacaoPonto).where(MarcacaoPonto.id == marcacao_id))
        return result.scalar_one()
    except Exception:
        record_offline_sync("error")
        record_time_entry("offline", "error")
        raise
