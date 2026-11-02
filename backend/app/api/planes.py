"""Router planes de obra social (C-11, D-16). Lectura: personal; escritura: solo admin."""
from fastapi import APIRouter

from app.api.clinica_comun import a_http
from app.api.obras_sociales import EscrituraCatalogoDep, OsReposDep
from app.core.deps import CurrentUserDep, DbDep
from app.esquemas.obra_social import PlanIn, PlanOut, PlanPatch
from app.servicios import obra_social_servicio as svc

router = APIRouter(prefix="/planes", tags=["planes"])


@router.get("")
async def listar_planes(
    usuario: CurrentUserDep, repos: OsReposDep, db: DbDep, obra_social_id: int | None = None,
) -> list[PlanOut]:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        return await svc.listar_planes(repos, actor, obra_social_id)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None


@router.post("", status_code=201)
async def crear_plan(
    datos: PlanIn, usuario: EscrituraCatalogoDep, repos: OsReposDep, db: DbDep
) -> PlanOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        plan = await svc.crear_plan(repos, actor, datos)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return plan


@router.patch("/{plan_id}")
async def editar_plan(
    plan_id: int, datos: PlanPatch, usuario: EscrituraCatalogoDep, repos: OsReposDep, db: DbDep,
) -> PlanOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        plan = await svc.editar_plan(repos, actor, plan_id, datos)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return plan


__all__ = ["router"]
