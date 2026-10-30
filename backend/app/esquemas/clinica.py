"""Esquemas clínicos: historia clínica, odontograma, catálogos (C-08, D-02/D-03/D-08).

Todos estrictos (`extra='forbid'`). El cliente NO envía `profesional_id`,
`fecha` ni `catalogo_version`: los fija el servidor. `alergias` vacías se
normalizan a `None` ("no relevadas", distinto de "sin alergias conocidas").
"""
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, Field, model_validator

from app.esquemas.base import BaseSchema

Cara = Literal[
    "oclusal", "mesial", "distal", "vestibular", "palatina", "lingual",
    "raiz", "pieza_completa",
]
Alcance = Literal["cualquiera", "pieza"]


def es_pieza_fdi(pieza: int) -> bool:
    """FDI permanente exacto: 11-18, 21-28, 31-38, 41-48 (no el rango 11-48)."""
    return 11 <= pieza <= 48 and 1 <= pieza % 10 <= 8


def _validar_pieza(pieza: int) -> int:
    if not es_pieza_fdi(pieza):
        raise ValueError("pieza_fdi debe ser 11-18, 21-28, 31-38 o 41-48")
    return pieza


PiezaFdi = Annotated[int, AfterValidator(_validar_pieza)]


def cara_compatible_con_pieza(pieza: int, cara: str) -> bool:
    """`palatina` solo en superiores (1x, 2x); `lingual` solo en inferiores (3x, 4x)."""
    if cara == "palatina":
        return pieza < 30
    if cara == "lingual":
        return pieza >= 30
    return True


def _texto_acotado(maximo: int):
    """Recorta, normaliza vacío a None y acota el largo (mismo límite que el CHECK)."""

    def _validar(valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip()
        if len(valor) > maximo:
            raise ValueError(f"máximo {maximo} caracteres")
        return valor or None

    return _validar


def _motivo(valor: str) -> str:
    valor = valor.strip()
    if not valor:
        raise ValueError("el motivo no puede estar vacío")
    return valor


Antecedentes = Annotated[str | None, AfterValidator(_texto_acotado(10000))]
Alergias = Annotated[str | None, AfterValidator(_texto_acotado(2000))]
Motivo = Annotated[str, Field(min_length=1, max_length=500), AfterValidator(_motivo)]


class HistoriaIn(BaseSchema):
    paciente_id: int
    antecedentes: Antecedentes = None
    alergias: Alergias = None


class HistoriaPatch(BaseSchema):
    """Solo se aplican los campos enviados (`exclude_unset`)."""

    antecedentes: Antecedentes = None
    alergias: Alergias = None


class BajaIn(BaseSchema):
    motivo_baja: Motivo


class HistoriaOut(BaseSchema):
    id: int
    paciente_id: int
    antecedentes: str | None
    alergias: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    motivo_baja: str | None


class TratamientoOut(BaseSchema):
    id: int
    codigo: str
    codigo_nomenclador: str | None
    nombre: str
    precio_base: Decimal


class _HallazgoBase(BaseSchema):
    pieza_fdi: PiezaFdi
    cara: Cara
    estado: Annotated[str, Field(min_length=1, max_length=50)]

    @model_validator(mode="after")
    def _cara_de_la_arcada(self) -> Self:
        if not cara_compatible_con_pieza(self.pieza_fdi, self.cara):
            raise ValueError(
                f"la cara {self.cara} no existe en la pieza {self.pieza_fdi}"
            )
        return self


class HallazgoIn(_HallazgoBase):
    pass


class HallazgoCorreccionIn(_HallazgoBase):
    motivo: Motivo


class HallazgoOut(BaseSchema):
    id: int
    hc_id: int
    pieza_fdi: int
    cara: str
    estado: str
    catalogo_version: int
    fecha: datetime
    profesional_id: int
    corrige_a_id: int | None
    deleted_at: datetime | None
    motivo_baja: str | None
    # Derivado en el servidor (no es columna): True si quien consulta es el autor.
    # La SPA no conoce su profesional_id; solo el autor corrige o da de baja (D-07).
    es_propio: bool


class HallazgoConAlergias(BaseSchema):
    alergias: str | None
    hallazgo: HallazgoOut


class HallazgosConAlergias(BaseSchema):
    alergias: str | None
    hallazgos: list[HallazgoOut]


class EstadoCatalogoOut(BaseSchema):
    codigo: str
    nombre: str
    alcance: Alcance


class CatalogoOut(BaseSchema):
    version: int
    estados: list[EstadoCatalogoOut]


__all__ = [
    "Alcance", "BajaIn", "CatalogoOut", "Cara", "EstadoCatalogoOut",
    "HallazgoConAlergias", "HallazgoCorreccionIn", "HallazgoIn", "HallazgoOut",
    "HallazgosConAlergias", "HistoriaIn", "HistoriaOut", "HistoriaPatch",
    "PiezaFdi", "TratamientoOut", "cara_compatible_con_pieza", "es_pieza_fdi",
]
