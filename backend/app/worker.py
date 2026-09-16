"""Celery worker para tarefas em background."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# Criar app Celery
celery_app = Celery(
    "vibeponto",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.auditoria", "app.tasks.notificacoes", "app.tasks.exportacao", "app.tasks.beneficios"],
)

# Configurações
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutos
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Explicit module imports above also work when producers run outside the worker.


# Beat schedule (tarefas agendadas)
celery_app.conf.beat_schedule = {
    # Processar auditorias pendentes a cada 5 minutos
    "processar-auditorias-pendentes": {
        "task": "app.tasks.auditoria.processar_auditorias_pendentes",
        "schedule": 300.0,  # 5 minutos
    },
    # Enviar resumo diário às 18h
    "enviar-resumo-diario": {
        "task": "app.tasks.notificacoes.enviar_resumo_diario",
        "schedule": crontab(hour=18, minute=0),
    },
    # Processar recargas programadas à meia-noite
    "processar-recargas-programadas": {
        "task": "app.tasks.beneficios.processar_recargas_programadas",
        "schedule": crontab(hour=0, minute=0),
    },
}
