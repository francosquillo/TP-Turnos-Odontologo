"""Rutas publicas reserva (C-05, D-03/D-06): sin Bearer, sin `require_role`.

`POST /reservas` crea pendiente online con token un solo uso (nunca
sobreturno, `creado_por=NULL`). `GET /confirmar/:token` (mas alias POST)
confirma via la maquina existente. Desconocido -> 404 generico; reusado,
expirado o no pendiente -> 410 (con contacto, sin exponer agenda ajena).
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.turnos import (
    PacienteRepoDep,
    ProfesionalRepoDep,
    SillonRepoDep,
    TurnoRepoDep,
)
from app.core.deps import DbDep, StoreDep
from app.esquemas.reserva import ConfirmarOut, ReservaIn, ReservaOut
from app.servicios import agenda_servicio as agenda
from app.servicios import reserva_servicio as reserva

router = APIRouter(tags=["reservas"])


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


async def _confirmar(token: str, db: DbDep, turnos: TurnoRepoDep, tienda: StoreDep):
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
    return ConfirmarOut(
        estado=turno.estado,
        inicio=turno.inicio,
        fin=turno.fin,
        profesional_id=turno.profesional_id,
    )


@router.get("/confirmar/{token}")
async def confirmar_reserva(token: str, db: DbDep, turnos: TurnoRepoDep, tienda: StoreDep):
    """Confirma en 1 clic (link de WhatsApp/mail hace GET, US-011)."""
    return await _confirmar(token, db, turnos, tienda)


@router.post("/confirmar/{token}")
async def confirmar_reserva_post(token: str, db: DbDep, turnos: TurnoRepoDep, tienda: StoreDep):
    """Alias programatico con identica logica (D-06)."""
    return await _confirmar(token, db, turnos, tienda)


__all__ = ["router"]
