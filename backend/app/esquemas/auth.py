"""Esquemas /auth: estrictos (extra='forbid'), sin hash en ningun response."""
from app.esquemas.base import BaseSchema


class LoginIn(BaseSchema):
    email: str
    password: str


class TokenOut(BaseSchema):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseSchema):
    id: int
    email: str
    nombre: str
    rol: str
