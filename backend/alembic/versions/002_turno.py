"""002 turno agenda core: tabla turno + doble EXCLUDE parcial (C-04, D-01).

Choque imposible por profesional y por sillon a nivel DB; solo participan
turnos activos no-sobreturno (cancelado/ausente liberan hueco). Columna
token_confirmacion_hash reservada NULL (flujo token es C-05, D-05).
Reversible: downgrade elimina la tabla (y sus constraints).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_turno"
down_revision: Union[str, None] = "001_core_identidad_pacientes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ESTADOS = ("pendiente", "confirmado", "asistido", "ausente", "cancelado")
ORIGENES = ("secretaria", "online", "lista_espera")


def upgrade() -> None:
    op.create_table(
        "turno",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("profesional_id", sa.BigInteger(), nullable=False),
        sa.Column("sillon_id", sa.BigInteger(), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "estado",
            sa.Text(),
            server_default="pendiente",
            nullable=False,
        ),
        sa.Column(
            "origen",
            sa.Text(),
            server_default="secretaria",
            nullable=False,
        ),
        sa.Column("token_confirmacion_hash", sa.Text(), nullable=True),
        sa.Column(
            "sobre_turno", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("motivo_sobreturno", sa.Text(), nullable=True),
        sa.Column("motivo_cancelacion", sa.Text(), nullable=True),
        sa.Column("creado_por", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("fin > inicio", name="ck_turno_fin_mayor_inicio"),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'confirmado', 'asistido', 'ausente', 'cancelado')",
            name="ck_turno_estado_catalogo",
        ),
        sa.CheckConstraint(
            "origen IN ('secretaria', 'online', 'lista_espera')",
            name="ck_turno_origen_catalogo",
        ),
        sa.ForeignKeyConstraint(["paciente_id"], ["paciente.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["profesional_id"], ["profesional.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["sillon_id"], ["sillon.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["creado_por"], ["usuario.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_turno_profesional_inicio", "turno", ["profesional_id", "inicio"])
    op.create_index("ix_turno_sillon_inicio", "turno", ["sillon_id", "inicio"])
    op.create_index("ix_turno_estado", "turno", ["estado"])
    op.create_index(
        "ix_turno_token_hash",
        "turno",
        ["token_confirmacion_hash"],
        postgresql_where=sa.text("token_confirmacion_hash IS NOT NULL"),
    )
    # D-01: doble EXCLUDE parcial (requiere btree_gist, habilitado en C-01).
    op.execute(
        "ALTER TABLE turno ADD CONSTRAINT ex_turno_prof_sin_solape "
        "EXCLUDE USING gist (profesional_id WITH =, tstzrange(inicio, fin) WITH &&) "
        "WHERE (sobre_turno IS FALSE AND estado IN ('pendiente','confirmado','asistido'))"
    )
    op.execute(
        "ALTER TABLE turno ADD CONSTRAINT ex_turno_sillon_sin_solape "
        "EXCLUDE USING gist (sillon_id WITH =, tstzrange(inicio, fin) WITH &&) "
        "WHERE (sobre_turno IS FALSE AND estado IN ('pendiente','confirmado','asistido'))"
    )


def downgrade() -> None:
    # Tolerante (fix verify C-04): la tabla pudo venir de metadata/legacy
    # sin estos indices; IF EXISTS evita "index does not exist".
    op.execute("DROP INDEX IF EXISTS ix_turno_token_hash")
    op.execute("DROP INDEX IF EXISTS ix_turno_estado")
    op.execute("DROP INDEX IF EXISTS ix_turno_sillon_inicio")
    op.execute("DROP INDEX IF EXISTS ix_turno_profesional_inicio")
    op.execute("DROP TABLE IF EXISTS turno")
