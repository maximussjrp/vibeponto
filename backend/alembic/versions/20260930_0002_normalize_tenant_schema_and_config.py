"""normalize tenant schema and config structures

Revision ID: 20260930_0002
Revises: 20260917_0001
Create Date: 2026-09-30 00:00:00
"""

import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260930_0002"
down_revision = "20260917_0001"
branch_labels = None
depends_on = None


def normalize_config(cfg: dict) -> dict:
    if not isinstance(cfg, dict):
        cfg = {}

    config = dict(cfg)

    # Ensure sections exist
    ponto = dict(config.get("ponto") or {})
    notificacoes = dict(config.get("notificacoes") or {})
    seguranca = dict(config.get("seguranca") or {})
    integracoes = dict(config.get("integracoes") or {})

    # Migrate legacy root keys into section ponto if not present
    if "jornada_diaria" in config and "jornada_diaria" not in ponto:
        ponto["jornada_diaria"] = config["jornada_diaria"]
    if "tolerancia_minutos" in config and "tolerancia_minutos" not in ponto:
        ponto["tolerancia_minutos"] = config["tolerancia_minutos"]
    if "requer_foto" in config and "exigir_foto" not in ponto:
        ponto["exigir_foto"] = config["requer_foto"]
    if "requer_geolocalizacao" in config and "exigir_geolocalizacao" not in ponto:
        ponto["exigir_geolocalizacao"] = config["requer_geolocalizacao"]
    if "permite_hora_extra" in config and "hora_extra_automatica" not in ponto:
        ponto["hora_extra_automatica"] = config["permite_hora_extra"]

    config["ponto"] = ponto
    config["notificacoes"] = notificacoes
    config["seguranca"] = seguranca
    config["integracoes"] = integracoes

    return config


def upgrade() -> None:
    # 1. Add razao_social column if not exists
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("tenants")]

    if "razao_social" not in columns:
        op.add_column("tenants", sa.Column("razao_social", sa.String(255), nullable=True))

    # 2. Normalize configs for existing tenants
    connection = op.get_bind()
    results = connection.execute(sa.text("SELECT id, config FROM tenants")).fetchall()

    for row in results:
        tenant_id, cfg = row[0], row[1]
        if isinstance(cfg, str):
            try:
                cfg = json.loads(cfg)
            except Exception:
                cfg = {}

        normalized = normalize_config(cfg or {})
        connection.execute(
            sa.text("UPDATE tenants SET config = :config WHERE id = :id"),
            {"config": json.dumps(normalized), "id": tenant_id}
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("tenants")]

    if "razao_social" in columns:
        op.drop_column("tenants", "razao_social")
