"""Turno: agenda core con doble anti-solapamiento a nivel DB (C-04, D-01).

Dos EXCLUDE parciales (profesional y sillon) sobre tstzrange(inicio, fin):
solo participan turnos activos no-sobreturno; cancelado/ausente liberan el
hueco y sobre_turno=true pasa por el predicado (RN-TU-01/02).
token_confirmacion_hash reservada NULL: el flujo token es C-05 (D-05).
"""
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base

_PREDICADO_ACTIVOS = (
    "sobre_turno IS FALSE "
    "AND estado IN ('pendiente','confirmado','asistido')"
)


class Turno(Base):
    __tablename__ = "turno"
    __table_args__ = (
        sa.CheckConstraint("fin > inicio", name="ck_turno_fin_mayor_inicio"),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'confirmado', 'asistido', 'ausente', 'cancelado')",
            name="ck_turno_estado_catalogo",
        ),
        sa.CheckConstraint(
            "origen IN ('secretaria', 'online', 'lista_espera')",
            name="ck_turno_origen_catalogo",
        ),
        # D-01: el choque es imposible por DB (btree_gist para el `=`).
        ExcludeConstraint(
            ("profesional_id", "="),
            (sa.text("tstzrange(inicio, fin)"), "&&"),
            where=sa.text(_PREDICADO_ACTIVOS),
            name="ex_turno_prof_sin_solape",
        ),
        ExcludeConstraint(
            ("sillon_id", "="),
            (sa.text("tstzrange(inicio, fin)"), "&&"),
            where=sa.text(_PREDICADO_ACTIVOS),
            name="ex_turno_sillon_sin_solape",
        ),
        sa.Index("ix_turno_profesional_inicio", "profesional_id", "inicio"),
        sa.Index("ix_turno_sillon_inicio", "sillon_id", "inicio"),
        sa.Index("ix_turno_estado", "estado"),
        sa.Index(
            "ix_turno_token_hash",
            "token_confirmacion_hash",
            postgresql_where=sa.text("token_confirmacion_hash IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    paciente_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("paciente.id", ondelete="RESTRICT"),
        nullable=False,
    )
    profesional_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("profesional.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sillon_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("sillon.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inicio: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    fin: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    estado: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default="pendiente"
    )
    origen: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default="secretaria"
    )
    token_confirmacion_hash: Mapped[str | None] = mapped_column(
        sa.Text, nullable=True
    )
    sobre_turno: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    motivo_sobreturno: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    motivo_cancelacion: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    creado_por: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("usuario.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
