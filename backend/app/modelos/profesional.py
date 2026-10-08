"""Profesional: vinculo opcional a cuenta + agenda_config JSONB (D-05)."""
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base


class Profesional(Base):
    __tablename__ = "profesional"
    __table_args__ = (
        sa.CheckConstraint(
            "length(matricula) <= 40", name="ck_profesional_matricula_len"
        ),
        sa.Index("ix_profesional_usuario_id", "usuario_id"),
        sa.Index(
            "ix_profesional_agenda_gin", "agenda_config", postgresql_using="gin"
        ),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    usuario_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("usuario.id", ondelete="SET NULL"),
        nullable=True,
    )
    matricula: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    especialidades: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default=""
    )
    agenda_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    activo: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
