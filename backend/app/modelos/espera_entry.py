"""EsperaEntry: fila de lista de espera con oferta tokenizada (C-07, D-01).

Estados: activa | ofrecida | convertida | vencida.
CHECK: profesional_id O especialidad debe estar presente (toda entry apunta
a alguien o a algo).
CHECK: estado='ofrecida' exige oferta_expira_en + token_oferta_hash.
Índices: paciente_id, estado, profesional_id, created_at (FIFO).
Sin EXCLUDE (no hay solapamiento propio) y sin UNIQUE global (un paciente
puede esperar dos cosas distintas; la exclusión de doble-oferta es lógica
D-02/D-05, no DB).
"""
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base


class EsperaEntry(Base):
    """Fila de espera del paciente por profesional o especialidad."""

    __tablename__ = "espera_entry"
    __table_args__ = (
        sa.CheckConstraint(
            "profesional_id IS NOT NULL OR especialidad IS NOT NULL",
            name="ck_espera_destino_presente",
        ),
        sa.CheckConstraint(
            "estado != 'ofrecida' OR (oferta_expira_en IS NOT NULL AND "
            "token_oferta_hash IS NOT NULL)",
            name="ck_espera_ofrecida_exige_vencimiento",
        ),
        sa.CheckConstraint(
            "estado IN ('activa', 'ofrecida', 'convertida', 'vencida')",
            name="ck_espera_estado_catalogo",
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"], ["paciente.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["profesional_id"], ["profesional.id"], ondelete="RESTRICT"
        ),
        sa.Index("ix_espera_paciente_id", "paciente_id"),
        sa.Index("ix_espera_estado", "estado"),
        sa.Index("ix_espera_profesional_id", "profesional_id"),
        sa.Index("ix_espera_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    paciente_id: Mapped[int] = mapped_column(
        sa.BigInteger, nullable=False
    )
    profesional_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, nullable=True
    )
    especialidad: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    preferencia_horaria: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    estado: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default="activa"
    )
    oferta_expira_en: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    token_oferta_hash: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    oferta_hueco: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    motivo_baja: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


__all__ = ["EsperaEntry"]
