"""Esquema de GET /seguridad (C-12, D-05): solo hechos, nunca secretos ni datos de pacientes."""
from app.esquemas.base import BaseSchema


class SeguridadOut(BaseSchema):
    datos_ficticios: bool
    declaracion: str
    hash_contrasenas: str
    access_token_min: int
    refresh_rotativo: bool
    whatsapp_modo: str
    whatsapp_sin_datos_clinicos: bool
    google_calendar_habilitado: bool
    google_calendar_nota: str
    auditoria: list[str]
    respaldos: list[str]
    cifrado: str
