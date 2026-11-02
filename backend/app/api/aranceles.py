"""Router aranceles versionados (C-11, D-08, D-16).

POST crea; PATCH solo admite vigencia_hasta (el precio es inmutable: un precio nuevo es un
arancel nuevo). Sin DELETE. Lectura: personal; escritura: solo admin.
"""
from fastapi import APIRouter

from app.api.clinica_comun import a_http
from app.api.obras_sociales import EscrituraCatalogoDep, OsReposDep
from app.core.deps import CurrentUserDep, DbDep
from app.esquemas.obra_social import ArancelIn, ArancelOut, ArancelPatch
from app.servicios import obra_social_servicio as svc

router = APIRouter(prefix="/aranceles", tags=["aranceles"])


@router.get("")
async def listar_aranceles(
    usuario: CurrentUserDep, repos: OsReposDep, db: DbDep, plan_id: int | None = None,
    codigo: str | None = None,
) -> list[ArancelOut]:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        return await svc.listar_aranceles(repos, actor, plan_id, codigo)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None


@router.post("", status_code=201)
async def crear_arancel(
    datos: ArancelIn, usuario: EscrituraCatalogoDep, repos: OsReposDep, db: DbDep
) -> ArancelOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        arancel = await svc.crear_arancel(repos, actor, datos)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return arancel


@router.patch("/{arancel_id}")
async def cerrar_arancel(
    arancel_id: int, datos: ArancelPatch, usuario: EscrituraCatalogoDep, repos: OsReposDep,
    db: DbDep,
) -> ArancelOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        arancel = await svc.cerrar_arancel(repos, actor, arancel_id, datos.vigencia_hasta)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return arancel


__all__ = ["router"]
