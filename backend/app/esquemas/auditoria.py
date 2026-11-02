"""Esquema de salida de la auditoria admin (C-12 R3)."""
from datetime import datetime

from app.esquemas.base import BaseSchema


class EventoAuditoriaOut(BaseSchema):
    id: int
    actor_id: int
    accion: str
    objeto_tipo: str
    objeto_id: int | None
    detalle: dict
    created_at: datetime
