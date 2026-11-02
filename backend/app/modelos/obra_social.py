"""Obras sociales, planes y aranceles versionados (C-11, D-07, D-08).

`Arancel.precio` es lo que la OS paga por el código y el plan. El precio es inmutable
(un precio nuevo es un arancel nuevo); lo único que se edita es `vigencia_hasta`. La
superposición de vigencias la impide un EXCLUDE sobre `daterange` (requiere `btree_gist`,
habilitado en C-01). Baja lógica con `activa`/`activo`: no hay borrado físico.
"""
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base


class ObraSocial(Base):
    __tablename__ = "obra_social"
    __table_args__ = (
        sa.CheckConstraint("length(nombre) BETWEEN 1 AND 120", name="ck_obra_social_nombre_len"),
        sa.UniqueConstraint("nombre", name="uq_obra_social_nombre"),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    nombre: Mapped[str] = mapped_column(sa.Text, nullable=False)
    activa: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class Plan(Base):
    __tablename__ = "plan"
    __table_args__ = (
        sa.CheckConstraint("length(nombre) BETWEEN 1 AND 120", name="ck_plan_nombre_len"),
        sa.UniqueConstraint("obra_social_id", "nombre", name="uq_plan_obra_social_nombre"),
        sa.ForeignKeyConstraint(["obra_social_id"], ["obra_social.id"], ondelete="RESTRICT"),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    obra_social_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    nombre: Mapped[str] = mapped_column(sa.Text, nullable=False)
    activo: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class Arancel(Base):
    __tablename__ = "arancel"
    __table_args__ = (
        sa.CheckConstraint("precio > 0", name="ck_arancel_precio_positivo"),
        sa.CheckConstraint(
            "vigencia_hasta IS NULL OR vigencia_hasta >= vigencia_desde",
            name="ck_arancel_vigencia_rango",
        ),
        ExcludeConstraint(
            ("plan_id", "="),
            ("codigo_nomenclador", "="),
            (sa.text("daterange(vigencia_desde, vigencia_hasta, '[]')"), "&&"),
            name="ex_arancel_sin_solape",
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["plan.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["creado_por"], ["usuario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cerrado_por"], ["usuario.id"], ondelete="RESTRICT"),
        sa.Index("ix_arancel_plan_codigo", "plan_id", "codigo_nomenclador"),
        sa.Index("ix_arancel_creado_por", "creado_por"),
        sa.Index("ix_arancel_cerrado_por", "cerrado_por"),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    plan_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    codigo_nomenclador: Mapped[str] = mapped_column(sa.Text, nullable=False)
    descripcion: Mapped[str] = mapped_column(sa.Text, nullable=False)
    precio: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    vigencia_desde: Mapped[date] = mapped_column(sa.Date, nullable=False)
    vigencia_hasta: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    creado_por: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    cerrado_por: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    cerrado_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


__all__ = ["Arancel", "ObraSocial", "Plan"]
