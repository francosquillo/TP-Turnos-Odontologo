"""009 auditoria de acciones admin (C-12 R3, D-10).

Crea `evento_auditoria` (append-only): actor, accion de un catalogo cerrado, objeto afectado y un
detalle JSONB sin contrasenas ni datos clinicos. Un trigger `BEFORE UPDATE OR DELETE` rechaza
cualquier cambio. Repite a proposito los literales del modelo (la migracion no importa modelos)
y un test los compara. Reversible: el downgrade borra la tabla, su trigger y su funcion.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "009_auditoria_admin"
down_revision: Union[str, None] = "008_obras_sociales"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACCIONES = (
    "usuario_alta",
    "usuario_edicion",
    "usuario_desactivacion",
    "usuario_eliminacion",
    "pacientes_importacion",
    "exportacion_total",
)

FUNCION_AUDITORIA_INMUTABLE_DDL = (
    "CREATE OR REPLACE FUNCTION evento_auditoria_inmutable() RETURNS trigger "
    "LANGUAGE plpgsql AS $$ BEGIN "
    "RAISE EXCEPTION 'el evento de auditoria es inmutable' "
    "USING ERRCODE = 'integrity_constraint_violation'; "
    "END; $$"
)
TRIGGER_AUDITORIA_INMUTABLE_DDL = (
    "CREATE TRIGGER trg_evento_auditoria_inmutable BEFORE UPDATE OR DELETE ON evento_auditoria "
    "FOR EACH ROW EXECUTE FUNCTION evento_auditoria_inmutable()"
)
FUNCION_AUDITORIA_INMUTABLE_DROP = "DROP FUNCTION IF EXISTS evento_auditoria_inmutable()"


def upgrade() -> None:
    acciones_sql = ", ".join(f"'{a}'" for a in ACCIONES)
    op.create_table(
        "evento_auditoria",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("actor_id", sa.BigInteger(), nullable=False),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("objeto_tipo", sa.Text(), nullable=False),
        sa.Column("objeto_id", sa.BigInteger(), nullable=True),
        sa.Column("detalle", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(f"accion IN ({acciones_sql})", name="ck_evento_auditoria_accion"),
        sa.ForeignKeyConstraint(["actor_id"], ["usuario.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_evento_auditoria_created_at", "evento_auditoria", [sa.text("created_at DESC")])
    op.create_index("ix_evento_auditoria_actor_id", "evento_auditoria", ["actor_id"])
    op.execute(FUNCION_AUDITORIA_INMUTABLE_DDL)
    op.execute(TRIGGER_AUDITORIA_INMUTABLE_DDL)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_evento_auditoria_inmutable ON evento_auditoria")
    op.execute("DROP INDEX IF EXISTS ix_evento_auditoria_actor_id")
    op.execute("DROP INDEX IF EXISTS ix_evento_auditoria_created_at")
    op.execute("DROP TABLE IF EXISTS evento_auditoria")
    op.execute(FUNCION_AUDITORIA_INMUTABLE_DROP)
