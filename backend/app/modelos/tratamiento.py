"""Tratamiento: catálogo de solo lectura para presupuestos de C-09 (D-10).

`codigo_nomenclador` es texto sin FK: `Arancel` recién existe en C-11.
"""
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base


class Tratamiento(Base):
    __tablename__ = "tratamiento"
    __table_args__ = (
        sa.CheckConstraint("precio_base >= 0", name="ck_tratamiento_precio_no_negativo"),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    codigo: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    codigo_nomenclador: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    nombre: Mapped[str] = mapped_column(sa.Text, nullable=False)
    precio_base: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


__all__ = ["Tratamiento"]
