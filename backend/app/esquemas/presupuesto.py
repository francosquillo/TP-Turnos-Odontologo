"""Esquemas de presupuestos (C-09, D-04, D-06, D-09).

Todos estrictos (`extra='forbid'`). El cliente NO envía `profesional_id`,
`estado`, `total` ni `precio`: los fija el servidor. Los importes viajan como
texto decimal con dos decimales. `pieza_fdi`, `cara` y `motivo_rechazo` son
opcionales en la salida porque el admin recibe la vista financiera (D-09).
"""
from datetime import datetime
from typing import Annotated, Self

from pydantic import Field, model_validator

from app.esquemas.base import BaseSchema, Dinero
from app.esquemas.clinica import Motivo

MAX_ITEMS = 50


class ItemIn(BaseSchema):
    hallazgo_id: int
    tratamiento_id: int
    cantidad: Annotated[int, Field(ge=1, le=99)] = 1


def _sin_repetidos(items: list[ItemIn]) -> list[ItemIn]:
    pares = [(i.hallazgo_id, i.tratamiento_id) for i in items]
    if len(set(pares)) != len(pares):
        raise ValueError("hay ítems repetidos (mismo hallazgo y tratamiento)")
    return items


ItemsIn = Annotated[list[ItemIn], Field(min_length=1, max_length=MAX_ITEMS)]


class PresupuestoIn(BaseSchema):
    paciente_id: int
    items: ItemsIn

    @model_validator(mode="after")
    def _items_unicos(self) -> Self:
        _sin_repetidos(self.items)
        return self


class PresupuestoPut(BaseSchema):
    """Reemplaza la lista completa de ítems de un borrador."""

    items: ItemsIn

    @model_validator(mode="after")
    def _items_unicos(self) -> Self:
        _sin_repetidos(self.items)
        return self


class RechazoIn(BaseSchema):
    motivo: Motivo


class ItemOut(BaseSchema):
    id: int
    hallazgo_id: int
    tratamiento_id: int
    tratamiento_nombre: str
    pieza_fdi: int | None
    cara: str | None
    cantidad: int
    precio: Dinero
    subtotal: Dinero
    # False si el hallazgo fue dado de baja o corregido después de presupuestar (D-05).
    hallazgo_vigente: bool


class PresupuestoOut(BaseSchema):
    id: int
    paciente_id: int
    profesional_id: int
    estado: str
    total: Dinero
    motivo_rechazo: str | None
    presentado_at: datetime | None
    decidido_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Derivado: el cargo del presupuesto aceptado fue anulado (D-14).
    cargo_anulado: bool
    # Derivado: quien consulta es el autor (la SPA no conoce su profesional_id).
    es_propio: bool
    items: list[ItemOut]


__all__ = [
    "ItemIn", "ItemOut", "PresupuestoIn", "PresupuestoOut", "PresupuestoPut", "RechazoIn",
]
