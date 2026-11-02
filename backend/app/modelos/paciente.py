"""Paciente: soft-delete via deleted_at (RN-GL-01, D-06)."""
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base


class Paciente(Base):
    __tablename__ = "paciente"
    __table_args__ = (
        sa.CheckConstraint("length(nombre) <= 120", name="ck_paciente_nombre_len"),
        sa.CheckConstraint("length(apellido) <= 120", name="ck_paciente_apellido_len"),
        sa.CheckConstraint("length(dni) <= 20", name="ck_paciente_dni_len"),
        # DNI nullable con unicidad parcial: duplicados reales rechazados,
        # multiples NULL permitidos (D-05).
        sa.Index(
            "uq_paciente_dni",
            "dni",
            unique=True,
            postgresql_where=sa.text("dni IS NOT NULL"),
        ),
        sa.Index("ix_paciente_apellido", "apellido"),
        sa.Index("ix_paciente_telefono", "telefono"),
        # C-11 (D-07): plan opcional; la obra social se deriva del plan.
        sa.ForeignKeyConstraint(["plan_id"], ["plan.id"], ondelete="RESTRICT"),
        sa.Index("ix_paciente_plan_id", "plan_id"),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    nombre: Mapped[str] = mapped_column(sa.Text, nullable=False)
    apellido: Mapped[str] = mapped_column(sa.Text, nullable=False)
    dni: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    telefono: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    email: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    cobertura_os: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    notas: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    plan_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    consentimiento_datos: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    consentimiento_fecha: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
