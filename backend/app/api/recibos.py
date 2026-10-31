"""Router recibos (C-10, D-13, D-16, D-17, D-22, D-23).

Lectura: `secretaria` y `admin`. Anulación: solo `admin`. `odontologo` no accede. Sin
DELETE ni PUT: el recibo solo se anula por contramovimiento con motivo (en el cuerpo).
El servicio solo hace flush; este router es dueño del commit.
"""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.caja import CajaReposDep
from app.api.clinica_comun import a_http
from app.core.deps import DbDep, require_role
from app.esquemas.caja import AnulacionReciboIn, ReciboOut
from app.modelos import Usuario
from app.servicios import caja_servicio as svc

router = APIRouter(prefix="/recibos", tags=["recibos"])

LecturaRecibosDep = Annotated[Usuario, Depends(require_role("secretaria", "admin"))]
AnulacionRecibosDep = Annotated[Usuario, Depends(require_role("admin"))]


@router.get("")
async def listar_recibos(
    fecha: date, usuario: LecturaRecibosDep, repos: CajaReposDep, db: DbDep,
) -> list[ReciboOut]:
    """Recibos emitidos en la caja de `fecha`, del número mayor al menor."""
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        return await svc.listar_recibos(repos, actor, fecha)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None


@router.post("/{recibo_id}/anular")
async def anular_recibo(
    recibo_id: int, datos: AnulacionReciboIn, usuario: AnulacionRecibosDep,
    repos: CajaReposDep, db: DbDep,
) -> ReciboOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        recibo = await svc.anular_recibo(repos, actor, recibo_id, datos.motivo)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return recibo


__all__ = ["router"]
