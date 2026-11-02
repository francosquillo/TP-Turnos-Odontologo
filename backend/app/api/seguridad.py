"""Router publico GET /seguridad (C-12, D-05, US-052).

Sin auth y sin I/O (`def` sincrono): arma los hechos desde `get_settings()` y desde lo que el
codigo realmente tiene. No afirma nada que el sistema no cumpla (p. ej. cifrado en reposo).
"""
from importlib.util import find_spec

from fastapi import APIRouter

from app.core.config import Settings, get_settings
from app.esquemas.seguridad import SeguridadOut
from app.modelos import Base

router = APIRouter(prefix="/seguridad", tags=["seguridad"])

DECLARACION = (
    "Todos los datos de esta demostración son ficticios y de prueba. "
    "No se cargan ni se guardan datos reales de pacientes."
)
CIFRADO = (
    "Cifrado en tránsito y en reposo: pendiente para producción (RN-GL-03); "
    "el despliegue v1.0 es local."
)
GCAL_NOTA = (
    "Google Calendar no sincroniza turnos en esta versión: solo se informa si hay "
    "credenciales configuradas."
)


def _credencial_real(valor: str) -> bool:
    """Una variable vacia o con el placeholder del `.env.example` no cuenta como configurada."""
    return bool(valor) and not valor.startswith("CHANGEME")


def _auditoria() -> list[str]:
    hechos = [
        "Sobreturnos: quién lo autorizó y el motivo.",
        "Anulaciones de recibos y de cobros: quién y con qué motivo.",
        "Cambios de aranceles: quién creó y quién cerró cada vigencia.",
    ]
    if "evento_auditoria" in Base.metadata.tables:
        hechos.append("Acciones de administración sobre usuarios y datos (registro que no se puede modificar).")
    return hechos


def _respaldos() -> list[str]:
    hechos = ["Los datos viven en un volumen Docker local; no hay respaldo automático externo."]
    if find_spec("app.servicios.exportacion_servicio") is not None:
        hechos.append("El administrador puede descargar una exportación total en CSV.")
    return hechos


def armar_seguridad(settings: Settings) -> SeguridadOut:
    return SeguridadOut(
        datos_ficticios=True,
        declaracion=DECLARACION,
        hash_contrasenas="argon2",
        access_token_min=settings.jwt_expire_min,
        refresh_rotativo=True,
        whatsapp_modo="mock" if settings.whatsapp_mock else "real",
        whatsapp_sin_datos_clinicos=True,
        google_calendar_habilitado=_credencial_real(settings.gcal_client_id)
        and _credencial_real(settings.gcal_secret),
        google_calendar_nota=GCAL_NOTA,
        auditoria=_auditoria(),
        respaldos=_respaldos(),
        cifrado=CIFRADO,
    )


@router.get("")
def obtener_seguridad() -> SeguridadOut:
    """Hechos de seguridad verificables contra la configuracion vigente."""
    return armar_seguridad(get_settings())


__all__ = ["router", "armar_seguridad"]
