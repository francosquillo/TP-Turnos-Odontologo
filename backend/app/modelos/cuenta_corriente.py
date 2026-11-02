"""Cuenta corriente y movimientos inmutables (C-09, D-11, D-12, D-16).

El saldo NO es columna: se deriva con SUM(monto). `movimiento` es inmutable por
trigger (UPDATE/DELETE por fila lanzan excepción); `TRUNCATE` y `DROP` no lo
disparan, así que las fixtures siguen funcionando. Los tests usan `create_all`,
por eso el DDL del trigger se adjunta desde el modelo (`after_create`); la
migración 006 repite los mismos literales y un test compara ambos.
`recibo_id` referencia `recibo` (C-10, D-15): un `pago` nace siempre con recibo, y cada
recibo tiene un solo `pago`. Un `ajuste` de anulación también puede citar el recibo.
"""
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base

TIPOS_MOVIMIENTO = ("cargo", "pago", "ajuste")
_TIPOS_SQL = ", ".join(f"'{t}'" for t in TIPOS_MOVIMIENTO)

# Dos sentencias separadas: asyncpg no acepta varias en un solo `execute`.
# Sin `%` en el texto: `DDL()` interpola con `%`.
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


class CuentaCorriente(Base):
    __tablename__ = "cuenta_corriente"
    __table_args__ = (
        sa.UniqueConstraint("paciente_id", name="uq_cuenta_corriente_paciente"),
        sa.ForeignKeyConstraint(["paciente_id"], ["paciente.id"], ondelete="RESTRICT"),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    paciente_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class Movimiento(Base):
    __tablename__ = "movimiento"
    __table_args__ = (
        sa.CheckConstraint(f"tipo IN ({_TIPOS_SQL})", name="ck_movimiento_tipo"),
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
        sa.CheckConstraint(
            "tipo <> 'pago' OR recibo_id IS NOT NULL", name="ck_movimiento_pago_con_recibo"
        ),
        sa.ForeignKeyConstraint(["anula_a_id"], ["movimiento.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["recibo_id"], ["recibo.id"], ondelete="RESTRICT", name="fk_movimiento_recibo"
        ),
        sa.ForeignKeyConstraint(["creado_por"], ["usuario.id"], ondelete="RESTRICT"),
        sa.Index("ix_movimiento_cc_created", "cc_id", "created_at"),
        sa.Index("ix_movimiento_turno_id", "turno_id"),
        sa.Index("ix_movimiento_presupuesto_id", "presupuesto_id"),
        sa.Index("ix_movimiento_creado_por", "creado_por"),
        sa.Index("ix_movimiento_recibo_id", "recibo_id"),
        sa.Index(
            "uq_movimiento_pago_recibo",
            "recibo_id",
            unique=True,
            postgresql_where=sa.text("tipo = 'pago'"),
        ),
        sa.Index(
            "uq_movimiento_cargo_presupuesto",
            "presupuesto_id",
            unique=True,
            postgresql_where=sa.text("tipo = 'cargo'"),
        ),
        # C-11 (D-05): como mucho un ajuste de cobertura (negativo, sin anulacion ni recibo).
        sa.Index(
            "uq_movimiento_cobertura_presupuesto",
            "presupuesto_id",
            unique=True,
            postgresql_where=sa.text(
                "tipo = 'ajuste' AND anula_a_id IS NULL AND recibo_id IS NULL AND monto < 0"
            ),
        ),
        sa.Index(
            "uq_movimiento_anula_a",
            "anula_a_id",
            unique=True,
            postgresql_where=sa.text("anula_a_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    cc_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    tipo: Mapped[str] = mapped_column(sa.Text, nullable=False)
    monto: Mapped[Decimal] = mapped_column(sa.Numeric(16, 2), nullable=False)
    concepto: Mapped[str] = mapped_column(sa.Text, nullable=False)
    motivo: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    turno_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    presupuesto_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    recibo_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    anula_a_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    creado_por: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


event.listen(Movimiento.__table__, "after_create", sa.DDL(FUNCION_INMUTABLE_DDL))
event.listen(Movimiento.__table__, "after_create", sa.DDL(TRIGGER_INMUTABLE_DDL))
event.listen(Movimiento.__table__, "after_drop", sa.DDL(FUNCION_INMUTABLE_DROP))


__all__ = [
    "CuentaCorriente", "FUNCION_INMUTABLE_DDL", "Movimiento", "TIPOS_MOVIMIENTO",
    "TRIGGER_INMUTABLE_DDL",
]
