"""Catálogo versionado de estados + hallazgo de odontograma (C-08, D-02..D-05).

El hallazgo es inmutable en sus campos clínicos: una corrección da de baja la
fila y crea otra con `corrige_a_id` (D-05). FDI exacto (11-18/21-28/31-38/
41-48, no el rango 11-48), cara coherente con la arcada y estado con FK
compuesta (estado, catalogo_version) al catálogo, para que la DB impida valores
fuera de catálogo sin perder legibilidad de datos viejos.
"""
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base

CARAS = (
    "oclusal", "mesial", "distal", "vestibular", "palatina", "lingual",
    "raiz", "pieza_completa",
)

# (codigo, nombre, alcance): V1 = los 7 valores nombrados en la KB (D-04).
# La migración 005_clinica repite estos literales (no importa modelos).
CATALOGO_ESTADOS_V1: tuple[tuple[str, str, str], ...] = (
    ("sano", "Sano", "cualquiera"),
    ("caries", "Caries", "cualquiera"),
    ("obturacion", "Obturación", "cualquiera"),
    ("corona", "Corona", "pieza"),
    ("endodoncia", "Endodoncia", "pieza"),
    ("implante", "Implante", "pieza"),
    ("ausente", "Ausente", "pieza"),
)
CATALOGO_VERSION_V1 = 1

_CARAS_SQL = ", ".join(f"'{c}'" for c in CARAS)


class EstadoHallazgoCatalogo(Base):
    """Estado clínico permitido en una versión del catálogo (solo lectura por API)."""

    __tablename__ = "estado_hallazgo_catalogo"
    __table_args__ = (
        sa.UniqueConstraint("codigo", "version", name="uq_estado_catalogo_codigo_version"),
        sa.CheckConstraint(
            "alcance IN ('cualquiera', 'pieza')", name="ck_estado_catalogo_alcance"
        ),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    codigo: Mapped[str] = mapped_column(sa.Text, nullable=False)
    version: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    nombre: Mapped[str] = mapped_column(sa.Text, nullable=False)
    alcance: Mapped[str] = mapped_column(sa.Text, nullable=False)
    vigente: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)


class HallazgoOdontograma(Base):
    """Hallazgo clínico por pieza FDI y cara (RN-CL-01/03)."""

    __tablename__ = "hallazgo_odontograma"
    __table_args__ = (
        sa.CheckConstraint(
            "pieza_fdi BETWEEN 11 AND 48 AND pieza_fdi % 10 BETWEEN 1 AND 8",
            name="ck_hallazgo_pieza_fdi_valida",
        ),
        sa.CheckConstraint(f"cara IN ({_CARAS_SQL})", name="ck_hallazgo_cara_catalogo"),
        sa.CheckConstraint(
            "(cara <> 'palatina' OR pieza_fdi < 30) AND "
            "(cara <> 'lingual' OR pieza_fdi >= 30)",
            name="ck_hallazgo_cara_arcada",
        ),
        sa.CheckConstraint(
            "(deleted_at IS NULL) = (motivo_baja IS NULL)",
            name="ck_hallazgo_baja_con_motivo",
        ),
        sa.ForeignKeyConstraint(
            ["estado", "catalogo_version"],
            ["estado_hallazgo_catalogo.codigo", "estado_hallazgo_catalogo.version"],
            name="fk_hallazgo_estado_catalogo",
        ),
        sa.ForeignKeyConstraint(
            ["hc_id"], ["historia_clinica.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["profesional_id"], ["profesional.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["corrige_a_id"], ["hallazgo_odontograma.id"]),
        sa.Index("ix_hallazgo_hc_pieza", "hc_id", "pieza_fdi"),
        sa.Index("ix_hallazgo_profesional_id", "profesional_id"),
        sa.Index("ix_hallazgo_estado_version", "estado", "catalogo_version"),
        sa.Index(
            "uq_hallazgo_corrige_a",
            "corrige_a_id",
            unique=True,
            postgresql_where=sa.text("corrige_a_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    hc_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    pieza_fdi: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    cara: Mapped[str] = mapped_column(sa.Text, nullable=False)
    estado: Mapped[str] = mapped_column(sa.Text, nullable=False)
    catalogo_version: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    fecha: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    profesional_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    corrige_a_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    motivo_baja: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


__all__ = [
    "CARAS",
    "CATALOGO_ESTADOS_V1",
    "CATALOGO_VERSION_V1",
    "EstadoHallazgoCatalogo",
    "HallazgoOdontograma",
]
