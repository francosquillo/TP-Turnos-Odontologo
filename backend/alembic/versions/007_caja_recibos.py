"""007 caja, recibos y movimientos de caja (C-10, D-01, D-02, D-10, D-14, D-15, D-25).

Crea `caja`, `recibo`, `recibo_contador` y `movimiento_caja`, con las funciones y
triggers de inmutabilidad (D-14). Sobre `movimiento` agrega la FK a `recibo`, su indice,
`uq_movimiento_pago_recibo` y `ck_movimiento_pago_con_recibo` (D-15). Repite a proposito
los literales del DDL de `modelos/caja.py` (la migracion no importa modelos) y un test
compara ambos. `ADD CONSTRAINT` no actualiza filas: no dispara el trigger de `movimiento`.
Falla si hay un `pago` sin recibo valido: se prefiere el error a un dato sin recibo.
Reversible: el downgrade quita lo agregado; no revierte estados ni borra pagos porque
`movimiento` es inmutable (datos ficticios).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007_caja_recibos"
down_revision: Union[str, None] = "006_presupuestos_cc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MEDIOS = ("efectivo", "transferencia", "tarjeta_simulada")
ESTADOS_CAJA = ("abierta", "cerrada")
CLAVE_REGEX = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"

FUNCION_MOVCAJA_INMUTABLE_DDL = (
    "CREATE OR REPLACE FUNCTION movimiento_caja_inmutable() RETURNS trigger "
    "LANGUAGE plpgsql AS $$ BEGIN "
    "RAISE EXCEPTION 'movimiento de caja es inmutable' "
    "USING ERRCODE = 'integrity_constraint_violation'; "
    "END; $$"
)
TRIGGER_MOVCAJA_INMUTABLE_DDL = (
    "CREATE TRIGGER trg_movimiento_caja_inmutable BEFORE UPDATE OR DELETE ON movimiento_caja "
    "FOR EACH ROW EXECUTE FUNCTION movimiento_caja_inmutable()"
)
FUNCION_MOVCAJA_INMUTABLE_DROP = "DROP FUNCTION IF EXISTS movimiento_caja_inmutable()"

FUNCION_MOVCAJA_CAJA_ABIERTA_DDL = (
    "CREATE OR REPLACE FUNCTION movimiento_caja_caja_abierta() RETURNS trigger "
    "LANGUAGE plpgsql AS $$ BEGIN "
    "IF (SELECT estado FROM caja WHERE id = NEW.caja_id FOR SHARE) = 'cerrada' THEN "
    "RAISE EXCEPTION 'la caja esta cerrada' "
    "USING ERRCODE = 'integrity_constraint_violation'; "
    "END IF; "
    "RETURN NEW; "
    "END; $$"
)
TRIGGER_MOVCAJA_CAJA_ABIERTA_DDL = (
    "CREATE TRIGGER trg_movimiento_caja_caja_abierta BEFORE INSERT ON movimiento_caja "
    "FOR EACH ROW EXECUTE FUNCTION movimiento_caja_caja_abierta()"
)
FUNCION_MOVCAJA_CAJA_ABIERTA_DROP = "DROP FUNCTION IF EXISTS movimiento_caja_caja_abierta()"

FUNCION_CAJA_PROTEGER_DDL = (
    "CREATE OR REPLACE FUNCTION caja_proteger() RETURNS trigger "
    "LANGUAGE plpgsql AS $$ BEGIN "
    "IF TG_OP = 'DELETE' OR OLD.estado = 'cerrada' THEN "
    "RAISE EXCEPTION 'la caja no se borra y una caja cerrada no se modifica' "
    "USING ERRCODE = 'integrity_constraint_violation'; "
    "END IF; "
    "RETURN NEW; "
    "END; $$"
)
TRIGGER_CAJA_PROTEGER_DDL = (
    "CREATE TRIGGER trg_caja_proteger BEFORE UPDATE OR DELETE ON caja "
    "FOR EACH ROW EXECUTE FUNCTION caja_proteger()"
)
FUNCION_CAJA_PROTEGER_DROP = "DROP FUNCTION IF EXISTS caja_proteger()"

FUNCION_RECIBO_PROTEGER_DDL = (
    "CREATE OR REPLACE FUNCTION recibo_proteger() RETURNS trigger "
    "LANGUAGE plpgsql AS $$ BEGIN "
    "IF TG_OP = 'DELETE' OR OLD.anulado OR NOT NEW.anulado "
    "OR ROW(NEW.id, NEW.numero, NEW.paciente_id, NEW.monto, NEW.medio, NEW.emitido_por, "
    "NEW.clave_idempotencia, NEW.created_at) "
    "IS DISTINCT FROM ROW(OLD.id, OLD.numero, OLD.paciente_id, OLD.monto, OLD.medio, "
    "OLD.emitido_por, OLD.clave_idempotencia, OLD.created_at) THEN "
    "RAISE EXCEPTION 'el recibo es inmutable salvo su anulacion' "
    "USING ERRCODE = 'integrity_constraint_violation'; "
    "END IF; "
    "RETURN NEW; "
    "END; $$"
)
TRIGGER_RECIBO_PROTEGER_DDL = (
    "CREATE TRIGGER trg_recibo_proteger BEFORE UPDATE OR DELETE ON recibo "
    "FOR EACH ROW EXECUTE FUNCTION recibo_proteger()"
)
FUNCION_RECIBO_PROTEGER_DROP = "DROP FUNCTION IF EXISTS recibo_proteger()"


def _id():
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True)


def _created_at():
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    medios_sql = ", ".join(f"'{m}'" for m in MEDIOS)
    estados_sql = ", ".join(f"'{e}'" for e in ESTADOS_CAJA)

    op.create_table(
        "caja",
        _id(),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("abierta_por", sa.BigInteger(), nullable=False),
        sa.Column("estado", sa.Text(), server_default="abierta", nullable=False),
        sa.Column("total_sistema", sa.Numeric(18, 2), nullable=True),
        sa.Column("total_contado", sa.Numeric(18, 2), nullable=True),
        sa.Column("diferencia", sa.Numeric(18, 2), nullable=True),
        sa.Column("motivo_diferencia", sa.Text(), nullable=True),
        sa.Column("cerrada_por", sa.BigInteger(), nullable=True),
        sa.Column("cerrada_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.CheckConstraint(f"estado IN ({estados_sql})", name="ck_caja_estado"),
        sa.CheckConstraint(
            "(estado = 'cerrada' AND total_sistema IS NOT NULL AND total_contado IS NOT NULL "
            "AND diferencia IS NOT NULL AND cerrada_por IS NOT NULL AND cerrada_at IS NOT NULL) "
            "OR (estado = 'abierta' AND total_sistema IS NULL AND total_contado IS NULL "
            "AND diferencia IS NULL AND motivo_diferencia IS NULL AND cerrada_por IS NULL "
            "AND cerrada_at IS NULL)",
            name="ck_caja_cierre_completo",
        ),
        sa.CheckConstraint(
            "diferencia IS NULL OR diferencia = total_contado - total_sistema",
            name="ck_caja_diferencia",
        ),
        sa.CheckConstraint(
            "diferencia IS NULL OR diferencia = 0 OR motivo_diferencia IS NOT NULL",
            name="ck_caja_diferencia_con_motivo",
        ),
        sa.CheckConstraint(
            "total_contado IS NULL OR total_contado >= 0", name="ck_caja_contado_no_negativo"
        ),
        sa.UniqueConstraint("fecha", name="uq_caja_fecha"),
        sa.ForeignKeyConstraint(["abierta_por"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cerrada_por"], ["usuario.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_caja_abierta_por", "caja", ["abierta_por"])
    op.create_index("ix_caja_cerrada_por", "caja", ["cerrada_por"])
    op.create_index(
        "uq_caja_una_abierta", "caja", ["estado"],
        unique=True, postgresql_where=sa.text("estado = 'abierta'"),
    )

    op.create_table(
        "recibo",
        _id(),
        sa.Column("numero", sa.BigInteger(), nullable=False),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("monto", sa.Numeric(16, 2), nullable=False),
        sa.Column("medio", sa.Text(), nullable=False),
        sa.Column("emitido_por", sa.BigInteger(), nullable=False),
        sa.Column("clave_idempotencia", sa.Text(), nullable=False),
        sa.Column("anulado", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("motivo_anulacion", sa.Text(), nullable=True),
        sa.Column("anulado_por", sa.BigInteger(), nullable=True),
        sa.Column("anulado_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.CheckConstraint("monto > 0", name="ck_recibo_monto_positivo"),
        sa.CheckConstraint(f"medio IN ({medios_sql})", name="ck_recibo_medio"),
        sa.CheckConstraint(
            "(anulado AND motivo_anulacion IS NOT NULL AND anulado_por IS NOT NULL "
            "AND anulado_at IS NOT NULL) "
            "OR (NOT anulado AND motivo_anulacion IS NULL AND anulado_por IS NULL "
            "AND anulado_at IS NULL)",
            name="ck_recibo_anulacion",
        ),
        sa.CheckConstraint(
            f"clave_idempotencia ~ '{CLAVE_REGEX}'", name="ck_recibo_clave_formato"
        ),
        sa.UniqueConstraint("numero", name="uq_recibo_numero"),
        sa.UniqueConstraint("clave_idempotencia", name="uq_recibo_clave_idempotencia"),
        sa.ForeignKeyConstraint(["paciente_id"], ["paciente.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["emitido_por"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["anulado_por"], ["usuario.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_recibo_paciente_id", "recibo", ["paciente_id"])
    op.create_index("ix_recibo_emitido_por", "recibo", ["emitido_por"])
    op.create_index("ix_recibo_anulado_por", "recibo", ["anulado_por"])

    op.create_table(
        "recibo_contador",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, primary_key=True),
        sa.Column("ultimo", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_recibo_contador_unico"),
    )

    op.create_table(
        "movimiento_caja",
        _id(),
        sa.Column("caja_id", sa.BigInteger(), nullable=False),
        sa.Column("recibo_id", sa.BigInteger(), nullable=False),
        sa.Column("medio", sa.Text(), nullable=False),
        sa.Column("monto", sa.Numeric(16, 2), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("creado_por", sa.BigInteger(), nullable=False),
        _created_at(),
        sa.CheckConstraint(f"medio IN ({medios_sql})", name="ck_movcaja_medio"),
        sa.CheckConstraint("monto <> 0", name="ck_movcaja_monto_no_cero"),
        sa.CheckConstraint(
            "monto > 0 OR motivo IS NOT NULL", name="ck_movcaja_reversion_con_motivo"
        ),
        sa.ForeignKeyConstraint(["caja_id"], ["caja.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recibo_id"], ["recibo.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["creado_por"], ["usuario.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_movcaja_caja_id", "movimiento_caja", ["caja_id"])
    op.create_index("ix_movcaja_recibo_id", "movimiento_caja", ["recibo_id"])
    op.create_index("ix_movcaja_creado_por", "movimiento_caja", ["creado_por"])
    op.create_index(
        "uq_movcaja_ingreso", "movimiento_caja", ["recibo_id"],
        unique=True, postgresql_where=sa.text("monto > 0"),
    )
    op.create_index(
        "uq_movcaja_reversion", "movimiento_caja", ["recibo_id"],
        unique=True, postgresql_where=sa.text("monto < 0"),
    )

    # Una sentencia por execute: asyncpg no acepta varias.
    for ddl in (
        FUNCION_CAJA_PROTEGER_DDL, TRIGGER_CAJA_PROTEGER_DDL,
        FUNCION_RECIBO_PROTEGER_DDL, TRIGGER_RECIBO_PROTEGER_DDL,
        FUNCION_MOVCAJA_INMUTABLE_DDL, TRIGGER_MOVCAJA_INMUTABLE_DDL,
        FUNCION_MOVCAJA_CAJA_ABIERTA_DDL, TRIGGER_MOVCAJA_CAJA_ABIERTA_DDL,
    ):
        op.execute(ddl)

    # D-15: el pago nace con recibo. Falla si una base local tiene un pago sin recibo valido.
    op.create_foreign_key(
        "fk_movimiento_recibo", "movimiento", "recibo", ["recibo_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_movimiento_recibo_id", "movimiento", ["recibo_id"])
    op.create_index(
        "uq_movimiento_pago_recibo", "movimiento", ["recibo_id"],
        unique=True, postgresql_where=sa.text("tipo = 'pago'"),
    )
    op.create_check_constraint(
        "ck_movimiento_pago_con_recibo", "movimiento",
        "tipo <> 'pago' OR recibo_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_movimiento_pago_con_recibo", "movimiento", type_="check")
    op.execute("DROP INDEX IF EXISTS uq_movimiento_pago_recibo")
    op.execute("DROP INDEX IF EXISTS ix_movimiento_recibo_id")
    op.drop_constraint("fk_movimiento_recibo", "movimiento", type_="foreignkey")

    op.execute("DROP TRIGGER IF EXISTS trg_movimiento_caja_caja_abierta ON movimiento_caja")
    op.execute("DROP TRIGGER IF EXISTS trg_movimiento_caja_inmutable ON movimiento_caja")
    op.execute("DROP TRIGGER IF EXISTS trg_recibo_proteger ON recibo")
    op.execute("DROP TRIGGER IF EXISTS trg_caja_proteger ON caja")

    op.execute("DROP INDEX IF EXISTS uq_movcaja_reversion")
    op.execute("DROP INDEX IF EXISTS uq_movcaja_ingreso")
    op.execute("DROP INDEX IF EXISTS ix_movcaja_creado_por")
    op.execute("DROP INDEX IF EXISTS ix_movcaja_recibo_id")
    op.execute("DROP INDEX IF EXISTS ix_movcaja_caja_id")
    op.execute("DROP TABLE IF EXISTS movimiento_caja")
    op.execute("DROP TABLE IF EXISTS recibo_contador")
    op.execute("DROP INDEX IF EXISTS ix_recibo_anulado_por")
    op.execute("DROP INDEX IF EXISTS ix_recibo_emitido_por")
    op.execute("DROP INDEX IF EXISTS ix_recibo_paciente_id")
    op.execute("DROP TABLE IF EXISTS recibo")
    op.execute("DROP INDEX IF EXISTS uq_caja_una_abierta")
    op.execute("DROP INDEX IF EXISTS ix_caja_cerrada_por")
    op.execute("DROP INDEX IF EXISTS ix_caja_abierta_por")
    op.execute("DROP TABLE IF EXISTS caja")

    for drop in (
        FUNCION_MOVCAJA_CAJA_ABIERTA_DROP, FUNCION_MOVCAJA_INMUTABLE_DROP,
        FUNCION_RECIBO_PROTEGER_DROP, FUNCION_CAJA_PROTEGER_DROP,
    ):
        op.execute(drop)
