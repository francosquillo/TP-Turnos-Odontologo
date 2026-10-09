"""Esquemas Usuario: estrictos (extra='forbid', D-07), sin password en response."""
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
