"""Tasks package."""

from app.tasks.auditoria import processar_auditoria_marcacao, processar_auditorias_pendentes
from app.tasks.beneficios import notificar_saldo_baixo, processar_estorno, processar_recargas_programadas
from app.tasks.exportacao import exportar_aej, exportar_espelho_pdf, exportar_relatorio_equipe
from app.tasks.notificacoes import enviar_alerta_auditoria, enviar_email, enviar_notificacao_push, enviar_resumo_diario

__all__ = [
    # Auditoria
    "processar_auditoria_marcacao",
    "processar_auditorias_pendentes",
    # Benefícios
    "processar_recargas_programadas",
    "notificar_saldo_baixo",
    "processar_estorno",
    # Exportação
    "exportar_aej",
    "exportar_espelho_pdf",
    "exportar_relatorio_equipe",
    # Notificações
    "enviar_notificacao_push",
    "enviar_email",
    "enviar_resumo_diario",
    "enviar_alerta_auditoria",
]
