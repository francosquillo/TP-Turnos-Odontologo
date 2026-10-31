"""Esquemas de cuenta corriente (C-09, D-11, D-12, D-14).

El saldo se deriva (SUM) en cada lectura y viaja como texto decimal. No hay
esquema de alta de movimientos: la única escritura por API es la anulación.
"""
from datetime import datetime

from app.esquemas.base import BaseSchema, Dinero
from app.esquemas.clinica import Motivo


class AnulacionIn(BaseSchema):
    motivo: Motivo


class MovimientoOut(BaseSchema):
    id: int
    tipo: str
    monto: Dinero
    concepto: str
    motivo: str | None
    turno_id: int | None
    presupuesto_id: int | None
    recibo_id: int | None
    anula_a_id: int | None
    creado_por: int
    created_at: datetime
    anulado: bool


class CuentaOut(BaseSchema):
    paciente_id: int
    saldo: Dinero
    movimientos: list[MovimientoOut]


__all__ = ["AnulacionIn", "CuentaOut", "MovimientoOut"]
