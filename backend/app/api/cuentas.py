"""Router cuentas corrientes (C-09, D-11, D-14, D-15, D-19).

Lectura: secretaria y admin. Anulación: solo admin. El odontólogo no accede. No hay
alta de movimientos, PUT ni PATCH del saldo: la única escritura es `anular`, que
crea un contramovimiento. Sin rutas de cobro (C-10). El servicio solo hace flush;
este router es dueño del commit.
"""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.clinica_comun import a_http
from app.api.presupuestos import PresupuestoReposDep
from app.core.deps import DbDep, require_role
from app.esquemas.cuenta import AnulacionIn, CuentaOut, MovimientoOut
from app.modelos import Usuario
from app.servicios import cuenta_servicio as svc

router = APIRouter(prefix="/cuentas", tags=["cuentas"])

LecturaCuentaDep = Annotated[Usuario, Depends(require_role("secretaria", "admin"))]
AnulacionCuentaDep = Annotated[Usuario, Depends(require_role("admin"))]


@router.get("/{paciente_id}")
async def obtener_cuenta(
    paciente_id: int, usuario: LecturaCuentaDep, repos: PresupuestoReposDep, db: DbDep,
) -> CuentaOut:
    """Saldo derivado y movimientos; consultar no crea filas."""
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        return await svc.obtener_cuenta(repos, actor, paciente_id)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None


@router.post("/{paciente_id}/movimientos/{movimiento_id}/anular", status_code=201)
async def anular_movimiento(
    paciente_id: int, movimiento_id: int, datos: AnulacionIn, usuario: AnulacionCuentaDep,
    repos: PresupuestoReposDep, db: DbDep,
) -> MovimientoOut:
    """Contramovimiento de un cargo con motivo (cuerpo, nunca query)."""
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        anulacion = await svc.anular_cargo(repos, actor, paciente_id, movimiento_id, datos.motivo)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return anulacion


__all__ = ["router"]
