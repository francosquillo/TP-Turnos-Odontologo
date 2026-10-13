"""Esquemas notificaciones staff: proyeccion sin PHI (D-06)."""
from datetime import datetime

from app.esquemas.base import BaseSchema


class PendienteOut(BaseSchema):
    turno_id: int
    inicio: datetime
    paciente_nombre: str
    motivo: str | None = None


__all__ = ["PendienteOut"]
