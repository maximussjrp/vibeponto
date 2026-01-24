"""Tarefas de auditoria em background."""

import asyncio
from uuid import UUID

from celery import shared_task

from app.core.database import async_session_maker
from app.services.auditoria import auditoria_service


@shared_task(bind=True, max_retries=3)
def processar_auditoria_marcacao(self, marcacao_id: str, tenant_id: str):
    """
    Processa auditoria de uma marcação específica.
    
    Args:
        marcacao_id: ID da marcação
        tenant_id: ID do tenant
    """
    try:
        asyncio.run(_processar_auditoria(marcacao_id, tenant_id))
    except Exception as exc:
        self.retry(exc=exc, countdown=60)


async def _processar_auditoria(marcacao_id: str, tenant_id: str):
    """Helper async para processar auditoria."""
    async with async_session_maker() as db:
        await auditoria_service.processar_marcacao(
            db=db,
            marcacao_id=UUID(marcacao_id),
            tenant_id=UUID(tenant_id),
        )
        await db.commit()


@shared_task
def processar_auditorias_pendentes():
    """Processa todas as auditorias pendentes."""
    asyncio.run(_processar_pendentes())


async def _processar_pendentes():
    """Helper async para processar pendentes."""
    from sqlalchemy import select
    
    from app.models import MarcacaoPonto, MarcacaoStatus
    
    async with async_session_maker() as db:
        # Buscar marcações pendentes
        stmt = select(MarcacaoPonto).where(
            MarcacaoPonto.status == MarcacaoStatus.PENDENTE,
        ).limit(100)
        
        result = await db.execute(stmt)
        marcacoes = result.scalars().all()
        
        for marcacao in marcacoes:
            try:
                await auditoria_service.processar_marcacao(
                    db=db,
                    marcacao_id=marcacao.id,
                    tenant_id=marcacao.tenant_id,
                )
            except Exception as e:
                print(f"Erro ao processar marcação {marcacao.id}: {e}")
                continue
        
        await db.commit()
