"""Esquemas de obras sociales, planes, aranceles y validador (C-11, D-04, D-07, D-08).

Todos estrictos (`extra='forbid'`). El precio de un arancel es inmutable: `ArancelPatch`
solo declara `vigencia_hasta`, así que un `precio` en el cuerpo es 422. Los importes
viajan como texto con 2 decimales (`Dinero`).
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, model_validator

from app.esquemas.base import BaseSchema, Dinero


def _nombre(valor: str) -> str:
    valor = valor.strip()
    if not valor:
        raise ValueError("el texto no puede estar vacío")
    return valor


Nombre = Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_nombre)]
Codigo = Annotated[str, Field(min_length=1, max_length=40), AfterValidator(_nombre)]
Descripcion = Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_nombre)]
# Positivo, dos decimales y dentro de NUMERIC(12,2); nunca NaN ni infinito.
PrecioArancel = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class ObraSocialIn(BaseSchema):
    nombre: Nombre


class ObraSocialPatch(BaseSchema):
    """Solo se aplican los campos enviados (`exclude_unset`)."""

    nombre: Nombre | None = None
    activa: bool | None = None


class ObraSocialOut(BaseSchema):
    id: int
    nombre: str
    activa: bool
    created_at: datetime


class PlanIn(BaseSchema):
    obra_social_id: int
    nombre: Nombre


class PlanPatch(BaseSchema):
    nombre: Nombre | None = None
    activo: bool | None = None


class PlanOut(BaseSchema):
    id: int
    obra_social_id: int
    obra_social_nombre: str
    nombre: str
    activo: bool
    created_at: datetime


class ArancelIn(BaseSchema):
    plan_id: int
    codigo_nomenclador: Codigo
    descripcion: Descripcion
    precio: PrecioArancel
    vigencia_desde: date
    vigencia_hasta: date | None = None

    @model_validator(mode="after")
    def _rango_valido(self) -> "ArancelIn":
        if self.vigencia_hasta is not None and self.vigencia_hasta < self.vigencia_desde:
            raise ValueError("vigencia_hasta no puede ser anterior a vigencia_desde")
        return self


class ArancelPatch(BaseSchema):
    """Lo único editable de un arancel: cerrar su vigencia (el precio es inmutable)."""

    vigencia_hasta: date


class ArancelOut(BaseSchema):
    id: int
    plan_id: int
    codigo_nomenclador: str
    descripcion: str
    precio: Dinero
    vigencia_desde: date
    vigencia_hasta: date | None
    creado_por: int | None
    cerrado_por: int | None
    cerrado_at: datetime | None
    created_at: datetime


class PlanPacienteIn(BaseSchema):
    """`plan_id` es obligatorio (sin default): `null` quita el plan, y `{}` es 422."""

    plan_id: int | None


class PlanPacienteOut(BaseSchema):
    paciente_id: int
    plan_id: int | None
    plan_nombre: str | None
    obra_social_id: int | None
    obra_social_nombre: str | None


EstadoCobertura = Literal["cubierto", "sin_arancel", "sin_plan"]


class ValidadorCoberturaOut(BaseSchema):
    estado: EstadoCobertura
    paciente_id: int
    tratamiento_id: int
    plan_id: int | None
    precio: Dinero
    arancel: Dinero | None
    cubierto: Dinero
    a_cargo: Dinero
    porcentaje: Dinero
    fecha: date


__all__ = [
    "ArancelIn", "ArancelOut", "ArancelPatch", "EstadoCobertura", "ObraSocialIn",
    "ObraSocialOut", "ObraSocialPatch", "PlanIn", "PlanOut", "PlanPacienteIn",
    "PlanPacienteOut", "PlanPatch", "ValidadorCoberturaOut",
]
