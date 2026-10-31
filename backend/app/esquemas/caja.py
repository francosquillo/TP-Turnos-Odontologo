"""Esquemas de caja y recibos (C-10, D-03, D-08, D-12, D-17, D-25).

Todos estrictos (`extra='forbid'`). El cliente NO envía fecha, paciente, totales del
sistema ni diferencia: los calcula el servidor. Los importes viajan como texto con
2 decimales (`Dinero`). La `clave_idempotencia` es un UUID v4 en minúsculas, obligatoria
en el cuerpo del cobro y nunca devuelta por ninguna respuesta.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field

from app.esquemas.base import BaseSchema, Dinero
from app.esquemas.clinica import Motivo
from app.modelos.caja import CLAVE_REGEX

MedioPago = Literal["efectivo", "transferencia", "tarjeta_simulada"]
Bloqueo = Literal["caja_pendiente", "caja_cerrada"]

ClaveIdempotencia = Annotated[str, Field(pattern=CLAVE_REGEX)]
# Positivo, dos decimales y dentro de NUMERIC(16,2); nunca NaN ni infinito.
MontoCobro = Annotated[Decimal, Field(gt=0, max_digits=16, decimal_places=2)]
TotalContado = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]


class CobroIn(BaseSchema):
    presupuesto_id: int
    monto: MontoCobro
    medio: MedioPago
    clave_idempotencia: ClaveIdempotencia


class CierreIn(BaseSchema):
    caja_id: int
    total_contado: TotalContado
    motivo_diferencia: Motivo | None = None


class AnulacionReciboIn(BaseSchema):
    motivo: Motivo


class ReciboOut(BaseSchema):
    id: int
    numero: int
    paciente_id: int
    paciente_nombre: str
    monto: Dinero
    medio: MedioPago
    fecha: date
    emitido_por: int
    created_at: datetime
    anulado: bool
    motivo_anulacion: str | None
    anulado_por: int | None
    anulado_at: datetime | None


class CobroOut(ReciboOut):
    presupuesto_id: int
    presupuesto_estado: str


class CajaOut(BaseSchema):
    id: int
    fecha: date
    estado: Literal["abierta", "cerrada"]
    abierta_por: int
    total_sistema: Dinero
    total_contado: Dinero | None
    diferencia: Dinero | None
    motivo_diferencia: str | None
    cerrada_por: int | None
    cerrada_at: datetime | None


class DesgloseMedioOut(BaseSchema):
    medio: MedioPago
    subtotal: Dinero


class EstadoCajaOut(BaseSchema):
    fecha: date
    hoy: date
    operable: bool
    bloqueo: Bloqueo | None
    caja: CajaOut | None
    desglose: list[DesgloseMedioOut]


__all__ = [
    "AnulacionReciboIn", "CajaOut", "CierreIn", "CobroIn", "CobroOut", "DesgloseMedioOut",
    "EstadoCajaOut", "ReciboOut",
]
