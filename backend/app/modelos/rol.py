"""Rol: 3 fijos (admin/odontologo/secretaria). NUNCA rol dueno (IN-01)."""
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modelos import Base

ROLES_FIJOS = ("admin", "odontologo", "secretaria")


class Rol(Base):
    __tablename__ = "rol"
    __table_args__ = (
        sa.CheckConstraint(
            "nombre IN ('admin', 'odontologo', 'secretaria')",
            name="ck_rol_nombre_catalogo",
        ),
        sa.CheckConstraint("length(nombre) <= 32", name="ck_rol_nombre_len"),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    nombre: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="rol")
