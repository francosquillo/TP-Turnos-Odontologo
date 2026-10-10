"""Esquemas Turno: estrictos (extra='forbid', regla dura). Sin token (D-05)."""
from datetime import datetime
from typing import Literal

from pydantic import model_validator

from app.esquemas.base import BaseSchema

EstadoTurno = Literal["pendiente", "confirmado", "asistido", "ausente", "cancelado"]
OrigenTurno = Literal["secretaria", "online", "lista_espera"]


class TurnoIn(BaseSchema):
    paciente_id: int
    profesional_id: int
    sillon_id: int
    inicio: datetime
    fin: datetime
    origen: OrigenTurno = "secretaria"
    sobre_turno: bool = False
    motivo_sobreturno: str | None = None

    @model_validator(mode="after")
    def _fin_mayor_inicio(self):
        if self.fin <= self.inicio:
            raise ValueError("fin debe ser > inicio")
        return self


class TurnoOut(BaseSchema):
    id: int
    paciente_id: int
    profesional_id: int
    sillon_id: int
    inicio: datetime
    fin: datetime
    estado: EstadoTurno
    origen: OrigenTurno
    sobre_turno: bool
    motivo_sobreturno: str | None = None
    motivo_cancelacion: str | None = None
    creado_por: int | None = None
    created_at: datetime


class EstadoPatch(BaseSchema):
    estado: EstadoTurno
    motivo: str | None = None


class ReprogramarIn(BaseSchema):
    inicio: datetime
    fin: datetime
    sobre_turno: bool = False
    motivo_sobreturno: str | None = None

    @model_validator(mode="after")
    def _fin_mayor_inicio(self):
        if self.fin <= self.inicio:
            raise ValueError("fin debe ser > inicio")
        return self


class HuecoOut(BaseSchema):
    inicio: datetime
    fin: datetime


class AgendaItemOut(BaseSchema):
    id: int
    inicio: datetime
    fin: datetime
    estado: EstadoTurno
    paciente_id: int
    paciente_nombre: str | None = None
    profesional_id: int
    profesional_matricula: str | None = None
    sillon_id: int
    sillon_nombre: str | None = None
