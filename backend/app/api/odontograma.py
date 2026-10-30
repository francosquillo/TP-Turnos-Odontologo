"""Router odontograma: catálogo de estados + hallazgos por historia (C-08, D-05..D-09).

Toda respuesta clínica lleva `alergias` en la raíz (D-08). Los hallazgos no se
sobrescriben: PUT corrige (baja + fila nueva) y POST .../baja anula; no hay DELETE.
"""
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.clinica_comun import (
    ClinicaReposDep, EscrituraClinicaDep, LecturaClinicaDep, a_http,
)
from app.core.deps import CurrentUserDep, DbDep
from app.esquemas.clinica import (
    BajaIn, CatalogoOut, EstadoCatalogoOut, HallazgoConAlergias,
    HallazgoCorreccionIn, HallazgoIn, HallazgoOut, HallazgosConAlergias, PiezaFdi,
)
from app.servicios import clinica_servicio as svc

router = APIRouter(prefix="/odontograma", tags=["odontograma"])


_CAMPOS = (
    "id", "hc_id", "pieza_fdi", "cara", "estado", "catalogo_version", "fecha",
    "profesional_id", "corrige_a_id", "deleted_at", "motivo_baja",
)


def _a_out(hallazgo, actor: svc.Actor) -> HallazgoOut:
    """`es_propio` depende de quién consulta (solo el autor corrige o anula)."""
    propio = actor.profesional_id is not None and hallazgo.profesional_id == actor.profesional_id
    datos = {campo: getattr(hallazgo, campo) for campo in _CAMPOS}
    return HallazgoOut.model_validate({**datos, "es_propio": propio})


def _con_alergias(hc, hallazgo, actor: svc.Actor) -> HallazgoConAlergias:
    return HallazgoConAlergias(alergias=hc.alergias, hallazgo=_a_out(hallazgo, actor))


@router.get("/catalogo")
async def ver_catalogo(_usuario: CurrentUserDep, repos: ClinicaReposDep) -> CatalogoOut:
    """Catálogo vigente de estados; cualquier rol autenticado (sin PHI)."""
    version, estados = await svc.catalogo_vigente(repos)
    return CatalogoOut(
        version=version or 0,
        estados=[
            EstadoCatalogoOut(codigo=e.codigo, nombre=e.nombre, alcance=e.alcance)
            for e in estados
        ],
    )


@router.get("/{hc_id}/hallazgos")
async def listar_hallazgos(
    hc_id: int, usuario: LecturaClinicaDep, repos: ClinicaReposDep, db: DbDep,
    pieza: Annotated[PiezaFdi | None, Query()] = None,
    incluir_anulados: bool = False,
) -> HallazgosConAlergias:
    try:
        actor = await svc.construir_actor(repos, usuario)
        hc, hallazgos = await svc.listar_hallazgos(
            repos, actor, hc_id, pieza, incluir_anulados
        )
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    return HallazgosConAlergias(
        alergias=hc.alergias,
        hallazgos=[_a_out(h, actor) for h in hallazgos],
    )


@router.post("/{hc_id}/hallazgos", status_code=201)
async def registrar_hallazgo(
    hc_id: int, datos: HallazgoIn, usuario: EscrituraClinicaDep,
    repos: ClinicaReposDep, db: DbDep,
) -> HallazgoConAlergias:
    try:
        actor = await svc.construir_actor(repos, usuario)
        hallazgo = await svc.registrar_hallazgo(
            repos, actor, hc_id, datos.pieza_fdi, datos.cara, datos.estado
        )
        hc = await svc.obtener_historia(repos, actor, hc_id)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return _con_alergias(hc, hallazgo, actor)


@router.get("/{hc_id}/hallazgos/{hallazgo_id}")
async def obtener_hallazgo(
    hc_id: int, hallazgo_id: int, usuario: LecturaClinicaDep,
    repos: ClinicaReposDep, db: DbDep,
) -> HallazgoConAlergias:
    try:
        actor = await svc.construir_actor(repos, usuario)
        hc, hallazgo = await svc.obtener_hallazgo(repos, actor, hc_id, hallazgo_id)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    return _con_alergias(hc, hallazgo, actor)


@router.put("/{hc_id}/hallazgos/{hallazgo_id}")
async def corregir_hallazgo(
    hc_id: int, hallazgo_id: int, datos: HallazgoCorreccionIn,
    usuario: EscrituraClinicaDep, repos: ClinicaReposDep, db: DbDep,
) -> HallazgoConAlergias:
    """Corrige un error: da de baja el original y devuelve la fila nueva (id nuevo)."""
    try:
        actor = await svc.construir_actor(repos, usuario)
        nuevo = await svc.corregir_hallazgo(
            repos, actor, hc_id, hallazgo_id, datos.pieza_fdi, datos.cara,
            datos.estado, datos.motivo,
        )
        hc = await svc.obtener_historia(repos, actor, hc_id)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return _con_alergias(hc, nuevo, actor)


@router.post("/{hc_id}/hallazgos/{hallazgo_id}/baja")
async def dar_de_baja_hallazgo(
    hc_id: int, hallazgo_id: int, datos: BajaIn, usuario: EscrituraClinicaDep,
    repos: ClinicaReposDep, db: DbDep,
) -> HallazgoConAlergias:
    try:
        actor = await svc.construir_actor(repos, usuario)
        hallazgo = await svc.dar_de_baja_hallazgo(
            repos, actor, hc_id, hallazgo_id, datos.motivo_baja
        )
        hc = await svc.obtener_historia(repos, actor, hc_id)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return _con_alergias(hc, hallazgo, actor)


__all__ = ["router"]
