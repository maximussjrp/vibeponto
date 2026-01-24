"""Tarefas de benefícios em background."""

import asyncio
from decimal import Decimal
from uuid import UUID

from celery import shared_task


@shared_task
def processar_recargas_programadas():
    """Processa recargas programadas para o dia."""
    asyncio.run(_processar_recargas())


async def _processar_recargas():
    """Helper async para processar recargas."""
    from datetime import date

    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.models import Recarga, RecargaStatus

    async with async_session_maker() as db:
        hoje = date.today()
        
        # Buscar recargas agendadas para hoje
        stmt = select(Recarga).where(
            Recarga.status == RecargaStatus.AGENDADA,
            Recarga.data_programada == hoje,
        )
        
        result = await db.execute(stmt)
        recargas = result.scalars().all()
        
        for recarga in recargas:
            try:
                await _executar_recarga(db, recarga)
            except Exception as e:
                print(f"Erro ao processar recarga {recarga.id}: {e}")
                recarga.status = RecargaStatus.FALHA
                recarga.erro = str(e)
        
        await db.commit()
        
        print(f"💳 {len(recargas)} recargas processadas")


async def _executar_recarga(db, recarga):
    """Executa uma recarga."""
    from app.models import BeneficioCarteira, RecargaStatus
    
    # Buscar carteira
    carteira = await db.get(BeneficioCarteira, recarga.carteira_id)
    if not carteira:
        raise ValueError("Carteira não encontrada")
    
    # Creditar saldo
    carteira.saldo += recarga.valor
    recarga.status = RecargaStatus.CONCLUIDA
    recarga.processado_em = __import__("datetime").datetime.now()


@shared_task
def notificar_saldo_baixo(carteira_id: str, saldo_atual: str, limite_minimo: str):
    """
    Notifica usuário sobre saldo baixo.
    
    Args:
        carteira_id: ID da carteira
        saldo_atual: Saldo atual
        limite_minimo: Limite configurado
    """
    from app.tasks.notificacoes import enviar_notificacao_push
    
    # TODO: Buscar usuário da carteira
    print(f"⚠️ Saldo baixo na carteira {carteira_id}: R$ {saldo_atual}")


@shared_task
def processar_estorno(transacao_id: str, motivo: str):
    """
    Processa estorno de transação.
    
    Args:
        transacao_id: ID da transação
        motivo: Motivo do estorno
    """
    asyncio.run(_processar_estorno(transacao_id, motivo))


async def _processar_estorno(transacao_id: str, motivo: str):
    """Helper async para processar estorno."""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.models import BeneficioCarteira, Transacao, TransacaoStatus

    async with async_session_maker() as db:
        transacao = await db.get(Transacao, UUID(transacao_id))
        if not transacao:
            raise ValueError("Transação não encontrada")
        
        # Marcar como estornada
        transacao.status = TransacaoStatus.ESTORNADA
        
        # Devolver saldo
        carteira = await db.get(BeneficioCarteira, transacao.carteira_id)
        carteira.saldo += transacao.valor
        
        await db.commit()
        
        print(f"↩️ Estorno processado: {transacao_id}")
