"""Modelos do banco de dados - Entidades principais."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


# ============================================================================
# ENUMS
# ============================================================================

class UserRole(str, Enum):
    """Papéis de usuário no sistema."""
    ADMIN_DP = "admin_dp"
    GESTOR = "gestor"
    COLABORADOR = "colaborador"
    AUDITOR = "auditor"
    FINANCEIRO = "financeiro"


class UserStatus(str, Enum):
    """Status do usuário."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class MarcacaoTipo(str, Enum):
    """Tipo de marcação de ponto."""
    FOTO = "foto"
    FACIAL = "facial"
    QR_CODE = "qr_code"
    MATRICULA = "matricula"
    WHATSAPP = "whatsapp"
    WEB = "web"


class MarcacaoEvento(str, Enum):
    """Evento da marcação."""
    ENTRADA = "entrada"
    PAUSA_INICIO = "pausa_inicio"
    PAUSA_FIM = "pausa_fim"
    SAIDA = "saida"


class MarcacaoStatus(str, Enum):
    """Status da marcação."""
    PENDENTE = "pendente"
    PROCESSADO = "processado"
    SUSPEITA = "suspeita"
    CORRIGIDO = "corrigido"
    REJEITADO = "rejeitado"


class AuditoriaDecisao(str, Enum):
    """Decisão da auditoria."""
    APROVADA = "aprovada"
    REPROVADA = "reprovada"
    REVISAO = "revisao"


class DocumentoTipo(str, Enum):
    """Tipo de documento."""
    HOLERITE = "holerite"
    RECIBO_FERIAS = "recibo_ferias"
    RECIBO_13 = "recibo_13"
    INFORME_RENDIMENTOS = "informe_rendimentos"
    CONTRATO = "contrato"
    OUTRO = "outro"


class AssinaturaMetodo(str, Enum):
    """Método de assinatura."""
    ESIGN = "esign"
    ICP_BRASIL = "icp_brasil"


class AssinaturaStatus(str, Enum):
    """Status da assinatura."""
    PENDENTE = "pendente"
    ASSINADO = "assinado"
    RECUSADO = "recusado"
    EXPIRADO = "expirado"


class BeneficioTipo(str, Enum):
    """Tipo de benefício."""
    VA = "va"  # Vale Alimentação
    VR = "vr"  # Vale Refeição
    VT = "vt"  # Vale Transporte
    CULTURA = "cultura"
    SAUDE = "saude"
    EDUCACAO = "educacao"
    FLEX = "flex"


class CartaoStatus(str, Enum):
    """Status do cartão."""
    ATIVO = "ativo"
    BLOQUEADO = "bloqueado"
    CANCELADO = "cancelado"
    PENDENTE = "pendente"


class EscalaRegime(str, Enum):
    """Regime de escala."""
    FIXO = "fixo"
    FLEX = "flex"
    TURNO_12X36 = "12x36"
    TURNO_6X1 = "6x1"
    PERSONALIZADO = "personalizado"


class DispositivoTipo(str, Enum):
    """Tipo de dispositivo."""
    MOBILE = "mobile"
    TABLET = "tablet"
    WEB = "web"
    KIOSK = "kiosk"


class NotificacaoCanal(str, Enum):
    """Canal de notificação."""
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    WHATSAPP = "whatsapp"


class WebhookEvento(str, Enum):
    """Eventos de webhook."""
    PONTO_MARCADO = "ponto.marcado"
    PONTO_SUSPEITA = "ponto.suspeita"
    DOCUMENTO_ASSINADO = "documento.assinado"
    BENEFICIO_RECARGA = "beneficio.recarga.concluida"
    INTEGRACAO_EXPORT = "integracao.folha.exportado"


# ============================================================================
# MODELOS BASE
# ============================================================================

