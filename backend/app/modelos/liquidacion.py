"""Liquidaciones a obras sociales (C-11, D-09, D-10, D-12, D-13).

Una liquidación agrupa prestaciones (ítems de presupuesto aceptado, D-02) de una OS y un
período. `item_presupuesto_id` es UNIQUE: una prestación se liquida una sola vez. Un ítem
sin arancel (`arancel_id` nulo) es de revisión manual y vale 0. Estados: borrador ->
presentada -> cobrada; un `borrador` se descarta con borrado físico (D-10).
"""
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base

ESTADOS_LIQUIDACION = ("borrador", "presentada", "cobrada")
_ESTADOS_SQL = ", ".join(f"'{e}'" for e in ESTADOS_LIQUIDACION)


class Liquidacion(Base):
    __tablename__ = "liquidacion"
    __table_args__ = (
        sa.CheckConstraint(f"estado IN ({_ESTADOS_SQL})", name="ck_liquidacion_estado"),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM periodo) = 1", name="ck_liquidacion_periodo_dia_uno"
        ),
        sa.CheckConstraint("total >= 0", name="ck_liquidacion_total_no_negativo"),
        sa.ForeignKeyConstraint(["os_id"], ["obra_social.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["creada_por"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["presentada_por"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cobrada_por"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cobro_revertido_por"], ["usuario.id"], ondelete="RESTRICT"),
        sa.Index("ix_liquidacion_os_periodo", "os_id", "periodo"),
        sa.Index("ix_liquidacion_creada_por", "creada_por"),
        sa.Index("ix_liquidacion_presentada_por", "presentada_por"),
        sa.Index("ix_liquidacion_cobrada_por", "cobrada_por"),
        sa.Index("ix_liquidacion_cobro_revertido_por", "cobro_revertido_por"),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    os_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    periodo: Mapped[date] = mapped_column(sa.Date, nullable=False)
    estado: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default="borrador")
    total: Mapped[Decimal] = mapped_column(
        sa.Numeric(16, 2), nullable=False, server_default="0"
    )
    creada_por: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    presentada_por: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    presentada_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    cobrada_por: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    cobrada_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    cobro_revertido_por: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    cobro_revertido_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class ItemLiquidacion(Base):
    __tablename__ = "item_liquidacion"
    __table_args__ = (
        sa.CheckConstraint("monto >= 0", name="ck_itemliq_monto_no_negativo"),
        sa.CheckConstraint(
            "arancel_id IS NOT NULL OR monto = 0", name="ck_itemliq_revision_monto_cero"
        ),
        sa.UniqueConstraint("item_presupuesto_id", name="uq_itemliq_item_presupuesto"),
        sa.ForeignKeyConstraint(["liquidacion_id"], ["liquidacion.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["item_presupuesto_id"], ["item_presupuesto.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["plan.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["arancel_id"], ["arancel.id"], ondelete="RESTRICT"),
        sa.Index("ix_itemliq_liquidacion_id", "liquidacion_id"),
        sa.Index("ix_itemliq_plan_id", "plan_id"),
        sa.Index("ix_itemliq_arancel_id", "arancel_id"),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    liquidacion_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    item_presupuesto_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    plan_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    arancel_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    fecha_prestacion: Mapped[date] = mapped_column(sa.Date, nullable=False)
    monto: Mapped[Decimal] = mapped_column(sa.Numeric(16, 2), nullable=False)


__all__ = ["ESTADOS_LIQUIDACION", "ItemLiquidacion", "Liquidacion"]
