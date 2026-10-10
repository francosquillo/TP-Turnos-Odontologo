"""Esquemas reserva publica: estrictos (extra='forbid', regla dura).

Telefono se valida/normaliza en el servicio (acepta formatos con espacios y
guiones); el esquema solo exige presencia. Nombre >= 2 (US-002 CA-3).
"""
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.esquemas.base import BaseSchema


class ReservaIn(BaseSchema):
    profesional_id: int
    sillon_id: int
    inicio: datetime
    fin: datetime
    nombre: str = Field(min_length=2)
    telefono: str = Field(min_length=1)
    dni: str | None = None
    email: str | None = None

    @model_validator(mode="after")
    def _fin_mayor_inicio(self):
        if self.fin <= self.inicio:
            raise ValueError("fin debe ser > inicio")
        return self


class ReservaOut(BaseSchema):
    turno_id: int
    estado: Literal["pendiente"] = "pendiente"
    token: str
    expira_en: datetime


class ConfirmarOut(BaseSchema):
    estado: str
    inicio: datetime
    fin: datetime
    profesional_id: int
