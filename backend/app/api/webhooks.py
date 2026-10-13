"""Webhook WhatsApp (C-06, D-05, RN-AU-04, RN-TU-03).

Ruta publica SIN Bearer (Meta no tiene nuestro JWT) pero CON HMAC-SHA256 del
cuerpo crudo usando WHATSAPP_WEBHOOK_SECRET: sin firma o firma invalida ->
401 + log estructurado (ip + motivo, NUNCA cuerpo ni telefono). El cuerpo se
lee con `request.body()` ANTES de Pydantic para no romper la firma.

Eventos: `respuesta_paciente` (vocabulario cerrado SI/NO, resolucion
2026-10-13: NO cancela directo con motivo auditado; lo no reconocido -> 200
sin mutar + aviso) actualiza el turno via `cambiar_estado` (sin SQL directo);
`estado_mensaje` actualiza solo la Notificacion sin tocar el turno.
"""
import hashlib
import hmac
import logging
import unicodedata

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError
from typing import Annotated

from fastapi import Depends

from app.api.notificaciones import NotifRepoDep
from app.api.turnos import PacienteRepoDep, TurnoRepoDep
from app.core.deps import DbDep, SettingsDep, StoreDep
from app.esquemas.webhook import (
    AdaptadorWebhook,
    EstadoMensajeIn,
    RespuestaPacienteIn,
)
from app.servicios import agenda_servicio as agenda
from app.servicios import notificacion_servicio as notif_svc
from app.servicios.whatsapp_cliente import crear_cliente

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_log = logging.getLogger(__name__)

# Vocabulario cerrado normalizado (resolucion P3-A v1.0 demo).
SI_VOCABULARIO = frozenset({"si", "confirmo", "confirmar"})
NO_VOCABULARIO = frozenset({"no", "cancelo", "cancelar"})
_MAP_ESTADO = {
    "sent": "enviada",
    "delivered": "entregada",
    "read": "leída",
    "failed": "fallida",
}


def normalizar_texto(texto: str) -> str:
    """Minusculas sin tildes ni espacios (vocabulario cerrado)."""
    bajo = unicodedata.normalize("NFD", texto.lower().strip())
    return "".join(c for c in bajo if unicodedata.category(c) != "Mn").strip()


def firmar(cuerpo: bytes, secreto: str) -> str:
    """Firma esperada `sha256=<hex>` del cuerpo crudo (RN-AU-04)."""
    return "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


def get_cliente_whatsapp(settings: SettingsDep):
    """Cliente segun env (mock default; Meta con fail-fast)."""
    return crear_cliente(
        settings.whatsapp_mock,
        token=settings.whatsapp_token,
        phone_id=settings.whatsapp_phone_id,
    )


ClienteDep = Annotated[object, Depends(get_cliente_whatsapp)]


def _no_autorizado(request: Request, motivo: str) -> JSONResponse:
    _log.warning(
        "webhook whatsapp rechazado: %s desde %s",
        motivo,
        request.client.host if request.client else "?",
    )
    return JSONResponse(status_code=401, content={"detail": "firma invalida"})


@router.get("/whatsapp")
async def verificar_challenge(request: Request, settings: SettingsDep):
    """Challenge de verificacion de Meta (token por env)."""
    # FastAPI mapea hub.mode -> hub_mode solo con alias; se lee el query crudo
    # para no depender del nombre del parametro.
    query = dict(request.query_params)
    modo = query.get("hub.mode")
    token = query.get("hub.verify_token")
    challenge = query.get("hub.challenge", "")
    if (
        modo == "subscribe"
        and token
        and hmac.compare_digest(token, settings.whatsapp_webhook_secret)
    ):
        return PlainTextResponse(challenge or "")
    raise HTTPException(status_code=403, detail="verificacion invalida")


