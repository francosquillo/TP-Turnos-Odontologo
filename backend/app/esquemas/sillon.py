"""Esquemas Sillon: estrictos (extra='forbid', D-07)."""
from app.esquemas.base import BaseSchema


class SillonCreate(BaseSchema):
    nombre: str
    sede: str | None = None


class SillonResponse(BaseSchema):
    id: int
    nombre: str
    sede: str
    activo: bool
