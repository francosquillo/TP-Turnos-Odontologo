"""Esquemas de la importacion de pacientes (C-12 R4, D-11): reporte por fila."""
from app.esquemas.base import BaseSchema


class ErrorFila(BaseSchema):
    """Fila rechazada: numero en el archivo (encabezado = fila 1) y motivo."""

    fila: int
    motivo: str


class ImportacionOut(BaseSchema):
    creados: int
    rechazados: int
    errores: list[ErrorFila]
