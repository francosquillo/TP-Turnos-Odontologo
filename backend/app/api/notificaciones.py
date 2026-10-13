"""Notificaciones staff (C-06, D-06): aviso de fallidas sin PHI.

`GET /notificaciones/pendientes` proyecta las filas `fallida` a
{turno_id, inicio, paciente_nombre, motivo} para que secretaria llame a mano.
Requiere rol secretaria|admin; NUNCA expone clinica ni telefonos.
"""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import DbDep, require_role
from app.esquemas.notificacion import PendienteOut
from app.modelos import Usuario
from app.repos.notificacion_repo import NotificacionRepository
from app.repos.paciente_repo import PacienteRepository
from app.repos.turno_repo import TurnoRepository

router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])

StaffDep = Annotated[Usuario, Depends(require_role("admin", "secretaria"))]


def get_notif_repo(db: DbDep) -> NotificacionRepository:
    return NotificacionRepository(db)


def get_turno_repo_notif(db: DbDep) -> TurnoRepository:
    return TurnoRepository(db)


def get_paciente_repo_notif(db: DbDep) -> PacienteRepository:
    return PacienteRepository(db)


NotifRepoDep = Annotated[NotificacionRepository, Depends(get_notif_repo)]
TurnoNotifDep = Annotated[TurnoRepository, Depends(get_turno_repo_notif)]
PacienteNotifDep = Annotated[PacienteRepository, Depends(get_paciente_repo_notif)]


@router.get("/pendientes", response_model=list[PendienteOut])
async def pendientes(
    _usuario: StaffDep,
    notifs: NotifRepoDep,
    turnos: TurnoNotifDep,
    pacientes: PacienteNotifDep,
    limit: int = 50,
    offset: int = 0,
) -> list[PendienteOut]:
    """Fallidas para llamada manual (paginado, sin PHI, RN-NO-03)."""
    limite = max(1, min(limit, 100))
    salida: list[PendienteOut] = []
    for fila in await notifs.fallidas(limit=limite, offset=max(0, offset)):
        turno = await turnos.get(fila.turno_id)
        if turno is None:
            continue
        paciente = await pacientes.get(turno.paciente_id)
        nombre = str(getattr(paciente, "nombre", "") or "").split()
        salida.append(
            PendienteOut(
                turno_id=turno.id,
                inicio=turno.inicio,
                paciente_nombre=nombre[0] if nombre else "paciente",
                motivo=fila.ultimo_error,
            )
        )
    return salida


__all__ = [
    "router",
    "get_notif_repo",
    "get_turno_repo_notif",
    "get_paciente_repo_notif",
]
