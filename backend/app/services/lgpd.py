"""Serviço de compliance LGPD."""

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID
import hashlib
import json
import logging

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    AuditLog,
    BeneficioCarteira,
    Documento,
    MarcacaoPonto,
    Transacao,
    Usuario,
    UserStatus,
)


logger = logging.getLogger(__name__)


class LGPDService:
    """
    Serviço de conformidade com a Lei Geral de Proteção de Dados (LGPD).
    
    Implementa:
    - Direito de acesso aos dados (Art. 18, II)
    - Direito de correção (Art. 18, III)
    - Direito de exclusão/anonimização (Art. 18, VI)
    - Direito de portabilidade (Art. 18, V)
    - Registro de consentimento
    - Logs de auditoria
    - Retenção de dados
    """
    
    # =========================================================================
    # Consentimento
    # =========================================================================
    
    async def registrar_consentimento(
        self,
        db: AsyncSession,
        usuario_id: UUID,
        tipo_consentimento: str,
        consentido: bool,
        versao_politica: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Registra consentimento do usuário.
        
        Tipos:
        - termos_uso
        - politica_privacidade
        - coleta_biometrica
        - coleta_localizacao
        - marketing
        """
        await self._log_auditoria(
            db=db,
            usuario_id=usuario_id,
            acao="consentimento_registrado",
            detalhes={
                "tipo": tipo_consentimento,
                "consentido": consentido,
                "versao_politica": versao_politica,
                "ip": ip_address,
                "user_agent": user_agent,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        
        # Atualizar metadata do usuário
        result = await db.execute(
            select(Usuario).where(Usuario.id == usuario_id)
        )
        usuario = result.scalar_one_or_none()
        
        if usuario:
            consentimentos = usuario.config or {}
            if "consentimentos" not in consentimentos:
                consentimentos["consentimentos"] = {}
            
            consentimentos["consentimentos"][tipo_consentimento] = {
                "consentido": consentido,
                "versao": versao_politica,
                "data": datetime.utcnow().isoformat(),
            }
            
            await db.execute(
                update(Usuario)
                .where(Usuario.id == usuario_id)
                .values(config=consentimentos)
            )
    
    async def verificar_consentimento(
        self,
        db: AsyncSession,
        usuario_id: UUID,
        tipo_consentimento: str,
    ) -> bool:
        """Verifica se usuário deu consentimento específico."""
        result = await db.execute(
            select(Usuario.config).where(Usuario.id == usuario_id)
        )
        config = result.scalar_one_or_none()
        
        if not config:
            return False
        
        consentimentos = config.get("consentimentos", {})
        info = consentimentos.get(tipo_consentimento, {})
        
        return info.get("consentido", False)
    
    # =========================================================================
    # Direito de Acesso (Art. 18, II)
    # =========================================================================
    
    async def exportar_dados_usuario(
        self,
        db: AsyncSession,
        usuario_id: UUID,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """
        Exporta todos os dados do usuário em formato estruturado.
        
        Para atender ao direito de acesso e portabilidade.
        """
        dados: dict[str, Any] = {
            "exportado_em": datetime.utcnow().isoformat(),
            "versao_formato": "1.0",
        }
        
        # Dados pessoais
        result = await db.execute(
            select(Usuario).where(
                Usuario.id == usuario_id,
                Usuario.tenant_id == tenant_id,
            )
        )
        usuario = result.scalar_one_or_none()
        
        if not usuario:
            raise ValueError("Usuário não encontrado")
        
        dados["dados_pessoais"] = {
            "nome": usuario.nome,
            "email": usuario.email,
            "cpf": usuario.cpf,
            "telefone": usuario.telefone,
            "matricula": usuario.matricula,
            "cargo": usuario.cargo,
            "departamento": usuario.departamento,
            "data_admissao": usuario.data_admissao.isoformat() if usuario.data_admissao else None,
            "criado_em": usuario.created_at.isoformat() if usuario.created_at else None,
        }
        
        # Marcações de ponto
        result = await db.execute(
            select(MarcacaoPonto)
            .where(
                MarcacaoPonto.usuario_id == usuario_id,
                MarcacaoPonto.tenant_id == tenant_id,
            )
            .order_by(MarcacaoPonto.timestamp_local.desc())
            .limit(10000)  # Limitar para não estourar memória
        )
        marcacoes = result.scalars().all()
        
        dados["marcacoes_ponto"] = [
            {
                "id": str(m.id),
                "evento": m.evento.value,
                "data_hora": m.timestamp_local.isoformat(),
                "latitude": str(m.latitude) if m.latitude else None,
                "longitude": str(m.longitude) if m.longitude else None,
                "tipo": m.tipo.value,
                "status": m.status.value,
            }
            for m in marcacoes
        ]
        
        # Documentos
        result = await db.execute(
            select(Documento)
            .where(
                Documento.usuario_id == usuario_id,
                Documento.tenant_id == tenant_id,
            )
            .order_by(Documento.created_at.desc())
        )
        documentos = result.scalars().all()
        
        dados["documentos"] = [
            {
                "id": str(d.id),
                "tipo": d.tipo.value,
                "nome": d.nome,
                "descricao": d.descricao,
                "criado_em": d.created_at.isoformat() if d.created_at else None,
            }
            for d in documentos
        ]
        
        # Carteiras de benefícios
        result = await db.execute(
            select(BeneficioCarteira)
            .where(
                BeneficioCarteira.usuario_id == usuario_id,
                BeneficioCarteira.tenant_id == tenant_id,
            )
        )
        carteiras = result.scalars().all()
        
        dados["beneficios"] = [
            {
                "id": str(c.id),
                "tipo": c.tipo.value,
                "nome": c.nome,
                "saldo": str(c.saldo),
            }
            for c in carteiras
        ]
        
        # Transações
        carteira_ids = [c.id for c in carteiras]
        if carteira_ids:
            result = await db.execute(
                select(Transacao)
                .where(Transacao.carteira_id.in_(carteira_ids))
                .order_by(Transacao.created_at.desc())
                .limit(1000)
            )
            transacoes = result.scalars().all()
            
            dados["transacoes"] = [
                {
                    "id": str(t.id),
                    "tipo": t.tipo.value,
                    "valor": str(t.valor),
                    "descricao": t.descricao,
                    "data": t.created_at.isoformat() if t.created_at else None,
                }
                for t in transacoes
            ]
        else:
            dados["transacoes"] = []
        
        # Log desta exportação
        await self._log_auditoria(
            db=db,
            usuario_id=usuario_id,
            acao="dados_exportados",
            detalhes={"tipo": "exportacao_completa"},
        )
        
        return dados
    
    # =========================================================================
    # Direito de Exclusão / Anonimização (Art. 18, VI)
    # =========================================================================
    
    async def anonimizar_usuario(
        self,
        db: AsyncSession,
        usuario_id: UUID,
        tenant_id: UUID,
        solicitante_id: UUID,
    ) -> dict[str, Any]:
        """
        Anonimiza dados do usuário.
        
        Mantém registros necessários para compliance trabalhista,
        mas remove dados identificáveis.
        """
        result = await db.execute(
            select(Usuario).where(
                Usuario.id == usuario_id,
                Usuario.tenant_id == tenant_id,
            )
        )
        usuario = result.scalar_one_or_none()
        
        if not usuario:
            raise ValueError("Usuário não encontrado")
        
        # Gerar hash para pseudo-anonimização
        hash_id = hashlib.sha256(str(usuario_id).encode()).hexdigest()[:12]
        
        # Anonimizar dados pessoais
        dados_originais = {
            "nome": usuario.nome,
            "email": usuario.email,
            "cpf": usuario.cpf,
            "telefone": usuario.telefone,
        }
        
        await db.execute(
            update(Usuario)
            .where(Usuario.id == usuario_id)
            .values(
                nome=f"Usuário Anonimizado #{hash_id}",
                email=f"anonimo_{hash_id}@anonimizado.lgpd",
                cpf=f"***.***.***-{hash_id[:2]}",
                telefone=None,
                foto_url=None,
                face_encoding=None,
                mfa_secret=None,
                mfa_enabled=False,
                status=UserStatus.INACTIVE,
                config={"anonimizado": True, "data_anonimizacao": datetime.utcnow().isoformat()},
            )
        )
        
        # Anonimizar documentos (manter registro, remover arquivo)
        await db.execute(
            update(Documento)
            .where(
                Documento.usuario_id == usuario_id,
                Documento.tenant_id == tenant_id,
            )
            .values(
                storage_path=None,
                nome=f"Documento Anonimizado",
            )
        )
        
        # Manter marcações (obrigação trabalhista) mas remover evidências
        await db.execute(
            update(MarcacaoPonto)
            .where(
                MarcacaoPonto.usuario_id == usuario_id,
                MarcacaoPonto.tenant_id == tenant_id,
            )
            .values(
                foto_url=None,
                evidencias=None,
            )
        )
        
        # Log da anonimização
        await self._log_auditoria(
            db=db,
            usuario_id=solicitante_id,
            acao="usuario_anonimizado",
            detalhes={
                "usuario_anonimizado": str(usuario_id),
                "hash_referencia": hash_id,
            },
        )
        
        return {
            "sucesso": True,
            "hash_referencia": hash_id,
            "dados_anonimizados": list(dados_originais.keys()),
        }
    
    # =========================================================================
    # Retenção de Dados
    # =========================================================================
    
    async def executar_politica_retencao(
        self,
        db: AsyncSession,
        tenant_id: UUID,
    ) -> dict[str, int]:
        """
        Executa política de retenção de dados.
        
        Remove/anonimiza dados que excedem o período de retenção.
        """
        contadores = {
            "audit_logs_removidos": 0,
            "marcacoes_arquivadas": 0,
            "documentos_removidos": 0,
        }
        
        # Audit logs: manter por 3 anos (36 meses)
        data_limite_logs = datetime.utcnow() - timedelta(days=settings.audit_log_retention_months * 30)
        
        result = await db.execute(
            delete(AuditLog).where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.created_at < data_limite_logs,
            )
        )
        contadores["audit_logs_removidos"] = result.rowcount
        
        # Marcações: manter por 5 anos (Portaria 671)
        data_limite_ponto = datetime.utcnow() - timedelta(days=settings.data_retention_years * 365)
        
        # Apenas arquivar (mover para cold storage), não deletar
        # Em produção, mover para tabela de arquivo ou S3 Glacier
        result = await db.execute(
            select(MarcacaoPonto)
            .where(
                MarcacaoPonto.tenant_id == tenant_id,
                MarcacaoPonto.timestamp_local < data_limite_ponto,
            )
        )
        marcacoes_antigas = result.scalars().all()
        contadores["marcacoes_arquivadas"] = len(marcacoes_antigas)
        
        logger.info(
            f"Política de retenção executada para tenant {tenant_id}: {contadores}"
        )
        
        return contadores
    
    # =========================================================================
    # Auditoria
    # =========================================================================
    
    async def _log_auditoria(
        self,
        db: AsyncSession,
        usuario_id: UUID,
        acao: str,
        detalhes: dict[str, Any],
    ) -> None:
        """Registra ação no log de auditoria."""
        result = await db.execute(
            select(Usuario.tenant_id).where(Usuario.id == usuario_id)
        )
        tenant_id = result.scalar_one_or_none()
        
        if tenant_id:
            log = AuditLog(
                tenant_id=tenant_id,
                usuario_id=usuario_id,
                acao=acao,
                entidade_tipo="lgpd",
                detalhes=detalhes,
            )
            db.add(log)
    
    async def listar_logs_auditoria(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        usuario_id: Optional[UUID] = None,
        acao: Optional[str] = None,
        data_inicio: Optional[datetime] = None,
        data_fim: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[AuditLog], int]:
        """Lista logs de auditoria com filtros."""
        query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
        
        if usuario_id:
            query = query.where(AuditLog.usuario_id == usuario_id)
        if acao:
            query = query.where(AuditLog.acao == acao)
        if data_inicio:
            query = query.where(AuditLog.created_at >= data_inicio)
        if data_fim:
            query = query.where(AuditLog.created_at <= data_fim)
        
        # Contar total
        from sqlalchemy import func
        
        count_query = select(func.count()).select_from(query.subquery())
        result = await db.execute(count_query)
        total = result.scalar() or 0
        
        # Buscar página
        query = query.order_by(AuditLog.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        return list(logs), total
    
    # =========================================================================
    # Relatório LGPD
    # =========================================================================
    
    async def gerar_relatorio_compliance(
        self,
        db: AsyncSession,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """
        Gera relatório de compliance LGPD para o tenant.
        """
        from sqlalchemy import func
        
        # Contadores
        result = await db.execute(
            select(func.count()).select_from(Usuario).where(
                Usuario.tenant_id == tenant_id,
                Usuario.status == UserStatus.ACTIVE,
            )
        )
        total_usuarios_ativos = result.scalar() or 0
        
        result = await db.execute(
            select(func.count()).select_from(Usuario).where(
                Usuario.tenant_id == tenant_id,
                Usuario.config.contains({"anonimizado": True}),
            )
        )
        total_anonimizados = result.scalar() or 0
        
        result = await db.execute(
            select(func.count()).select_from(MarcacaoPonto).where(
                MarcacaoPonto.tenant_id == tenant_id,
            )
        )
        total_marcacoes = result.scalar() or 0
        
        result = await db.execute(
            select(func.count()).select_from(Documento).where(
                Documento.tenant_id == tenant_id,
            )
        )
        total_documentos = result.scalar() or 0
        
        # Últimas ações LGPD
        result = await db.execute(
            select(AuditLog)
            .where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.entidade_tipo == "lgpd",
            )
            .order_by(AuditLog.created_at.desc())
            .limit(10)
        )
        ultimas_acoes = result.scalars().all()
        
        return {
            "gerado_em": datetime.utcnow().isoformat(),
            "tenant_id": str(tenant_id),
            "estatisticas": {
                "usuarios_ativos": total_usuarios_ativos,
                "usuarios_anonimizados": total_anonimizados,
                "marcacoes_armazenadas": total_marcacoes,
                "documentos_armazenados": total_documentos,
            },
            "politica_retencao": {
                "dados_ponto_anos": settings.data_retention_years,
                "audit_logs_meses": settings.audit_log_retention_months,
            },
            "ultimas_acoes_lgpd": [
                {
                    "acao": log.acao,
                    "data": log.created_at.isoformat() if log.created_at else None,
                    "detalhes": log.detalhes,
                }
                for log in ultimas_acoes
            ],
        }


# Singleton
lgpd_service = LGPDService()
