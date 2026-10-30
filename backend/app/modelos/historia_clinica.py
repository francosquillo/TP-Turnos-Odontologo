"""Historia clínica: una por paciente, baja lógica con motivo (C-08, D-06).

`paciente_id` es UNIQUE total (no parcial): una HC nueva tras una baja partiría
el historial clínico en dos. La baja no toca los hallazgos (FK RESTRICT).
`updated_at` lo fija el servicio con el reloj Python (freezegun en tests).
"""
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base


class HistoriaClinica(Base):
    __tablename__ = "historia_clinica"
    __table_args__ = (
        sa.CheckConstraint(
            "(deleted_at IS NULL) = (motivo_baja IS NULL)", name="ck_hc_baja_con_motivo"
        ),
        sa.CheckConstraint(
            "antecedentes IS NULL OR length(antecedentes) <= 10000",
            name="ck_hc_antecedentes_largo",
        ),
        sa.CheckConstraint(
            "alergias IS NULL OR length(alergias) <= 2000", name="ck_hc_alergias_largo"
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"], ["paciente.id"], ondelete="RESTRICT"
        ),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    paciente_id: Mapped[int] = mapped_column(
        sa.BigInteger, unique=True, nullable=False
    )
    antecedentes: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    alergias: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    motivo_baja: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


__all__ = ["HistoriaClinica"]
