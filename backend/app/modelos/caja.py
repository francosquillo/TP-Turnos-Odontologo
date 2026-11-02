"""Caja, recibos y movimientos de caja (C-10, D-02, D-10, D-14, D-25).

Una caja por fecha operativa y, como máximo, una abierta (D-02). El recibo se numera
sin huecos con una fila contador (D-10) y es inmutable salvo su anulación (D-14). El
movimiento de caja es inmutable y no admite altas en una caja cerrada.

Los tests usan `create_all`, por eso el DDL de funciones y triggers se adjunta desde
acá (`after_create`); la migración 007 repite los mismos literales y un test compara
ambos. Reglas del DDL: una sentencia por `execute` (asyncpg) y sin `%` en el texto
(`DDL()` interpola con `%`).
"""
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base

MEDIOS = ("efectivo", "transferencia", "tarjeta_simulada")
_MEDIOS_SQL = ", ".join(f"'{m}'" for m in MEDIOS)
ESTADOS_CAJA = ("abierta", "cerrada")
_ESTADOS_SQL = ", ".join(f"'{e}'" for e in ESTADOS_CAJA)

# UUID v4 en minúsculas: la misma expresión que valida el esquema (D-25).
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

# FOR SHARE espera a un cierre en curso y vuelve a evaluar la fila ya cerrada.
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


class Caja(Base):
    __tablename__ = "caja"
    __table_args__ = (
        sa.CheckConstraint(f"estado IN ({_ESTADOS_SQL})", name="ck_caja_estado"),
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
        sa.Index("ix_caja_abierta_por", "abierta_por"),
        sa.Index("ix_caja_cerrada_por", "cerrada_por"),
        sa.Index(
            "uq_caja_una_abierta", "estado", unique=True,
            postgresql_where=sa.text("estado = 'abierta'"),
        ),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    fecha: Mapped[date] = mapped_column(sa.Date, nullable=False)
    abierta_por: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    estado: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="abierta")
    total_sistema: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 2), nullable=True)
    total_contado: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 2), nullable=True)
    diferencia: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 2), nullable=True)
    motivo_diferencia: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    cerrada_por: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    cerrada_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class Recibo(Base):
    __tablename__ = "recibo"
    __table_args__ = (
        sa.CheckConstraint("monto > 0", name="ck_recibo_monto_positivo"),
        sa.CheckConstraint(f"medio IN ({_MEDIOS_SQL})", name="ck_recibo_medio"),
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
        sa.Index("ix_recibo_paciente_id", "paciente_id"),
        sa.Index("ix_recibo_emitido_por", "emitido_por"),
        sa.Index("ix_recibo_anulado_por", "anulado_por"),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    numero: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    paciente_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    monto: Mapped[Decimal] = mapped_column(sa.Numeric(16, 2), nullable=False)
    medio: Mapped[str] = mapped_column(sa.Text, nullable=False)
    emitido_por: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    clave_idempotencia: Mapped[str] = mapped_column(sa.Text, nullable=False)
    anulado: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    motivo_anulacion: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    anulado_por: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    anulado_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class ReciboContador(Base):
    """Una sola fila (id = 1): el lock de fila serializa la numeración sin huecos."""

    __tablename__ = "recibo_contador"
    __table_args__ = (sa.CheckConstraint("id = 1", name="ck_recibo_contador_unico"),)

    id: Mapped[int] = mapped_column(sa.SmallInteger, primary_key=True, autoincrement=False)
    ultimo: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)


class MovimientoCaja(Base):
    __tablename__ = "movimiento_caja"
    __table_args__ = (
        sa.CheckConstraint(f"medio IN ({_MEDIOS_SQL})", name="ck_movcaja_medio"),
        sa.CheckConstraint("monto <> 0", name="ck_movcaja_monto_no_cero"),
        sa.CheckConstraint(
            "monto > 0 OR motivo IS NOT NULL", name="ck_movcaja_reversion_con_motivo"
        ),
        sa.ForeignKeyConstraint(["caja_id"], ["caja.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recibo_id"], ["recibo.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["liquidacion_id"], ["liquidacion.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["creado_por"], ["usuario.id"], ondelete="RESTRICT"),
        # C-11 (D-14): exactamente una referencia, recibo o liquidacion.
        sa.CheckConstraint(
            "num_nonnulls(recibo_id, liquidacion_id) = 1", name="ck_movcaja_una_referencia"
        ),
        sa.Index("ix_movcaja_liquidacion_id", "liquidacion_id"),
        sa.Index(
            "uq_movcaja_liq_ingreso", "liquidacion_id", unique=True,
            postgresql_where=sa.text("monto > 0"),
        ),
        sa.Index(
            "uq_movcaja_liq_reversion", "liquidacion_id", unique=True,
            postgresql_where=sa.text("monto < 0"),
        ),
        sa.Index("ix_movcaja_caja_id", "caja_id"),
        sa.Index("ix_movcaja_recibo_id", "recibo_id"),
        sa.Index("ix_movcaja_creado_por", "creado_por"),
        sa.Index(
            "uq_movcaja_ingreso", "recibo_id", unique=True,
            postgresql_where=sa.text("monto > 0"),
        ),
        sa.Index(
            "uq_movcaja_reversion", "recibo_id", unique=True,
            postgresql_where=sa.text("monto < 0"),
        ),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    caja_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    recibo_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    liquidacion_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    medio: Mapped[str] = mapped_column(sa.Text, nullable=False)
    monto: Mapped[Decimal] = mapped_column(sa.Numeric(16, 2), nullable=False)
    motivo: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    creado_por: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


event.listen(Caja.__table__, "after_create", sa.DDL(FUNCION_CAJA_PROTEGER_DDL))
event.listen(Caja.__table__, "after_create", sa.DDL(TRIGGER_CAJA_PROTEGER_DDL))
event.listen(Caja.__table__, "after_drop", sa.DDL(FUNCION_CAJA_PROTEGER_DROP))
event.listen(Recibo.__table__, "after_create", sa.DDL(FUNCION_RECIBO_PROTEGER_DDL))
event.listen(Recibo.__table__, "after_create", sa.DDL(TRIGGER_RECIBO_PROTEGER_DDL))
event.listen(Recibo.__table__, "after_drop", sa.DDL(FUNCION_RECIBO_PROTEGER_DROP))
event.listen(MovimientoCaja.__table__, "after_create", sa.DDL(FUNCION_MOVCAJA_INMUTABLE_DDL))
event.listen(MovimientoCaja.__table__, "after_create", sa.DDL(TRIGGER_MOVCAJA_INMUTABLE_DDL))
event.listen(MovimientoCaja.__table__, "after_create", sa.DDL(FUNCION_MOVCAJA_CAJA_ABIERTA_DDL))
event.listen(MovimientoCaja.__table__, "after_create", sa.DDL(TRIGGER_MOVCAJA_CAJA_ABIERTA_DDL))
event.listen(MovimientoCaja.__table__, "after_drop", sa.DDL(FUNCION_MOVCAJA_INMUTABLE_DROP))
event.listen(MovimientoCaja.__table__, "after_drop", sa.DDL(FUNCION_MOVCAJA_CAJA_ABIERTA_DROP))


__all__ = [
    "CLAVE_REGEX", "Caja", "ESTADOS_CAJA", "MEDIOS", "MovimientoCaja", "Recibo",
    "ReciboContador",
]
