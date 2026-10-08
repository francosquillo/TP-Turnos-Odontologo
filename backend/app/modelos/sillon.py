"""Sillon: sede texto libre, default sede unica v1.0 (extensible post-TP)."""
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base

SEDE_DEFAULT = "Sede única"


class Sillon(Base):
    __tablename__ = "sillon"
    __table_args__ = (
        sa.CheckConstraint("length(nombre) <= 80", name="ck_sillon_nombre_len"),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    nombre: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    sede: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default=sa.text("'Sede única'")
    )
    activo: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
