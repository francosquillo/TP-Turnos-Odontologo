"""Rutas publicas reserva (C-05, D-03/D-06): sin Bearer, sin `require_role`.

`POST /reservas` crea pendiente online con token un solo uso (nunca
sobreturno, `creado_por=NULL`). `GET /confirmar/:token` (mas alias POST)
confirma via la maquina existente. Desconocido -> 404 generico; reusado,
expirado o no pendiente -> 410 (con contacto, sin exponer agenda ajena).

C-06 task 6.1: confirmar con exito encola la plantilla `confirmacion` como
efecto lateral aditivo y best-effort (nunca cambia el 200/404/410).
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.turnos import (
    PacienteRepoDep,
    ProfesionalRepoDep,
    SillonRepoDep,
    TurnoRepoDep,
)
from app.api.webhooks import ClienteDep
from app.core.deps import DbDep, StoreDep
from app.esquemas.reserva import ConfirmarOut, ReservaIn, ReservaOut
from app.repos.notificacion_repo import NotificacionRepository
from app.servicios import agenda_servicio as agenda
from app.servicios import reserva_servicio as reserva

router = APIRouter(tags=["reservas"])

_log = logging.getLogger(__name__)


def get_notif_repo_reserva(db: DbDep) -> NotificacionRepository:
    """Repo notificaciones sobre la sesion del request (overridible en tests)."""
    return NotificacionRepository(db)


NotifReservaDep = Annotated[NotificacionRepository, Depends(get_notif_repo_reserva)]


def _conflicto(error: agenda.HuecoOcupadoError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "detail": "hueco ocupado",
            "alternativas": [
                {"inicio": ini.isoformat(), "fin": fin.isoformat()}
                for ini, fin in error.alternativas
            ],
        },
    )


def _no_confirmable(status: int, detail: str, contacto: str | None = None) -> JSONResponse:
    contenido: dict[str, str] = {"detail": detail}
    if contacto:
        contenido["contacto"] = contacto
    return JSONResponse(status_code=status, content=contenido)


@router.post("/reservas", status_code=201)
async def crear_reserva_publica(
    datos: ReservaIn,
    db: DbDep,
    turnos: TurnoRepoDep,
    pacientes: PacienteRepoDep,
    profesionales: ProfesionalRepoDep,
    sillones: SillonRepoDep,
) -> ReservaOut:
    """Crea un turno pendiente online + token (201, token una unica vez)."""
    try:
        resultado = await reserva.crear_reserva(
            turnos,
            pacientes,
            profesionales,
            sillones,
            profesional_id=datos.profesional_id,
            sillon_id=datos.sillon_id,
            inicio=datos.inicio,
            fin=datos.fin,
            nombre=datos.nombre,
            telefono=datos.telefono,
            dni=datos.dni,
            email=datos.email,
        )
    except agenda.HuecoOcupadoError as exc:
        await db.rollback()
        return _conflicto(exc)  # type: ignore[return-value]
    except agenda.EntidadNoEncontradaError as exc:
        await db.rollback()
        return JSONResponse(status_code=422, content={"detail": str(exc)})  # type: ignore[return-value]
    except (
        reserva.TelefonoInvalidoError,
        reserva.NombreInvalidoError,
        ValueError,
    ) as exc:
        await db.rollback()
        return JSONResponse(status_code=422, content={"detail": str(exc)})  # type: ignore[return-value]
    await db.commit()
    return ReservaOut(
        turno_id=resultado.turno.id,
        estado="pendiente",
        token=resultado.token,
        expira_en=resultado.expira_en,
    )


async def _efecto_confirmacion(db, notifs, tienda, cliente, turno, pacientes) -> None:
    """Encola `confirmacion` best-effort (C-06 6.1): nunca rompe el contrato."""
    try:
        from app.servicios import notificacion_servicio as notif_svc

        paciente = await pacientes.get(turno.paciente_id)
        nombre = str(getattr(paciente, "nombre", "") or "").split()
        email = getattr(paciente, "email", None) if paciente else None
        await notif_svc.encolar_confirmacion(
            notifs, tienda, turno,
            nombre_pila=nombre[0] if nombre else "paciente",
            cliente=cliente, email=email,
        )
    except Exception as exc:  # noqa: BLE001 - aditivo, la confirmacion ya vale
        _log.warning("efecto confirmacion omitido turno %s: %s",
                     getattr(turno, "id", "?"), type(exc).__name__)


async def _confirmar(token: str, db: DbDep, turnos: TurnoRepoDep, tienda: StoreDep,
                     pacientes: PacienteRepoDep, notifs: NotifReservaDep,
                     cliente: ClienteDep):
    """Logica compartida GET + alias POST (D-06: GET muta a proposito)."""
    try:
        turno = await reserva.confirmar_por_token(
            turnos, token, tienda_usados=tienda
        )
    except reserva.TokenDesconocidoError:
        await db.rollback()
        return _no_confirmable(404, "no encontrado")
    except reserva.TokenExpiradoError as exc:
        await db.rollback()
        return _no_confirmable(410, "token expirado", exc.contacto)
    except reserva.TokenUsadoError:
        await db.rollback()
        return _no_confirmable(
            410, "este turno ya fue confirmado", reserva.CONTACTO_CONSULTORIO
        )
    except reserva.TurnoNoConfirmableError as exc:
        await db.rollback()
        return _no_confirmable(410, str(exc), reserva.CONTACTO_CONSULTORIO)
    await db.commit()
    await _efecto_confirmacion(db, notifs, tienda, cliente, turno, pacientes)
    return ConfirmarOut(
        estado=turno.estado,
        inicio=turno.inicio,
        fin=turno.fin,
        profesional_id=turno.profesional_id,
    )


@router.get("/confirmar/{token}")
async def confirmar_reserva(token: str, db: DbDep, turnos: TurnoRepoDep, tienda: StoreDep,
                            pacientes: PacienteRepoDep, notifs: NotifReservaDep,
                            cliente: ClienteDep):
    """Confirma en 1 clic (link de WhatsApp/mail hace GET, US-011)."""
    return await _confirmar(token, db, turnos, tienda, pacientes, notifs, cliente)


@router.post("/confirmar/{token}")
async def confirmar_reserva_post(token: str, db: DbDep, turnos: TurnoRepoDep, tienda: StoreDep,
                                 pacientes: PacienteRepoDep, notifs: NotifReservaDep,
                                 cliente: ClienteDep):
    """Alias programatico con identica logica (D-06)."""
    return await _confirmar(token, db, turnos, tienda, pacientes, notifs, cliente)


__all__ = ["router"]
