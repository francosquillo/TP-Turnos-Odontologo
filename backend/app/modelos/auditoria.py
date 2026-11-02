"""Evento de auditoria de acciones admin (C-12 R3, D-10, RN-GL-02).

Append-only: un trigger rechaza `UPDATE` y `DELETE`. `detalle` nunca lleva contrasenas ni datos
clinicos (la importacion guarda conteos, no filas). Los tests usan `create_all`, por eso el DDL
de la funcion y el trigger se adjunta desde aca (`after_create`); la migracion 009 repite los
mismos literales y un test compara ambos. Reglas del DDL: una sentencia por `execute` (asyncpg)
y sin `%` en el texto (`DDL()` interpola con `%`).
"""
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos import Base

ACCIONES = (
    "usuario_alta",
    "usuario_edicion",
    "usuario_desactivacion",
    "usuario_eliminacion",
    "pacientes_importacion",
    "exportacion_total",
)
_ACCIONES_SQL = ", ".join(f"'{a}'" for a in ACCIONES)

FUNCION_AUDITORIA_INMUTABLE_DDL = (
    "CREATE OR REPLACE FUNCTION evento_auditoria_inmutable() RETURNS trigger "
    "LANGUAGE plpgsql AS $$ BEGIN "
    "RAISE EXCEPTION 'el evento de auditoria es inmutable' "
    "USING ERRCODE = 'integrity_constraint_violation'; "
    "END; $$"
)
TRIGGER_AUDITORIA_INMUTABLE_DDL = (
    "CREATE TRIGGER trg_evento_auditoria_inmutable BEFORE UPDATE OR DELETE ON evento_auditoria "
    "FOR EACH ROW EXECUTE FUNCTION evento_auditoria_inmutable()"
)
FUNCION_AUDITORIA_INMUTABLE_DROP = "DROP FUNCTION IF EXISTS evento_auditoria_inmutable()"


class EventoAuditoria(Base):
    __tablename__ = "evento_auditoria"
    __table_args__ = (
        sa.CheckConstraint(f"accion IN ({_ACCIONES_SQL})", name="ck_evento_auditoria_accion"),
        sa.ForeignKeyConstraint(["actor_id"], ["usuario.id"], ondelete="RESTRICT"),
        sa.Index("ix_evento_auditoria_created_at", sa.text("created_at DESC")),
        sa.Index("ix_evento_auditoria_actor_id", "actor_id"),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(always=True), primary_key=True)
    actor_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    accion: Mapped[str] = mapped_column(sa.Text, nullable=False)
    objeto_tipo: Mapped[str] = mapped_column(sa.Text, nullable=False)
    objeto_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    detalle: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


event.listen(EventoAuditoria.__table__, "after_create", sa.DDL(FUNCION_AUDITORIA_INMUTABLE_DDL))
event.listen(EventoAuditoria.__table__, "after_create", sa.DDL(TRIGGER_AUDITORIA_INMUTABLE_DDL))
event.listen(EventoAuditoria.__table__, "after_drop", sa.DDL(FUNCION_AUDITORIA_INMUTABLE_DROP))
