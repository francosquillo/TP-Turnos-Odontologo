"""GET /disponibilidad: huecos = agenda_config − turnos activos (C-04, D-04).

Reutilizable por C-05 tal cual para la reserva publica. RBAC staff lectura.
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.api.turnos import (
    LecturaDep,
    ProfesionalRepoDep,
    SillonRepoDep,
    TurnoRepoDep,
)
from app.esquemas.turno import HuecoOut
from app.servicios import agenda_servicio as svc

router = APIRouter(prefix="/disponibilidad", tags=["disponibilidad"])


@router.get("")
async def ver_disponibilidad(
    _usuario: LecturaDep,
    turnos: TurnoRepoDep,
    profesionales: ProfesionalRepoDep,
    sillones: SillonRepoDep,
    profesional_id: int,
    desde: datetime,
    hasta: datetime,
    sillon_id: int | None = None,
    duracion_min: int | None = None,
) -> list[HuecoOut]:
    """Huecos ofrecibles del profesional en [desde, hasta)."""
    profesional = await profesionales.get(profesional_id)
    if profesional is None:
        raise HTTPException(status_code=404, detail="profesional inexistente")
    if sillon_id is not None and await sillones.get(sillon_id) is None:
        raise HTTPException(status_code=404, detail="sillon inexistente")
    ocupados_raw = await turnos.activos_en_rango(
        desde, hasta, profesional_id=profesional_id, sillon_id=sillon_id
    )
    huecos = svc.calcular_huecos(
        getattr(profesional, "agenda_config", None) or {},
        desde,
        hasta,
        [(t.inicio, t.fin) for t in ocupados_raw],
        duracion_min,
    )
    return [HuecoOut(inicio=ini, fin=fin) for ini, fin in huecos]


__all__ = ["router"]
