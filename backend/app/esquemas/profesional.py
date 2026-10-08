"""Esquemas Profesional + AgendaConfig semanal (D-05/D-07)."""
import re
from typing import Any

from pydantic import field_validator

from app.esquemas.base import BaseSchema

_HORA_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class AgendaConfig(BaseSchema):
    """Valida forma semanal: {duracion_slot_min, horario: {dia: [[ini, fin]]}}."""

    duracion_slot_min: int
    horario: dict[str, list[list[str]]]

    @field_validator("duracion_slot_min")
    @classmethod
    def _duracion_positiva(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("duracion_slot_min debe ser positiva")
        return v

    @field_validator("horario")
    @classmethod
    def _horario_valido(cls, v: dict[str, list[list[str]]]) -> dict[str, list[list[str]]]:
        dias = [d for d, franjas in v.items() if franjas]
        if not dias:
            raise ValueError("horario debe tener al menos un dia con franjas")
        for dia, franjas in v.items():
            for franja in franjas:
                if len(franja) != 2:
                    raise ValueError(f"franja {franja} debe ser [ini, fin]")
                ini, fin = franja
                if not (_HORA_RE.match(ini) and _HORA_RE.match(fin)):
                    raise ValueError(f"franja {franja} debe ser HH:MM valida")
                if fin <= ini:
                    raise ValueError(f"franja {franja}: fin debe ser > inicio")
        return v


class ProfesionalCreate(BaseSchema):
    matricula: str
    especialidades: str = ""
    usuario_id: int | None = None
    agenda_config: dict[str, Any] | None = None


class ProfesionalResponse(BaseSchema):
    id: int
    matricula: str
    especialidades: str
    usuario_id: int | None = None
    agenda_config: dict[str, Any]
    activo: bool
