"""Esquemas webhook WhatsApp: estrictos (extra='forbid', regla dura).

El cuerpo crudo se preserva para el HMAC: la ruta lee `request.body()` ANTES
de validar con estos esquemas (D-05). Union discriminada por `evento`.
"""
from typing import Annotated, Literal, Union

from pydantic import Field, TypeAdapter

from app.esquemas.base import BaseSchema


class RespuestaPacienteIn(BaseSchema):
    evento: Literal["respuesta_paciente"]
    turno_id: int
    texto: str = Field(min_length=1, max_length=50)


class EstadoMensajeIn(BaseSchema):
    evento: Literal["estado_mensaje"]
    message_id: str = Field(min_length=1, max_length=128)
    estado: Literal["sent", "delivered", "read", "failed"]


WebhookIn = Annotated[
    Union[RespuestaPacienteIn, EstadoMensajeIn], Field(discriminator="evento")
]

AdaptadorWebhook = TypeAdapter(WebhookIn)


__all__ = ["AdaptadorWebhook", "EstadoMensajeIn", "RespuestaPacienteIn", "WebhookIn"]
