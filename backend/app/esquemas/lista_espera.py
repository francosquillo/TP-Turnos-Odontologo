"""Esquemas lista de espera: estrictos (extra='forbid', regla dura)."""
from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from app.esquemas.base import BaseSchema

EstadoEspera = Literal["activa", "ofrecida", "convertida", "vencida"]
Dia = Literal[
    "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"
]
HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class PreferenciaHorariaIn(BaseSchema):
    """Franja deseada (todo opcional; vacío = cualquier hueco). Ver D-01."""

    dias: list[Dia] | None = None
    desde: str | None = Field(default=None, pattern=HHMM)
    hasta: str | None = Field(default=None, pattern=HHMM)


class EsperaIn(BaseSchema):
    paciente_id: int
    profesional_id: int | None = None
    especialidad: str | None = Field(default=None, min_length=1, max_length=120)
    preferencia_horaria: PreferenciaHorariaIn | None = None

    @model_validator(mode="after")
    def _destino_presente(self) -> Self:
        if self.profesional_id is None and not self.especialidad:
            raise ValueError("debe especificarse profesional_id o especialidad")
        return self


class EsperaPatch(BaseSchema):
    """Edición de una entry `activa` (sin tocar estado: la baja es POST /baja)."""

    profesional_id: int | None = None
    especialidad: str | None = Field(default=None, min_length=1, max_length=120)
    preferencia_horaria: PreferenciaHorariaIn | None = None


class BajaIn(BaseSchema):
    motivo_baja: str = Field(min_length=1, max_length=200)


class OfrecerIn(BaseSchema):
    """Hueco que secretaría ofrece a mano a una entry puntual."""

    profesional_id: int
    sillon_id: int
    inicio: datetime
    fin: datetime
    turno_id: int | None = None  # turno cancelado de origen (cuelga el aviso)

    @model_validator(mode="after")
    def _fin_posterior(self) -> Self:
        if self.fin <= self.inicio:
            raise ValueError("fin debe ser posterior a inicio")
        return self


class EsperaOut(BaseSchema):
    id: int
    paciente_id: int
    profesional_id: int | None = None
    especialidad: str | None = None
    preferencia_horaria: dict | None = None
    estado: EstadoEspera
    oferta_expira_en: datetime | None = None  # para el countdown del frontend
    oferta_hueco: dict | None = None
    motivo_baja: str | None = None
    created_at: datetime


class OfertaPublicaOut(BaseSchema):
    """Detalle mínimo para la página pública: sin PHI (nombre de pila + horario)."""

    nombre_pila: str
    inicio: datetime
    fin: datetime
    oferta_expira_en: datetime


__all__ = [
    "BajaIn",
    "EsperaIn",
    "EsperaOut",
    "EsperaPatch",
    "EstadoEspera",
    "OfertaPublicaOut",
    "OfrecerIn",
    "PreferenciaHorariaIn",
]