class TimestampMixin:
    """Mixin para campos de timestamp."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================================
# TENANT (Multi-tenant)
# ============================================================================

class Tenant(Base, TimestampMixin):
    """Tenant - Empresa/Organização."""
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    cnpj: Mapped[str] = mapped_column(String(18), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    telefone: Mapped[Optional[str]] = mapped_column(String(20))
    endereco: Mapped[Optional[dict]] = mapped_column(JSONB)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relacionamentos
    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="tenant")
    equipes: Mapped[list["Equipe"]] = relationship(back_populates="tenant")


# ============================================================================
# USUÁRIO
# ============================================================================

class Usuario(Base, TimestampMixin):
    """Usuário do sistema."""
    __tablename__ = "usuarios"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_usuario_tenant_email"),
        UniqueConstraint("tenant_id", "cpf", name="uq_usuario_tenant_cpf"),
        UniqueConstraint("tenant_id", "matricula", name="uq_usuario_tenant_matricula"),
        Index("ix_usuarios_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    
    # Dados pessoais
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    cpf: Mapped[str] = mapped_column(String(14), nullable=False)
    telefone: Mapped[Optional[str]] = mapped_column(String(20))
    matricula: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Autenticação
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    mfa_secret: Mapped[Optional[str]] = mapped_column(Text)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_last_totp_step: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Status e papel
    papel: Mapped[UserRole] = mapped_column(String(20), default=UserRole.COLABORADOR)
    status: Mapped[UserStatus] = mapped_column(String(20), default=UserStatus.PENDING)
    
    # Biometria (template facial)
    foto_base_url: Mapped[Optional[str]] = mapped_column(String(500))
    face_encoding: Mapped[Optional[bytes]] = mapped_column()  # Para comparação facial
    
    # Equipe
    equipe_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("equipes.id")
    )
    
    # Metadados
    ultimo_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relacionamentos
    tenant: Mapped["Tenant"] = relationship(back_populates="usuarios")
    equipe: Mapped[Optional["Equipe"]] = relationship(back_populates="membros")
    marcacoes: Mapped[list["MarcacaoPonto"]] = relationship(back_populates="usuario")
    documentos: Mapped[list["Documento"]] = relationship(back_populates="usuario")
    carteiras: Mapped[list["BeneficioCarteira"]] = relationship(back_populates="usuario")
    dispositivos: Mapped[list["Dispositivo"]] = relationship(back_populates="usuario")


# ============================================================================
# EQUIPE
# ============================================================================

class Equipe(Base, TimestampMixin):
    """Equipe/Time."""
    __tablename__ = "equipes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(Text)
    lider_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relacionamentos
    tenant: Mapped["Tenant"] = relationship(back_populates="equipes")
    membros: Mapped[list["Usuario"]] = relationship(back_populates="equipe")
    perimetros: Mapped[list["Perimetro"]] = relationship(back_populates="equipe")
    escalas: Mapped[list["Escala"]] = relationship(back_populates="equipe")


# ============================================================================
# PERÍMETRO (Geofencing)
# ============================================================================

class Perimetro(Base, TimestampMixin):
    """Perímetro para geofencing."""
    __tablename__ = "perimetros"
    __table_args__ = (
        Index("ix_perimetros_geom", "geom", postgresql_using="gist"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(Text)
    
    # Pode ser associado a usuário ou equipe
    usuario_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("usuarios.id")
    )
    equipe_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("equipes.id")
    )
    
    # Geometria (polígono ou ponto + raio)
    geom = mapped_column(Geometry("POLYGON", srid=4326))
    centro_lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 8))
    centro_lng: Mapped[Optional[Decimal]] = mapped_column(Numeric(11, 8))
    raio_metros: Mapped[Optional[int]] = mapped_column(Integer, default=100)
    
    # Tolerâncias
    tolerancia_metros: Mapped[int] = mapped_column(Integer, default=50)
    tolerancia_minutos: Mapped[int] = mapped_column(Integer, default=5)
    
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relacionamentos
    equipe: Mapped[Optional["Equipe"]] = relationship(back_populates="perimetros")


# ============================================================================
# ESCALA
# ============================================================================

class Escala(Base, TimestampMixin):
    """Escala de trabalho."""
    __tablename__ = "escalas"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Pode ser associado a usuário ou equipe
    usuario_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("usuarios.id")
    )
    equipe_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("equipes.id")
    )
    
    regime: Mapped[EscalaRegime] = mapped_column(String(20), default=EscalaRegime.FIXO)
    
    # Janelas de trabalho (JSON com dias e horários)
    janelas: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Exemplo: {"seg": {"entrada": "08:00", "saida": "17:00", "pausa": 60}, ...}
    
    # Pausas remuneradas
    pausas_remuneradas: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Regras de HE e Banco de Horas
    regras_he: Mapped[Optional[dict]] = mapped_column(JSONB)
    regras_banco_horas: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Tolerâncias
    tolerancia_entrada_min: Mapped[int] = mapped_column(Integer, default=10)
    tolerancia_saida_min: Mapped[int] = mapped_column(Integer, default=10)
    
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    vigencia_inicio: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    vigencia_fim: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relacionamentos
    equipe: Mapped[Optional["Equipe"]] = relationship(back_populates="escalas")


# ============================================================================
# DISPOSITIVO
# ============================================================================

class Dispositivo(Base, TimestampMixin):
    """Dispositivo registrado."""
    __tablename__ = "dispositivos"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    usuario_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("usuarios.id")
    )
    
    tipo: Mapped[DispositivoTipo] = mapped_column(String(20))
    nome: Mapped[str] = mapped_column(String(255))
    plataforma: Mapped[Optional[str]] = mapped_column(String(50))  # iOS, Android, Web
    versao_app: Mapped[Optional[str]] = mapped_column(String(20))
    versao_os: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Identificadores
    device_id: Mapped[str] = mapped_column(String(255), unique=True)
    push_token: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Attestation (integridade do dispositivo)
    attestation_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    is_rooted: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Status
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    ultimo_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relacionamentos
    usuario: Mapped[Optional["Usuario"]] = relationship(back_populates="dispositivos")


# ============================================================================
# MARCAÇÃO DE PONTO
# ============================================================================

class MarcacaoPonto(Base, TimestampMixin):
    """Marcação de ponto."""
    __tablename__ = "marcacoes_ponto"
    __table_args__ = (
        Index("ix_marcacoes_usuario_ts", "usuario_id", "timestamp_servidor"),
        Index("ix_marcacoes_status", "status"),
        Index("ix_marcacoes_suspeita", "suspeita"),
        Index("ix_marcacoes_geom", "geom", postgresql_using="gist"),
        Index(
            "uq_marcacoes_offline_sync",
            "tenant_id",
            "usuario_id",
            "sync_id",
            unique=True,
            postgresql_where=text("sync_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    usuario_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    dispositivo_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("dispositivos.id")
    )
    perimetro_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("perimetros.id")
    )
    
    # Tipo e evento
    tipo: Mapped[MarcacaoTipo] = mapped_column(String(20), nullable=False)
    evento: Mapped[MarcacaoEvento] = mapped_column(String(20), nullable=False)
    
    # Timestamps
    timestamp_local: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timestamp_servidor: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(50), default="America/Sao_Paulo")
    
    # Geolocalização
    geom = mapped_column(Geometry("POINT", srid=4326))
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 8))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(11, 8))
    accuracy_metros: Mapped[Optional[int]] = mapped_column(Integer)
    sync_id: Mapped[Optional[str]] = mapped_column(String(128))
    
    # Modo e status
    modo: Mapped[str] = mapped_column(String(10), default="online")  # online/offline
    status: Mapped[MarcacaoStatus] = mapped_column(String(20), default=MarcacaoStatus.PENDENTE)
    suspeita: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Evidências (foto, liveness, device integrity)
    foto_url: Mapped[Optional[str]] = mapped_column(String(500))
    evidencias: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Comprovante
    comprovante_hash: Mapped[Optional[str]] = mapped_column(String(64))
    comprovante_assinatura: Mapped[Optional[str]] = mapped_column(Text)
    
    # Correção
    correcao_solicitada: Mapped[bool] = mapped_column(Boolean, default=False)
    correcao_motivo: Mapped[Optional[str]] = mapped_column(Text)
    correcao_novo_horario: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    correcao_aprovada_por: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    correcao_aprovada_em: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relacionamentos
    usuario: Mapped["Usuario"] = relationship(back_populates="marcacoes")
    auditoria: Mapped[Optional["Auditoria"]] = relationship(back_populates="marcacao")


class MFABackupCode(Base, TimestampMixin):
    """Backup code MFA armazenado apenas como hash e uso unico."""
    __tablename__ = "mfa_backup_codes"
    __table_args__ = (
        Index("ix_mfa_backup_codes_usuario_unused", "usuario_id", "used_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    usuario_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


# ============================================================================
# AUDITORIA (AuditorIA)
# ============================================================================

class Auditoria(Base, TimestampMixin):
    """Resultado da auditoria de marcação."""
    __tablename__ = "auditorias"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    marcacao_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("marcacoes_ponto.id"), unique=True, nullable=False
    )
    
    # Score e decisão
    score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    decisao: Mapped[AuditoriaDecisao] = mapped_column(String(20), nullable=False)
    motivos: Mapped[list] = mapped_column(JSONB, default=list)
    
    # Liveness
    liveness_passed: Mapped[bool] = mapped_column(Boolean, default=True)
    liveness_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    liveness_hints: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Imagens analisadas
    imagens_analisadas: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Revisão humana
    revisado_por: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    revisado_em: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    decisao_revisao: Mapped[Optional[str]] = mapped_column(String(20))
    observacao_revisao: Mapped[Optional[str]] = mapped_column(Text)

    # Relacionamentos
    marcacao: Mapped["MarcacaoPonto"] = relationship(back_populates="auditoria")


# ============================================================================
# DOCUMENTO
# ============================================================================

class Documento(Base, TimestampMixin):
    """Documento trabalhista."""
    __tablename__ = "documentos"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    usuario_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    
    tipo: Mapped[DocumentoTipo] = mapped_column(String(30), nullable=False)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(Text)
    
    # Período de referência
    periodo_referencia: Mapped[Optional[str]] = mapped_column(String(20))  # Ex: "2026-01"
    
    # Arquivo
    arquivo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    arquivo_nome: Mapped[str] = mapped_column(String(255), nullable=False)
    arquivo_tamanho: Mapped[int] = mapped_column(Integer)
    arquivo_hash: Mapped[str] = mapped_column(String(64))
    arquivo_mime: Mapped[str] = mapped_column(String(100))
    
    # Status de assinatura
    requer_assinatura: Mapped[bool] = mapped_column(Boolean, default=True)
    assinatura_status: Mapped[AssinaturaStatus] = mapped_column(
        String(20), default=AssinaturaStatus.PENDENTE
    )
    
    # Metadados
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relacionamentos
    usuario: Mapped["Usuario"] = relationship(back_populates="documentos")
    assinaturas: Mapped[list["Assinatura"]] = relationship(back_populates="documento")


# ============================================================================
# ASSINATURA
# ============================================================================

class Assinatura(Base, TimestampMixin):
    """Assinatura de documento."""
    __tablename__ = "assinaturas"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    documento_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documentos.id"), nullable=False
    )
    usuario_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    
    metodo: Mapped[AssinaturaMetodo] = mapped_column(String(20), nullable=False)
    status: Mapped[AssinaturaStatus] = mapped_column(
        String(20), default=AssinaturaStatus.PENDENTE
    )
    
    # Trilha de evidências
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    geoloc: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Hash e assinatura
    documento_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    assinatura_data: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timestamps
    assinado_em: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expira_em: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relacionamentos
    documento: Mapped["Documento"] = relationship(back_populates="assinaturas")


# ============================================================================
# BENEFÍCIO CARTEIRA
# ============================================================================

class BeneficioCarteira(Base, TimestampMixin):
    """Carteira de benefício."""
    __tablename__ = "beneficio_carteiras"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    usuario_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    
    tipo: Mapped[BeneficioTipo] = mapped_column(String(20), nullable=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    
    saldo: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    saldo_bloqueado: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    
    # Política de uso
    politica: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Ex: {"limite_diario": 100, "categorias": ["alimentacao"], "dias_permitidos": ["seg", "ter"...]}
    
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relacionamentos
    usuario: Mapped["Usuario"] = relationship(back_populates="carteiras")
    cartoes: Mapped[list["Cartao"]] = relationship(back_populates="carteira")
    recargas: Mapped[list["Recarga"]] = relationship(back_populates="carteira")
    transacoes: Mapped[list["Transacao"]] = relationship(back_populates="carteira")


# ============================================================================
# CARTÃO
# ============================================================================

class Cartao(Base, TimestampMixin):
    """Cartão de benefício."""
    __tablename__ = "cartoes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    carteira_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("beneficio_carteiras.id"), nullable=False
    )
    
    emissor: Mapped[str] = mapped_column(String(100), nullable=False)
    numero_mascarado: Mapped[str] = mapped_column(String(20), nullable=False)  # **** **** **** 1234
    
    status: Mapped[CartaoStatus] = mapped_column(String(20), default=CartaoStatus.PENDENTE)
    
    validade: Mapped[Optional[str]] = mapped_column(String(7))  # MM/YYYY
    
    # Metadados do emissor
    external_id: Mapped[Optional[str]] = mapped_column(String(100))
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relacionamentos
    carteira: Mapped["BeneficioCarteira"] = relationship(back_populates="cartoes")


# ============================================================================
# RECARGA
# ============================================================================

class Recarga(Base, TimestampMixin):
    """Recarga de carteira."""
    __tablename__ = "recargas"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    carteira_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("beneficio_carteiras.id"), nullable=False
    )
    
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    taxa: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    
    status: Mapped[str] = mapped_column(String(20), default="pendente")
    # pendente, processando, concluida, falha
    
    lote_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    referencia: Mapped[Optional[str]] = mapped_column(String(100))
    
    processada_em: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    erro_mensagem: Mapped[Optional[str]] = mapped_column(Text)

    # Relacionamentos
    carteira: Mapped["BeneficioCarteira"] = relationship(back_populates="recargas")


# ============================================================================
# TRANSAÇÃO
# ============================================================================

class Transacao(Base, TimestampMixin):
    """Transação de benefício."""
    __tablename__ = "transacoes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    carteira_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("beneficio_carteiras.id"), nullable=False
    )
    
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # credito, debito
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    saldo_anterior: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    saldo_posterior: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    descricao: Mapped[str] = mapped_column(String(255))
    categoria: Mapped[Optional[str]] = mapped_column(String(50))
    estabelecimento: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Referência externa
    external_id: Mapped[Optional[str]] = mapped_column(String(100))
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relacionamentos
    carteira: Mapped["BeneficioCarteira"] = relationship(back_populates="transacoes")


# ============================================================================
# WEBHOOK
# ============================================================================

class Webhook(Base, TimestampMixin):
    """Configuração de webhook."""
    __tablename__ = "webhooks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    
    evento: Mapped[WebhookEvento] = mapped_column(String(50), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    segredo: Mapped[str] = mapped_column(String(100), nullable=False)
    
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    tentativas_max: Mapped[int] = mapped_column(Integer, default=3)
    
    # Estatísticas
    total_entregas: Mapped[int] = mapped_column(Integer, default=0)
    total_sucesso: Mapped[int] = mapped_column(Integer, default=0)
    total_falha: Mapped[int] = mapped_column(Integer, default=0)
    ultima_entrega: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ultimo_status: Mapped[Optional[int]] = mapped_column(Integer)


# ============================================================================
# NOTIFICAÇÃO
# ============================================================================

class Notificacao(Base, TimestampMixin):
    """Notificação."""
    __tablename__ = "notificacoes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    usuario_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("usuarios.id")
    )
    
    canal: Mapped[NotificacaoCanal] = mapped_column(String(20), nullable=False)
    destino: Mapped[str] = mapped_column(String(255), nullable=False)  # email, telefone, device_token
    
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    
    status: Mapped[str] = mapped_column(String(20), default="pendente")
    # pendente, enviado, entregue, falha
    
    enviado_em: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    erro_mensagem: Mapped[Optional[str]] = mapped_column(Text)
    
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB)


# ============================================================================
# AUDIT LOG
# ============================================================================

class AuditLog(Base):
    """Log de auditoria imutável."""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    usuario_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    
    # Ação
    acao: Mapped[str] = mapped_column(String(50), nullable=False)
    # create, update, delete, login, logout, approve, reject, sign, etc.
    
    # Entidade afetada
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    
    # Dados
    dados_antes: Mapped[Optional[dict]] = mapped_column(JSONB)
    dados_depois: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Contexto
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    correlation_id: Mapped[Optional[str]] = mapped_column(String(36))
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
