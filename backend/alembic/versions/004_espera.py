"""004 espera_entry: tabla de lista de espera + CHECKs + índices (C-07, D-01).

Head verificado al inicio del apply: 003_notificacion (C-08 no ocupó 004).
Si C-08 generó 004_* entretanto, renombrar a 005_espera.py con
down_revision al head real; contenido intacto, tablas disjuntas.
Reversible: downgrade elimina tabla + índices (sin datos reales en v1.0).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "004_espera"
down_revision: Union[str, None] = "003_notificacion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "espera_entry",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("profesional_id", sa.BigInteger(), nullable=True),
        sa.Column("especialidad", sa.Text(), nullable=True),
        sa.Column("preferencia_horaria", JSONB(), nullable=True),
        sa.Column(
            "estado", sa.Text(), server_default="activa", nullable=False
        ),
        sa.Column("oferta_expira_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_oferta_hash", sa.Text(), nullable=True),
        sa.Column("oferta_hueco", JSONB(), nullable=True),
        sa.Column("motivo_baja", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "profesional_id IS NOT NULL OR especialidad IS NOT NULL",
            name="ck_espera_destino_presente",
        ),
        sa.CheckConstraint(
            "estado != 'ofrecida' OR (oferta_expira_en IS NOT NULL AND "
            "token_oferta_hash IS NOT NULL)",
            name="ck_espera_ofrecida_exige_vencimiento",
        ),
        sa.CheckConstraint(
            "estado IN ('activa', 'ofrecida', 'convertida', 'vencida')",
            name="ck_espera_estado_catalogo",
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"], ["paciente.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["profesional_id"], ["profesional.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_espera_paciente_id", "espera_entry", ["paciente_id"])
    op.create_index("ix_espera_estado", "espera_entry", ["estado"])
    op.create_index("ix_espera_profesional_id", "espera_entry", ["profesional_id"])
    op.create_index("ix_espera_created_at", "espera_entry", ["created_at"])


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_espera_created_at")
    op.execute("DROP INDEX IF EXISTS ix_espera_profesional_id")
    op.execute("DROP INDEX IF EXISTS ix_espera_estado")
    op.execute("DROP INDEX IF EXISTS ix_espera_paciente_id")
    op.execute("DROP TABLE IF EXISTS espera_entry")
