"""Esquemas Paciente: estrictos (extra='forbid', D-07)."""
from datetime import datetime

from app.esquemas.base import BaseSchema


class PacienteCreate(BaseSchema):
    nombre: str
    apellido: str
    dni: str | None = None
    telefono: str | None = None
    email: str | None = None
    cobertura_os: str | None = None
    notas: str | None = None
    consentimiento_datos: bool


class PacienteResponse(BaseSchema):
    id: int
    nombre: str
    apellido: str
    dni: str | None = None
    telefono: str | None = None
    email: str | None = None
    cobertura_os: str | None = None
    notas: str | None = None
    consentimiento_datos: bool
    deleted_at: datetime | None = None
