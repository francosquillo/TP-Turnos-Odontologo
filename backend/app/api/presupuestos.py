"""Router presupuestos (C-09, D-03, D-09, D-10, D-19, D-20).

Lectura: odontólogo vinculado, secretaria y admin (vista financiera). Escritura:
solo el odontólogo autor. Sin DELETE: la baja es lógica con motivo (RN-GL-01).
Los motivos viajan en el cuerpo, nunca en la URL (no entran a access logs).
Sin ruta de cobro: `pago` lo registra solo `POST /caja/cobrar` (C-10). `cobrado` lo marca la
caja al saldar el pendiente o, desde C-11, `aceptar` cuando la cobertura de la obra social
salda todo el importe (sin recibo); ninguna ruta acepta `estado` en el cuerpo. El servicio solo hace
flush; este router es dueño del commit. Todas las respuestas pasan por
`svc.a_salida`, el único punto que aplica la vista financiera del admin.
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from app.api.clinica_comun import EscrituraClinicaDep, a_http
from app.core.deps import DbDep, require_role
from app.esquemas.clinica import BajaIn
from app.esquemas.presupuesto import PresupuestoIn, PresupuestoOut, PresupuestoPut, RechazoIn
from app.modelos import Usuario
from app.servicios import presupuesto_servicio as svc

router = APIRouter(prefix="/presupuestos", tags=["presupuestos"])

LecturaPresupuestoDep = Annotated[
    Usuario, Depends(require_role("odontologo", "secretaria", "admin"))
]
EstadoFiltro = Literal["borrador", "presentado", "aceptado", "rechazado", "cobrado"]


def get_presupuesto_repos(db: DbDep) -> svc.PresupuestoRepos:
    return svc.PresupuestoRepos.de_sesion(db)


PresupuestoReposDep = Annotated[svc.PresupuestoRepos, Depends(get_presupuesto_repos)]


@router.get("")
async def listar_presupuestos(
    paciente_id: int, usuario: LecturaPresupuestoDep, repos: PresupuestoReposDep, db: DbDep,
    estado: EstadoFiltro | None = None,
) -> list[PresupuestoOut]:
    """Presupuestos del paciente (más reciente primero), sin bajas."""
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        lista = await svc.listar(repos, actor, paciente_id, estado)
        return await svc.a_salidas(repos, actor, lista)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None


@router.post("", status_code=201)
async def crear_presupuesto(
    datos: PresupuestoIn, usuario: EscrituraClinicaDep, repos: PresupuestoReposDep, db: DbDep,
) -> PresupuestoOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        presupuesto = await svc.crear(repos, actor, datos.paciente_id, datos.items)
        salida = await svc.a_salida(repos, actor, presupuesto)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return salida


@router.get("/{presupuesto_id}")
async def obtener_presupuesto(
    presupuesto_id: int, usuario: LecturaPresupuestoDep, repos: PresupuestoReposDep, db: DbDep,
) -> PresupuestoOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        presupuesto = await svc.obtener(repos, actor, presupuesto_id)
        return await svc.a_salida(repos, actor, presupuesto)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None


@router.put("/{presupuesto_id}")
async def reemplazar_items(
    presupuesto_id: int, datos: PresupuestoPut, usuario: EscrituraClinicaDep,
    repos: PresupuestoReposDep, db: DbDep,
) -> PresupuestoOut:
    """Reemplaza la lista completa de ítems de un borrador."""
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        presupuesto = await svc.reemplazar_items(repos, actor, presupuesto_id, datos.items)
        salida = await svc.a_salida(repos, actor, presupuesto)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return salida


@router.post("/{presupuesto_id}/presentar")
async def presentar_presupuesto(
    presupuesto_id: int, usuario: EscrituraClinicaDep, repos: PresupuestoReposDep, db: DbDep,
) -> PresupuestoOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        presupuesto = await svc.presentar(repos, actor, presupuesto_id)
        salida = await svc.a_salida(repos, actor, presupuesto)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return salida


@router.post("/{presupuesto_id}/aceptar")
async def aceptar_presupuesto(
    presupuesto_id: int, usuario: EscrituraClinicaDep, repos: PresupuestoReposDep, db: DbDep,
) -> PresupuestoOut:
    """Acepta y genera el cargo en la misma transacción."""
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        presupuesto = await svc.aceptar(repos, actor, presupuesto_id)
        salida = await svc.a_salida(repos, actor, presupuesto)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return salida


@router.post("/{presupuesto_id}/rechazar")
async def rechazar_presupuesto(
    presupuesto_id: int, datos: RechazoIn, usuario: EscrituraClinicaDep,
    repos: PresupuestoReposDep, db: DbDep,
) -> PresupuestoOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        presupuesto = await svc.rechazar(repos, actor, presupuesto_id, datos.motivo)
        salida = await svc.a_salida(repos, actor, presupuesto)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return salida


@router.post("/{presupuesto_id}/baja")
async def dar_de_baja_presupuesto(
    presupuesto_id: int, datos: BajaIn, usuario: EscrituraClinicaDep,
    repos: PresupuestoReposDep, db: DbDep,
) -> PresupuestoOut:
    """Baja lógica de un borrador con motivo (cuerpo, nunca query)."""
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        presupuesto = await svc.dar_de_baja(repos, actor, presupuesto_id, datos.motivo_baja)
        salida = await svc.a_salida(repos, actor, presupuesto)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return salida


__all__ = ["router"]
