"""GET /disponibilidad: huecos = agenda_config − turnos activos (C-04, D-04).

C-05 (D-04): gana rama publica SIN auth en este mismo router: ejecuta el
mismo `calcular_huecos` y devuelve solo [{inicio, fin}] (HuecoOut, sin datos
de pacientes), exigiendo siempre `profesional_id`. La rama staff con Bearer
conserva RBAC y comportamiento. Desvio documentado del delta-spec: anonimo
sin profesional_id -> 422 (nunca vuelca la agenda completa) en vez de 401.
"""
from datetime import datetime

from fastapi import HTTPException

from app.api.turnos import (
    ProfesionalRepoDep,
    SillonRepoDep,
    TurnoRepoDep,
)
from app.core.deps import BearerDep, RepoDep, get_current_user
from app.esquemas.turno import HuecoOut
from app.servicios import agenda_servicio as svc

from fastapi import APIRouter

router = APIRouter(prefix="/disponibilidad", tags=["disponibilidad"])

_ROLES_LECTURA = ("admin", "secretaria", "odontologo")


async def _huecos(
    turnos: TurnoRepoDep,
    profesionales: ProfesionalRepoDep,
    sillones: SillonRepoDep,
    profesional_id: int,
    desde: datetime,
    hasta: datetime,
    sillon_id: int | None,
    duracion_min: int | None,
) -> list[HuecoOut]:
    """Calculo compartido por ambas ramas (mismos huecos, D-04)."""
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


@router.get("")
async def ver_disponibilidad(
    credenciales: BearerDep,
    usuarios: RepoDep,
    turnos: TurnoRepoDep,
    profesionales: ProfesionalRepoDep,
    sillones: SillonRepoDep,
    desde: datetime,
    hasta: datetime,
    profesional_id: int | None = None,
    sillon_id: int | None = None,
    duracion_min: int | None = None,
) -> list[HuecoOut]:
    """Huecos ofrecibles en [desde, hasta): staff con Bearer, publica sin el."""
    usuario = None
    if credenciales is not None and credenciales.credentials:
        usuario = await get_current_user(usuarios, credenciales)
        if getattr(getattr(usuario, "rol", None), "nombre", None) not in _ROLES_LECTURA:
            raise HTTPException(status_code=403, detail="sin permiso")
    if usuario is None and profesional_id is None:
        # Rama publica: nunca "toda la agenda sin filtro" (RN-TU-05).
        raise HTTPException(status_code=422, detail="profesional_id requerido")
    return await _huecos(
        turnos, profesionales, sillones, profesional_id,  # type: ignore[arg-type]
        desde, hasta, sillon_id, duracion_min,
    )


__all__ = ["router"]
