"""Router caja (C-10, D-06, D-12, D-16, D-22, D-25).

`POST /cobrar` y `POST /cierre` solo para `secretaria`; `GET` para `secretaria` y `admin`;
`odontologo` no accede. El servicio solo hace flush; este router es dueño del commit.
Un reintento idempotente responde `200` y hace `rollback` en vez de `commit`: descarta
cualquier fila que el pedido haya podido crear (D-25). Los motivos viajan en el cuerpo,
nunca en la URL ni en logs.
"""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api.clinica_comun import a_http
from app.core.deps import DbDep, require_role
from app.esquemas.caja import CajaOut, CierreIn, CobroIn, CobroOut, EstadoCajaOut
from app.modelos import Usuario
from app.servicios import caja_servicio as svc

router = APIRouter(prefix="/caja", tags=["caja"])

LecturaCajaDep = Annotated[Usuario, Depends(require_role("secretaria", "admin"))]
OperacionCajaDep = Annotated[Usuario, Depends(require_role("secretaria"))]


def get_caja_repos(db: DbDep) -> svc.CajaRepos:
    return svc.CajaRepos.de_sesion(db)


CajaReposDep = Annotated[svc.CajaRepos, Depends(get_caja_repos)]


@router.get("")
async def obtener_caja(
    usuario: LecturaCajaDep, repos: CajaReposDep, db: DbDep, fecha: date | None = None,
) -> EstadoCajaOut:
    """Caja del día (o de `fecha`), desglose por medio y si se puede operar; no crea filas."""
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        return await svc.obtener_caja(repos, actor, fecha)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None


@router.post("/cobrar", status_code=201)
async def cobrar(
    datos: CobroIn, usuario: OperacionCajaDep, repos: CajaReposDep, db: DbDep,
    response: Response,
) -> CobroOut:
    """`201` si crea el recibo; `200` con el recibo original ante un reintento."""
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        cobro, creado = await svc.cobrar(repos, actor, datos)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    if creado:
        await db.commit()
    else:
        await db.rollback()
        response.status_code = 200
    return cobro


@router.post("/cierre")
async def cerrar_caja(
    datos: CierreIn, usuario: OperacionCajaDep, repos: CajaReposDep, db: DbDep,
) -> CajaOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        caja = await svc.cerrar(repos, actor, datos)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return caja


__all__ = ["router"]
