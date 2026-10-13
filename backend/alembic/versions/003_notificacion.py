"""003 notificacion + plantilla: canal WhatsApp con garantia sin-PHI (C-06, D-08).

Verificado al inicio del apply: head seguia en 002_turno (C-08 aun no genero
ningun 003_*), asi que este archivo es 003_notificacion.py con
down_revision='002_turno'. Si C-08 hubiese ocupado el 003, este archivo se
renombraria a 004_notificacion.py apuntando al head real (contenido igual:
las tablas no se tocan entre si).
Reversible: downgrade elimina seed + tablas (sin datos reales en v1.0).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "003_notificacion"
down_revision: Union[str, None] = "002_turno"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CANALES = ("whatsapp", "email", "sms")
PLANTILLAS = (
    "recordatorio_48h",
    "recordatorio_24h",
    "confirmacion",
    "hueco_liberado",
    "resena_google",
    "oferta_lista_espera",  # reservada para C-07 (fila seed, sin migrar)
)
ESTADOS = ("encolada", "enviada", "entregada", "leída", "fallida")


def upgrade() -> None:
    op.create_table(
        "plantilla",
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("cuerpo", sa.Text(), nullable=False),
        sa.Column("variables", JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("nombre", "version", name="pk_plantilla"),
    )
    op.create_table(
        "notificacion",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("turno_id", sa.BigInteger(), nullable=False),
        sa.Column("canal", sa.Text(), nullable=False),
        sa.Column("plantilla", sa.Text(), nullable=False),
        sa.Column("destinatario_ref", sa.Text(), nullable=True),
        sa.Column(
            "estado", sa.Text(), server_default="encolada", nullable=False
        ),
        sa.Column("costo", sa.Numeric(10, 3), nullable=True),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("intentos", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ultimo_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "canal IN ('whatsapp', 'email', 'sms')",
            name="ck_notificacion_canal_catalogo",
        ),
        sa.CheckConstraint(
            "plantilla IN ('recordatorio_48h', 'recordatorio_24h', 'confirmacion',"
            " 'hueco_liberado', 'resena_google', 'oferta_lista_espera')",
            name="ck_notificacion_plantilla_catalogo",
        ),
        sa.CheckConstraint(
            "estado IN ('encolada', 'enviada', 'entregada', 'leída', 'fallida')",
            name="ck_notificacion_estado_catalogo",
        ),
        sa.ForeignKeyConstraint(["turno_id"], ["turno.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_notificacion_turno", "notificacion", ["turno_id"])
    op.create_index("ix_notificacion_estado", "notificacion", ["estado"])
    # D-01: segunda barrera de idempotencia (la primera es Redis SET NX EX).
    op.create_index(
        "uq_notificacion_turno_plantilla_activa",
        "notificacion",
        ["turno_id", "plantilla"],
        unique=True,
        postgresql_where=sa.text("estado != 'fallida'"),
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_notificacion_turno_plantilla_activa")
    op.execute("DROP INDEX IF EXISTS ix_notificacion_estado")
    op.execute("DROP INDEX IF EXISTS ix_notificacion_turno")
    op.execute("DROP TABLE IF EXISTS notificacion")
    op.execute("DROP TABLE IF EXISTS plantilla")
