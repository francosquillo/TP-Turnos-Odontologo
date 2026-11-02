"""Esquemas Usuario: estrictos (extra='forbid', D-07), sin password en response."""
from typing import Annotated, Literal

from pydantic import StringConstraints, field_validator

from app.esquemas.base import BaseSchema


class UsuarioCreate(BaseSchema):
    nombre: str
    email: str
    password: str
    rol_id: int


class UsuarioResponse(BaseSchema):
    id: int
    nombre: str
    email: str
    rol_id: int
    activo: bool


class UsuarioAdminOut(BaseSchema):
    """Fila del listado admin: con nombre de rol, sin hash (C-03)."""

    id: int
    nombre: str
    email: str
    rol: str
    activo: bool


# --- C-12 (D-02): alta y edicion por admin ---------------------------------------------------------

RolNombre = Literal["admin", "odontologo", "secretaria"]
_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Email = Annotated[str, StringConstraints(strip_whitespace=True, pattern=_EMAIL, max_length=320)]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class UsuarioAltaIn(BaseSchema):
    nombre: Nombre
    email: Email
    password: Password
    rol: RolNombre


class UsuarioEdicionIn(BaseSchema):
    """Campos opcionales: uno ausente no cambia. `activo` solo admite `true` (reactivar)."""

    nombre: Nombre | None = None
    rol: RolNombre | None = None
    activo: bool | None = None
    password: Password | None = None

    @field_validator("activo")
    @classmethod
    def _solo_reactivar(cls, valor: bool | None) -> bool | None:
        if valor is False:
            raise ValueError("para desactivar usá PATCH /admin/usuarios/{id}/desactivar")
        return valor