@router.post("/whatsapp")
async def recibir_evento(
    request: Request,
    settings: SettingsDep,
    db: DbDep,
    turnos: TurnoRepoDep,
    notifs: NotifRepoDep,
    pacientes: PacienteRepoDep,
    tienda: StoreDep,
    cliente: ClienteDep,
):
    """Procesa un evento firmado de WhatsApp (respuesta o estado)."""
    secreto = settings.whatsapp_webhook_secret
    if not secreto:
        raise HTTPException(status_code=500, detail="webhook no configurado")
    cuerpo = await request.body()
    firma = request.headers.get("X-Hub-Signature-256", "")
    if not firma or not hmac.compare_digest(firma, firmar(cuerpo, secreto)):
        await db.rollback()
        return _no_autorizado(request, "sin_firma" if not firma else "firma_invalida")
    try:
        import json

        datos = AdaptadorWebhook.validate_python(json.loads(cuerpo or b"{}"))
    except (ValidationError, ValueError):
        await db.rollback()
        raise HTTPException(status_code=422, detail="evento invalido") from None
    if isinstance(datos, EstadoMensajeIn):
        return await _evento_estado(db, notifs, datos)
    return await _evento_respuesta(
        db, turnos, notifs, pacientes, tienda, cliente, datos
    )


async def _evento_estado(db, notifs, datos: EstadoMensajeIn):
    fila = await notifs.por_message_id(datos.message_id)
    if fila is None:
        return JSONResponse(status_code=200, content={"detail": "desconocido"})
    cambios: dict = {"estado": _MAP_ESTADO[datos.estado]}
    if datos.estado == "failed":
        cambios["ultimo_error"] = "entrega_fallida_meta"
    await notifs.actualizar(fila, **cambios)
    await db.commit()
    return {"detail": "actualizado", "estado": cambios["estado"]}


async def _evento_respuesta(
    db, turnos, notifs, pacientes, tienda, cliente, datos: RespuestaPacienteIn
):
    turno = await turnos.get(datos.turno_id)
    if turno is None:
        await db.rollback()
        raise HTTPException(status_code=404, detail="turno inexistente")
    texto = normalizar_texto(datos.texto)
    if texto in SI_VOCABULARIO:
        return await _responder_si(
            db, turnos, notifs, pacientes, tienda, cliente, turno)
    if texto in NO_VOCABULARIO:
        return await _responder_no(db, turnos, turno)
    _log.warning(
        "webhook respuesta no reconocida turno %s (aviso secretaria)",
        turno.id,
    )
    return JSONResponse(status_code=200, content={"detail": "no_reconocida"})


async def _responder_si(db, turnos, notifs, pacientes, tienda, cliente, turno):
    if turno.estado == "pendiente":
        try:
            turno = await agenda.cambiar_estado(turnos, turno.id, "confirmado")
        except (agenda.TransicionInvalidaError, ValueError) as exc:
            await db.rollback()
            raise HTTPException(status_code=422, detail=str(exc)) from None
        paciente = await pacientes.get(turno.paciente_id)
        nombre = str(getattr(paciente, "nombre", "") or "").split()
        email = getattr(paciente, "email", None) if paciente else None
        await notif_svc.encolar_confirmacion(
            notifs, tienda, turno,
            nombre_pila=nombre[0] if nombre else "paciente",
            cliente=cliente, email=email,
        )
        await db.commit()
        return {"detail": "confirmado"}
    # Confirmado o terminal: idempotente, 200 sin mutar (doulbe SI incluido).
    return JSONResponse(
        status_code=200,
        content={"detail": "ya_confirmado" if turno.estado == "confirmado"
                 else "sin_cambios"},
    )


async def _responder_no(db, turnos, turno):
    if turno.estado in ("pendiente", "confirmado"):
        try:
            await agenda.cambiar_estado(
                turnos, turno.id, "cancelado", motivo="respuesta_paciente")
        except (agenda.TransicionInvalidaError, ValueError) as exc:
            await db.rollback()
            raise HTTPException(status_code=422, detail=str(exc)) from None
        await db.commit()
        return {"detail": "cancelado"}
    return JSONResponse(status_code=200, content={"detail": "sin_cambios"})


__all__ = [
    "router",
    "firmar",
    "get_cliente_whatsapp",
    "normalizar_texto",
]
