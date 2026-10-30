"""Router historias clínicas (C-08, D-06..D-09).

Lectura: secretaria y odontólogo vinculado. Escritura: odontólogo vinculado.
Admin/Dueño: 403. Sin DELETE: la baja es lógica con motivo (RN-GL-01).
El servicio solo hace flush; este router es dueño del commit.
"""
from fastapi import APIRouter

from app.api.clinica_comun import (
    ClinicaReposDep, EscrituraClinicaDep, LecturaClinicaDep, a_http,
)
from app.core.deps import DbDep
from app.esquemas.clinica import BajaIn, HistoriaIn, HistoriaOut, HistoriaPatch
from app.servicios import clinica_servicio as svc

router = APIRouter(prefix="/historias", tags=["historias"])


def _a_out(hc) -> HistoriaOut:
    return HistoriaOut.model_validate(hc, from_attributes=True)


@router.get("")
async def buscar_historias(
    paciente_id: int, usuario: LecturaClinicaDep, repos: ClinicaReposDep, db: DbDep,
) -> list[HistoriaOut]:
    """Historia del paciente: lista de 0 o 1 (no hay listado masivo de PHI)."""
    try:
        actor = await svc.construir_actor(repos, usuario)
        return [_a_out(h) for h in await svc.buscar_historias(repos, actor, paciente_id)]
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None


@router.post("", status_code=201)
async def crear_historia(
    datos: HistoriaIn, usuario: EscrituraClinicaDep, repos: ClinicaReposDep, db: DbDep,
) -> HistoriaOut:
    try:
        actor = await svc.construir_actor(repos, usuario)
        hc = await svc.crear_historia(
            repos, actor, datos.paciente_id, datos.antecedentes, datos.alergias
        )
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return _a_out(hc)


@router.get("/{hc_id}")
async def obtener_historia(
    hc_id: int, usuario: LecturaClinicaDep, repos: ClinicaReposDep, db: DbDep,
) -> HistoriaOut:
    try:
        actor = await svc.construir_actor(repos, usuario)
        return _a_out(await svc.obtener_historia(repos, actor, hc_id))
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None


@router.patch("/{hc_id}")
async def actualizar_historia(
    hc_id: int, datos: HistoriaPatch, usuario: EscrituraClinicaDep,
    repos: ClinicaReposDep, db: DbDep,
) -> HistoriaOut:
    """Solo se aplican los campos enviados."""
    try:
        actor = await svc.construir_actor(repos, usuario)
        hc = await svc.actualizar_historia(
            repos, actor, hc_id, datos.model_dump(exclude_unset=True)
        )
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return _a_out(hc)


@router.post("/{hc_id}/baja")
async def dar_de_baja_historia(
    hc_id: int, datos: BajaIn, usuario: EscrituraClinicaDep,
    repos: ClinicaReposDep, db: DbDep,
) -> HistoriaOut:
    """Baja lógica con motivo (cuerpo, nunca query: no entra a access logs)."""
    try:
        actor = await svc.construir_actor(repos, usuario)
        hc = await svc.dar_de_baja_historia(repos, actor, hc_id, datos.motivo_baja)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return _a_out(hc)


__all__ = ["router"]
