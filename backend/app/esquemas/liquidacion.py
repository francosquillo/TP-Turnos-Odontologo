"""Esquemas de liquidaciones (C-11, D-09, D-12, D-13, D-15, D-16).

Estrictos (`extra='forbid'`). El cliente envía solo la obra social, el período `YYYY-MM`, el
medio y el motivo: el total, los montos, las fechas y el autor los calcula el servidor. No hay
esquema para editar importes. Los motivos viajan en el cuerpo y nunca en logs.
"""
import re
from datetime import date, datetime
from typing import Annotated

from pydantic import BeforeValidator

from app.esquemas.base import BaseSchema, Dinero
from app.esquemas.caja import MedioPago
from app.esquemas.clinica import Motivo

_PERIODO = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def _periodo_a_fecha(valor: object) -> date:
    """`YYYY-MM` -> primer día del mes; una `date` con día 1 también vale."""
    if isinstance(valor, date) and not isinstance(valor, datetime):
        if valor.day != 1:
            raise ValueError("el período debe ser el primer día del mes")
        return valor
    if not isinstance(valor, str):
        raise ValueError("el período debe tener el formato YYYY-MM")
    match = _PERIODO.match(valor)
    if match is None:
        raise ValueError("el período debe tener el formato YYYY-MM")
    return date(int(match.group(1)), int(match.group(2)), 1)


Periodo = Annotated[date, BeforeValidator(_periodo_a_fecha)]


class GenerarLiquidacionIn(BaseSchema):
    os_id: int
    periodo: Periodo


class CobrarLiquidacionIn(BaseSchema):
    medio: MedioPago


class RevertirCobroIn(BaseSchema):
    motivo: Motivo


class ItemLiquidacionOut(BaseSchema):
    id: int
    item_presupuesto_id: int
    fecha_prestacion: date
    paciente_nombre: str
    codigo: str
    descripcion: str
    cantidad: int
    monto: Dinero
    revision: bool


class PlanLiquidacionOut(BaseSchema):
    plan_id: int
    plan_nombre: str
    subtotal: Dinero
    items: list[ItemLiquidacionOut]


class LiquidacionOut(BaseSchema):
    """Resumen de listado: sin filas."""

    id: int
    os_id: int
    obra_social: str
    periodo: date
    estado: str
    total: Dinero
    cantidad_items: int
    cantidad_revision: int
    creada_por: int
    presentada_at: datetime | None
    cobrada_at: datetime | None
    cobro_revertido_at: datetime | None
    created_at: datetime


class LiquidacionDetalleOut(LiquidacionOut):
    planes: list[PlanLiquidacionOut]
    # Verdadero tras revertir el cobro: no se puede volver a cobrar (D-13).
    revertida: bool


__all__ = [
    "CobrarLiquidacionIn", "GenerarLiquidacionIn", "ItemLiquidacionOut", "LiquidacionDetalleOut",
    "LiquidacionOut", "PlanLiquidacionOut", "RevertirCobroIn",
]
