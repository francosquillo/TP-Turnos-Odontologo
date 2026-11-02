"""Cobertura de obra social: regla pura y validador (C-11, D-04, D-16).

`calcular_cobertura` es la única fórmula: la usan el validador y `aceptar`, así lo que se
muestra y lo que se congela no pueden divergir. `arancel.precio` es lo que la OS paga por
unidad; el tope al precio evita que la cobertura supere el cargo.

Solo lee (el validador NO crea filas). Sin logs. Mensajes de error fijos.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_CENTAVOS = Decimal("0.01")
_CIEN = Decimal("100")


@dataclass(frozen=True)
class Cobertura:
    cubierto: Decimal
    a_cargo: Decimal
    porcentaje: Decimal


def _dos(valor: Decimal) -> Decimal:
    return valor.quantize(_CENTAVOS, rounding=ROUND_HALF_UP)


def calcular_cobertura(arancel: Decimal | None, precio: Decimal, cantidad: int = 1) -> Cobertura:
    """`cubierto = min(arancel, precio) x cantidad`; `a_cargo = precio x cantidad - cubierto`."""
    if precio < 0 or (arancel is not None and arancel < 0):
        raise ValueError("los importes no pueden ser negativos")
    total = _dos(precio * cantidad)
    if arancel is None:
        return Cobertura(Decimal("0.00"), total, Decimal("0.00"))
    cubierto = _dos(min(arancel, precio) * cantidad)
    porcentaje = Decimal("0.00") if total == 0 else _dos(cubierto * _CIEN / total)
    return Cobertura(cubierto, _dos(total - cubierto), porcentaje)


__all__ = ["Cobertura", "calcular_cobertura"]
