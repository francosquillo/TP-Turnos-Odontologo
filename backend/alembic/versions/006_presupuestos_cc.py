"""006 presupuestos + cuenta corriente (C-09, D-01, D-02, D-11, D-12).

Crea `presupuesto`, `item_presupuesto`, `cuenta_corriente` y `movimiento`, mas
la funcion y el trigger que vuelven inmutable a `movimiento`. Repite a
proposito los literales del DDL de `modelos/cuenta_corriente.py` (la migracion
no importa modelos) y un test compara ambos.
`movimiento.recibo_id` es BIGINT sin FK: la tabla `recibo` la crea C-10.
Reversible: downgrade elimina tablas, indices y la funcion (solo datos ficticios).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_presupuestos_cc"
down_revision: Union[str, None] = "005_clinica"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ESTADOS = ("borrador", "presentado", "aceptado", "rechazado", "cobrado")
TIPOS = ("cargo", "pago", "ajuste")

FUNCION_INMUTABLE_DDL = (
    "CREATE OR REPLACE FUNCTION movimiento_inmutable() RETURNS trigger "
    "LANGUAGE plpgsql AS $$ BEGIN "
    "RAISE EXCEPTION 'movimiento es inmutable' "
    "USING ERRCODE = 'integrity_constraint_violation'; "
    "END; $$"
)
TRIGGER_INMUTABLE_DDL = (
    "CREATE TRIGGER trg_movimiento_inmutable BEFORE UPDATE OR DELETE ON movimiento "
    "FOR EACH ROW EXECUTE FUNCTION movimiento_inmutable()"
)
FUNCION_INMUTABLE_DROP = "DROP FUNCTION IF EXISTS movimiento_inmutable()"


def _id():
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True)


def _ts(nombre: str, *, default: bool = True, nullable: bool = False):
    if default:
        return sa.Column(
            nombre, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        )
    return sa.Column(nombre, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    estados_sql = ", ".join(f"'{e}'" for e in ESTADOS)
    tipos_sql = ", ".join(f"'{t}'" for t in TIPOS)

    op.create_table(
        "presupuesto",
        _id(),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("profesional_id", sa.BigInteger(), nullable=False),
        sa.Column("estado", sa.Text(), server_default="borrador", nullable=False),
        sa.Column("total", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("motivo_rechazo", sa.Text(), nullable=True),
        _ts("presentado_at", default=False, nullable=True),
        _ts("decidido_at", default=False, nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        _ts("deleted_at", default=False, nullable=True),
        sa.Column("motivo_baja", sa.Text(), nullable=True),
        sa.CheckConstraint(f"estado IN ({estados_sql})", name="ck_presupuesto_estado"),
        sa.CheckConstraint("total >= 0", name="ck_presupuesto_total_no_negativo"),
        sa.CheckConstraint(
            "(estado = 'rechazado') = (motivo_rechazo IS NOT NULL)",
            name="ck_presupuesto_rechazo_con_motivo",
        ),
        sa.CheckConstraint(
            "(deleted_at IS NULL) = (motivo_baja IS NULL)",
            name="ck_presupuesto_baja_con_motivo",
        ),
        sa.CheckConstraint(
            "deleted_at IS NULL OR estado = 'borrador'",
            name="ck_presupuesto_baja_solo_borrador",
        ),
        sa.ForeignKeyConstraint(["paciente_id"], ["paciente.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["profesional_id"], ["profesional.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_presupuesto_paciente_created", "presupuesto",
        ["paciente_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_presupuesto_profesional_id", "presupuesto", ["profesional_id"])

    op.create_table(
        "item_presupuesto",
        _id(),
        sa.Column("presupuesto_id", sa.BigInteger(), nullable=False),
        sa.Column("hallazgo_id", sa.BigInteger(), nullable=False),
        sa.Column("tratamiento_id", sa.BigInteger(), nullable=False),
        sa.Column("cantidad", sa.SmallInteger(), nullable=False),
        sa.Column("precio", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("cantidad BETWEEN 1 AND 99", name="ck_item_cantidad_rango"),
        sa.CheckConstraint("precio >= 0", name="ck_item_precio_no_negativo"),
        sa.UniqueConstraint(
            "presupuesto_id", "hallazgo_id", "tratamiento_id",
            name="uq_item_presupuesto_hallazgo_tratamiento",
        ),
        sa.ForeignKeyConstraint(["presupuesto_id"], ["presupuesto.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["hallazgo_id"], ["hallazgo_odontograma.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tratamiento_id"], ["tratamiento.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_item_presupuesto_hallazgo_id", "item_presupuesto", ["hallazgo_id"])
    op.create_index("ix_item_presupuesto_tratamiento_id", "item_presupuesto", ["tratamiento_id"])

    op.create_table(
        "cuenta_corriente",
        _id(),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        _ts("created_at"),
        sa.UniqueConstraint("paciente_id", name="uq_cuenta_corriente_paciente"),
        sa.ForeignKeyConstraint(["paciente_id"], ["paciente.id"], ondelete="RESTRICT"),
    )

    op.create_table(
        "movimiento",
        _id(),
        sa.Column("cc_id", sa.BigInteger(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("monto", sa.Numeric(16, 2), nullable=False),
        sa.Column("concepto", sa.Text(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("turno_id", sa.BigInteger(), nullable=True),
        sa.Column("presupuesto_id", sa.BigInteger(), nullable=True),
        # Sin FK: `recibo` no existe hasta C-10, que agrega la FK y el indice.
        sa.Column("recibo_id", sa.BigInteger(), nullable=True),
        sa.Column("anula_a_id", sa.BigInteger(), nullable=True),
        sa.Column("creado_por", sa.BigInteger(), nullable=False),
        _ts("created_at"),
        sa.CheckConstraint(f"tipo IN ({tipos_sql})", name="ck_movimiento_tipo"),
        sa.CheckConstraint(
            "(tipo = 'cargo' AND monto > 0) OR (tipo = 'pago' AND monto < 0) "
            "OR (tipo = 'ajuste' AND monto <> 0)",
            name="ck_movimiento_signo",
        ),
        sa.CheckConstraint(
            "anula_a_id IS NULL OR (tipo = 'ajuste' AND motivo IS NOT NULL)",
            name="ck_movimiento_anulacion",
        ),
        sa.ForeignKeyConstraint(["cc_id"], ["cuenta_corriente.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["turno_id"], ["turno.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["presupuesto_id"], ["presupuesto.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["anula_a_id"], ["movimiento.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["creado_por"], ["usuario.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_movimiento_cc_created", "movimiento", ["cc_id", "created_at"])
    op.create_index("ix_movimiento_turno_id", "movimiento", ["turno_id"])
    op.create_index("ix_movimiento_presupuesto_id", "movimiento", ["presupuesto_id"])
    op.create_index("ix_movimiento_creado_por", "movimiento", ["creado_por"])
    op.create_index(
        "uq_movimiento_cargo_presupuesto", "movimiento", ["presupuesto_id"],
        unique=True, postgresql_where=sa.text("tipo = 'cargo'"),
    )
    op.create_index(
        "uq_movimiento_anula_a", "movimiento", ["anula_a_id"],
        unique=True, postgresql_where=sa.text("anula_a_id IS NOT NULL"),
    )

    # Dos sentencias separadas: asyncpg no acepta varias en un execute.
    op.execute(FUNCION_INMUTABLE_DDL)
    op.execute(TRIGGER_INMUTABLE_DDL)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_movimiento_inmutable ON movimiento")
    op.execute("DROP INDEX IF EXISTS uq_movimiento_anula_a")
    op.execute("DROP INDEX IF EXISTS uq_movimiento_cargo_presupuesto")
    op.execute("DROP INDEX IF EXISTS ix_movimiento_creado_por")
    op.execute("DROP INDEX IF EXISTS ix_movimiento_presupuesto_id")
    op.execute("DROP INDEX IF EXISTS ix_movimiento_turno_id")
    op.execute("DROP INDEX IF EXISTS ix_movimiento_cc_created")
    op.execute("DROP TABLE IF EXISTS movimiento")
    op.execute(FUNCION_INMUTABLE_DROP)
    op.execute("DROP TABLE IF EXISTS cuenta_corriente")
    op.execute("DROP INDEX IF EXISTS ix_item_presupuesto_tratamiento_id")
    op.execute("DROP INDEX IF EXISTS ix_item_presupuesto_hallazgo_id")
    op.execute("DROP TABLE IF EXISTS item_presupuesto")
    op.execute("DROP INDEX IF EXISTS ix_presupuesto_profesional_id")
    op.execute("DROP INDEX IF EXISTS ix_presupuesto_paciente_created")
    op.execute("DROP TABLE IF EXISTS presupuesto")
