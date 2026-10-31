"""Esquemas base: estrictos por defecto (extra='forbid', regla dura)."""
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _dinero_a_texto(valor: Decimal) -> str:
    return f"{valor:.2f}"


# Importes: Decimal en memoria, texto con 2 decimales en JSON (C-09, D-21).
Dinero = Annotated[
    Decimal, PlainSerializer(_dinero_a_texto, return_type=str, when_used="json")
]
