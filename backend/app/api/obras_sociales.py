"""Router obras sociales (C-11, D-16). Reemplaza el stub /os de C-01.

Lectura: todo el personal autenticado. Escritura: solo admin. Sin DELETE: la baja es logica
(activa: false). El servicio solo hace flush; este router es dueno del commit.
"""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.clinica_comun import a_http
from app.core.deps import CurrentUserDep, DbDep, require_role
from app.esquemas.obra_social import ObraSocialIn, ObraSocialOut, ObraSocialPatch
from app.modelos import Usuario
from app.servicios import obra_social_servicio as svc

router = APIRouter(prefix="/obras-sociales", tags=["obras-sociales"])

EscrituraCatalogoDep = Annotated[Usuario, Depends(require_role("admin"))]


def get_os_repos(db: DbDep) -> svc.ObraSocialRepos:
    return svc.ObraSocialRepos.de_sesion(db)


OsReposDep = Annotated[svc.ObraSocialRepos, Depends(get_os_repos)]


@router.get("")
async def listar_obras(
    usuario: CurrentUserDep, repos: OsReposDep, db: DbDep
) -> list[ObraSocialOut]:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        return await svc.listar_obras(repos, actor)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None


@router.post("", status_code=201)
async def crear_obra(
    datos: ObraSocialIn, usuario: EscrituraCatalogoDep, repos: OsReposDep, db: DbDep
) -> ObraSocialOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        obra = await svc.crear_obra(repos, actor, datos)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return obra


@router.patch("/{obra_id}")
async def editar_obra(
    obra_id: int, datos: ObraSocialPatch, usuario: EscrituraCatalogoDep, repos: OsReposDep,
    db: DbDep,
) -> ObraSocialOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        obra = await svc.editar_obra(repos, actor, obra_id, datos)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return obra


__all__ = ["EscrituraCatalogoDep", "OsReposDep", "router"]
