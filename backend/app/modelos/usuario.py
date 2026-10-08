"""Usuario: exactamente UN rol por FK simple (IN-02, NUNCA usuario_rol)."""
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modelos import Base


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = (
        sa.CheckConstraint("length(nombre) <= 120", name="ck_usuario_nombre_len"),
        sa.CheckConstraint("length(email) <= 320", name="ck_usuario_email_len"),
        # Lookup case-insensitive (D-05): unicidad sobre LOWER(email).
        sa.Index("ix_usuario_rol_id", "rol_id"),
        sa.Index("uq_usuario_email_lower", sa.text("lower(email)"), unique=True),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    nombre: Mapped[str] = mapped_column(sa.Text, nullable=False)
    email: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    rol_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("rol.id", ondelete="RESTRICT"),
        nullable=False,
    )
    activo: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    rol: Mapped["Rol"] = relationship(back_populates="usuarios")
