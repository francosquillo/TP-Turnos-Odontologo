"""Cliente WhatsApp real/mock + fallback email/SMS stub (C-06, D-07, RN-NO-03).

Mismo contrato en ambas implementaciones: `enviar(destinatario, plantilla,
variables) -> ResultadoEnvio`. `WHATSAPP_MOCK=true` (default) simula sin HTTP
para la demo local; `false` exige TOKEN+PHONE_ID (fail-fast en arranque) y
pega a Graph API con timeout 10 s. Costo real: ref visible 0.026 USD por
`enviada` (constante COSTO_META_USD_REF; actualizar si Meta cambia).

Fallback stub (post-TP con proveedor real): responde enviada con costo 0 y
`via_fallback=True`; la orquestacion (3 intentos + mutacion de canal en la
misma fila) vive en `notificacion_servicio.enviar_con_reintentos`.

NUNCA PHI en logs: solo ultimos 4 digitos del destinatario.
"""
import logging
import uuid
from dataclasses import dataclass, field

# Ref visible: costo por mensaje enviado en la API real (USD).
COSTO_META_USD_REF = 0.026
TIMEOUT_SEG = 10

_log = logging.getLogger(__name__)


class ConfiguracionWhatsAppError(ValueError):
    """Creds ausentes con WHATSAPP_MOCK=false (fail-fast, se mapea a 500)."""


class EnvioFallidoError(ConnectionError):
    """El envio no llego (timeout, 4xx/5xx de Meta, red caida)."""


@dataclass
class ResultadoEnvio:
    estado: str  # enviada | fallida
    message_id: str | None = None
    costo: float = 0.0
    via_fallback: bool = False


def enmascarar_ref(destinatario: str | None) -> str:
    """Ultimos 4 digitos para logs (NUNCA el numero completo)."""
    digitos = "".join(c for c in str(destinatario or "") if c.isdigit())
    return f"***{digitos[-4:]}" if digitos else "***"


class MockWhatsAppCliente:
    """Simula el envio sin HTTP (demo local y C-07 desde el dia uno)."""

    def __init__(self) -> None:
        self.envios: list[dict] = []

    async def enviar(
        self, destinatario: str, plantilla: str, variables: dict
    ) -> ResultadoEnvio:
        self.envios.append(
            {"destinatario": destinatario, "plantilla": plantilla,
             "variables": dict(variables)}
        )
        _log.info(
            "whatsapp mock a %s plantilla %s",
            enmascarar_ref(destinatario), plantilla,
        )
        return ResultadoEnvio(
            estado="enviada", message_id=f"mock-{uuid.uuid4()}", costo=0.0
        )


class MetaCliente:
    """Pega a la Graph API de Meta (solo con creds reales por env)."""

    def __init__(self, token: str, phone_id: str) -> None:
        if not (token or "").strip() or not (phone_id or "").strip():
            raise ConfiguracionWhatsAppError(
                "WHATSAPP_MOCK=false exige WHATSAPP_TOKEN + WHATSAPP_PHONE_ID"
            )
        self._token = token
        self._phone_id = phone_id
        self.api_version = "v19.0"

    async def enviar(
        self, destinatario: str, plantilla: str, variables: dict
    ) -> ResultadoEnvio:
        import httpx

        url = (
            f"https://graph.facebook.com/{self.api_version}/"
            f"{self._phone_id}/messages"
        )
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SEG) as http:
                resp = await http.post(
                    url,
                    json={
                        "messaging_product": "whatsapp",
                        "to": destinatario,
                        "type": "template",
                        "template": {"name": plantilla, "language": {"code": "es_AR"}},
                    },
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=TIMEOUT_SEG,
                )
                resp.raise_for_status()
                message_id = (resp.json().get("messages") or [{}])[0].get("id")
        except Exception as exc:
            _log.warning(
                "whatsapp real fallo a %s: %s",
                enmascarar_ref(destinatario), type(exc).__name__,
            )
            raise EnvioFallidoError(str(exc) or "fallo envio Meta") from exc
        return ResultadoEnvio(
            estado="enviada", message_id=message_id, costo=COSTO_META_USD_REF
        )


class EmailStubCliente:
    """Stub trazado (sin SMTP real hasta decidir proveedor post-TP)."""

    def __init__(self) -> None:
        self.envios: list[dict] = []

    async def enviar(
        self, destinatario: str, plantilla: str, variables: dict
    ) -> ResultadoEnvio:
        self.envios.append(
            {"destinatario": destinatario, "plantilla": plantilla,
             "variables": dict(variables)}
        )
        return ResultadoEnvio(
            estado="enviada", message_id=f"stub-email-{uuid.uuid4()}",
            costo=0.0, via_fallback=True,
        )


class SmsStubCliente:
    """Stub trazado (sin proveedor SMS real en v1.0)."""

    def __init__(self) -> None:
        self.envios: list[dict] = []

    async def enviar(
        self, destinatario: str, plantilla: str, variables: dict
    ) -> ResultadoEnvio:
        self.envios.append(
            {"destinatario": destinatario, "plantilla": plantilla,
             "variables": dict(variables)}
        )
        return ResultadoEnvio(
            estado="enviada", message_id=f"stub-sms-{uuid.uuid4()}",
            costo=0.0, via_fallback=True,
        )


def crear_cliente(mock: bool, token: str = "", phone_id: str = ""):
    """Fabrica por env: mock por defecto, Meta con fail-fast si mock=false."""
    if mock:
        return MockWhatsAppCliente()
    return MetaCliente(token=token, phone_id=phone_id)


__all__ = [
    "COSTO_META_USD_REF",
    "TIMEOUT_SEG",
    "ConfiguracionWhatsAppError",
    "EmailStubCliente",
    "EnvioFallidoError",
    "MetaCliente",
    "MockWhatsAppCliente",
    "ResultadoEnvio",
    "SmsStubCliente",
    "crear_cliente",
    "enmascarar_ref",
]
