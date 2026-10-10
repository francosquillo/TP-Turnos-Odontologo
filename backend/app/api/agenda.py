"""GET /agenda: turnos del periodo por vista dia|semana|mes (C-04, US-001).

RBAC staff lectura; odontologo ve sus turnos propios. Vista invalida -> 422.
"""
from datetime import date
from typing import Literal

from fastapi import APIRouter

from app.api.turnos import (
    LecturaDep,
    PacienteRepoDep,
    ProfesionalRepoDep,
    SillonRepoDep,
    TurnoRepoDep,
    _es_odontologo,
    _profesional_propio_id,
)
from app.esquemas.turno import AgendaItemOut
from app.servicios import agenda_servicio as svc

router = APIRouter(prefix="/agenda", tags=["agenda"])

VistaAgenda = Literal["dia", "semana", "mes"]


@router.get("")
async def ver_agenda(
    usuario: LecturaDep,
    turnos: TurnoRepoDep,
    pacientes: PacienteRepoDep,
    profesionales: ProfesionalRepoDep,
    sillones: SillonRepoDep,
    vista: VistaAgenda,
    fecha: date,
    profesional_id: int | None = None,
    sillon_id: int | None = None,
    incluir_cancelados: bool = False,
) -> list[AgendaItemOut]:
    """Turnos del periodo ordenados por inicio con nombres para la UI."""
    if _es_odontologo(usuario):
        profesional_id = await _profesional_propio_id(profesionales, usuario)
        if profesional_id is None:
            return []
    desde, hasta = svc.rango_vista(vista, fecha)
    filas = await turnos.listar_periodo(
        desde, hasta,
        profesional_id=profesional_id, sillon_id=sillon_id,
        solo_activos=not incluir_cancelados,
    )
    salida: list[AgendaItemOut] = []
    for turno in filas:
        paciente = await pacientes.get(turno.paciente_id)
        profesional = await profesionales.get(turno.profesional_id)
        sillon = await sillones.get(turno.sillon_id)
        nombre_paciente = None
        if paciente is not None:
            nombre_paciente = (
                f"{getattr(paciente, 'nombre', '')} {getattr(paciente, 'apellido', '')}".strip()
                or None
            )
        salida.append(
            AgendaItemOut(
                id=turno.id,
                inicio=turno.inicio,
                fin=turno.fin,
                estado=turno.estado,
                paciente_id=turno.paciente_id,
                paciente_nombre=nombre_paciente,
                profesional_id=turno.profesional_id,
                profesional_matricula=getattr(profesional, "matricula", None),
                sillon_id=turno.sillon_id,
                sillon_nombre=getattr(sillon, "nombre", None),
            )
        )
    return salida


__all__ = ["router"]
