"""Presupuesto e ítems (C-09, D-02, D-06, D-07, D-18).

`total` es columna guardada: solo la recalcula el servicio, bajo `FOR UPDATE`.
El ítem referencia hallazgo Y tratamiento (ambos NOT NULL); `precio` es el
`precio_base` copiado por el servidor. `cobrado` queda admitido por el CHECK
pero ninguna ruta de C-09 lo escribe (lo define C-10).
"""
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base

ESTADOS_PRESUPUESTO = ("borrador", "presentado", "aceptado", "rechazado", "cobrado")
_ESTADOS_SQL = ", ".join(f"'{e}'" for e in ESTADOS_PRESUPUESTO)


class Presupuesto(Base):
    __tablename__ = "presupuesto"
    __table_args__ = (
        sa.CheckConstraint(f"estado IN ({_ESTADOS_SQL})", name="ck_presupuesto_estado"),
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
        sa.Index("ix_presupuesto_paciente_created", "paciente_id", sa.text("created_at DESC")),
        sa.Index("ix_presupuesto_profesional_id", "profesional_id"),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    paciente_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    profesional_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    estado: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="borrador")
    total: Mapped[Decimal] = mapped_column(
        sa.Numeric(16, 2), nullable=False, server_default="0"
    )
    motivo_rechazo: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    presentado_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    decidido_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    motivo_baja: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


class ItemPresupuesto(Base):
    __tablename__ = "item_presupuesto"
    __table_args__ = (
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
        # presupuesto_id queda cubierto por el prefijo del UNIQUE compuesto.
        sa.Index("ix_item_presupuesto_hallazgo_id", "hallazgo_id"),
        sa.Index("ix_item_presupuesto_tratamiento_id", "tratamiento_id"),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    presupuesto_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    hallazgo_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    tratamiento_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    cantidad: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    precio: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)


__all__ = ["ESTADOS_PRESUPUESTO", "ItemPresupuesto", "Presupuesto"]
