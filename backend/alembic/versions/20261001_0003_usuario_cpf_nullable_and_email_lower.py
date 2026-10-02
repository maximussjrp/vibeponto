"""usuario cpf nullable and lower email unique index

Revision ID: 20261001_0003
Revises: 20260930_0002
Create Date: 2026-10-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20261001_0003"
down_revision = "20260930_0002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    
    # 1. Pre-check for email case-insensitive collisions within the same tenant
    collision_check = bind.execute(sa.text("""
        SELECT tenant_id, LOWER(email) as lower_email, COUNT(*) as cnt 
        FROM usuarios 
        GROUP BY tenant_id, LOWER(email) 
        HAVING COUNT(*) > 1
    """)).fetchall()

    if collision_check:
        collisions_desc = ", ".join(f"Tenant {row[0]}: {row[1]} ({row[2]} ocorrências)" for row in collision_check)
        raise RuntimeError(f"Conflito de e-mails duplicados em caixa variante detectado: {collisions_desc}. Migração abortada para evitar perda de dados.")

    # 2. Make cpf nullable on usuarios table
    op.alter_column("usuarios", "cpf", existing_type=sa.String(14), nullable=True)

    # 3. Clean up placeholder CPFs ('00000000000') to NULL
    bind.execute(sa.text("UPDATE usuarios SET cpf = NULL WHERE cpf = '00000000000'"))

    # 4. Normalize existing emails to lowercase
    bind.execute(sa.text("UPDATE usuarios SET email = LOWER(email)"))

    # 5. Create lower(email) unique index per tenant if not exists
    dialect_name = bind.dialect.name
    if dialect_name == "postgresql":
        op.create_index(
            "uq_usuario_tenant_email_lower",
            "usuarios",
            ["tenant_id", sa.text("LOWER(email)")],
            unique=True,
            if_not_exists=True
        )

def downgrade() -> None:
    bind = op.get_bind()

    # 1. Pre-check: count usuarios with null CPF BEFORE making schema changes
    null_cpfs = bind.execute(sa.text("SELECT COUNT(*) FROM usuarios WHERE cpf IS NULL")).scalar()
    if null_cpfs and null_cpfs > 0:
        raise RuntimeError(
            f"Impossível reverter migração {revision}: existem {null_cpfs} usuário(s) com CPF nulo no banco. "
            "Preencha os CPFs antes de prosseguir com o downgrade."
        )

    # 2. Drop unique lower email index
    dialect_name = bind.dialect.name
    if dialect_name == "postgresql":
        op.drop_index("uq_usuario_tenant_email_lower", table_name="usuarios", if_exists=True)

    # 3. Restore NOT NULL constraint on cpf column
    op.alter_column("usuarios", "cpf", existing_type=sa.String(14), nullable=False)

