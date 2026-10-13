"""Notificacion + Plantilla: canal WhatsApp con garantia sin-PHI (C-06, D-01/D-02).

Notificacion es deliberadamente delgada: el cuerpo renderizado NUNCA se
persiste (solo las variables de render en `payload`), asi un SELECT
accidental no expone texto enviado. Segunda barrera de idempotencia a nivel
DB: UNIQUE parcial (turno_id, plantilla) WHERE estado != 'fallida' (la
primera es la clave Redis `notif:{turno_id}:{tipo}`, D-03).

Reprogramar habilita reenvio (resolucion humana 2026-10-13): el recordatorio
pertenece al horario del turno; si el turno cambia de inicio, el barrido
genera un tipo distinto o el operador reencola tras la fallida anterior.
"""
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base

CANALES = ("whatsapp", "email", "sms")
PLANTILLAS = (
    "recordatorio_48h",
    "recordatorio_24h",
    "confirmacion",
    "hueco_liberado",
    "resena_google",
    # Reservada para C-07 (oferta_lista_espera nace como fila seed + job, sin
    # migrar): el CHECK ya la admite para no bloquear al proximo change.
    "oferta_lista_espera",
)
ESTADOS = ("encolada", "enviada", "entregada", "leída", "fallida")


class Notificacion(Base):
    __tablename__ = "notificacion"
    __table_args__ = (
        sa.CheckConstraint(
            "canal IN ('whatsapp', 'email', 'sms')",
            name="ck_notificacion_canal_catalogo",
        ),
        sa.CheckConstraint(
            "plantilla IN ('recordatorio_48h', 'recordatorio_24h', 'confirmacion',"
            " 'hueco_liberado', 'resena_google', 'oferta_lista_espera')",
            name="ck_notificacion_plantilla_catalogo",
        ),
        sa.CheckConstraint(
            "estado IN ('encolada', 'enviada', 'entregada', 'leída', 'fallida')",
            name="ck_notificacion_estado_catalogo",
        ),
        sa.ForeignKeyConstraint(["turno_id"], ["turno.id"], ondelete="RESTRICT"),
        sa.Index("ix_notificacion_turno", "turno_id"),
        sa.Index("ix_notificacion_estado", "estado"),
        # D-01: una sola notificacion activa por turno+plantilla; tras
        # `fallida` se permite reencolar (reintento o reprogramacion).
        sa.Index(
            "uq_notificacion_turno_plantilla_activa",
            "turno_id",
            "plantilla",
            unique=True,
            postgresql_where=sa.text("estado != 'fallida'"),
        ),
    )

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    turno_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("turno.id", ondelete="RESTRICT"),
        nullable=False,
    )
    canal: Mapped[str] = mapped_column(sa.Text, nullable=False)
    plantilla: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # Telefono normalizado o email de destino (NUNCA nombre + dato clinico
    # juntos). En logs solo se muestran los ultimos 4 digitos.
    destinatario_ref: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    estado: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default="encolada"
    )
    # USD por envio real (0 en mock/stub); ref visible COSTO_META_USD_REF.
    costo: Mapped[Any] = mapped_column(sa.Numeric(10, 3), nullable=True)
    # Solo variables de render (nunca el texto enviado).
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    intentos: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default="0"
    )
    ultimo_error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class Plantilla(Base):
    """Catalogo versionado de plantillas (D-02, seed idempotente v1).

    C-07 anade `oferta_lista_espera` como fila seed sin migrar.
    """

    __tablename__ = "plantilla"
    __table_args__ = (
        sa.PrimaryKeyConstraint("nombre", "version", name="pk_plantilla"),
    )

    nombre: Mapped[str] = mapped_column(sa.Text, nullable=False)
    version: Mapped[str] = mapped_column(sa.Text, nullable=False)
    cuerpo: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # Variables declaradas que el render acepta (JSONB: lista de str).
    variables: Mapped[list] = mapped_column(JSONB, nullable=False)


__all__ = ["CANALES", "ESTADOS", "PLANTILLAS", "Notificacion", "Plantilla"]
