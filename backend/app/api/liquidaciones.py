"""Router liquidaciones a obras sociales (C-11, D-09..D-13, D-16, D-17).

`admin` opera todo; `odontologo` solo lista y consulta (con sus filas); `secretaria` recibe 403
en todo el prefijo. Esto NO habilita `/caja`: el ingreso es parte de la liquidación y
`POST /caja/cobrar` y `POST /caja/cierre` siguen siendo solo de `secretaria` (D-16 de C-10).
Descartar es `POST` porque `MetodoHttp` del frontend no incluye DELETE. El servicio solo hace
flush; este router es dueño del commit. Los motivos viajan en el cuerpo, nunca en logs.
"""
import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api.clinica_comun import a_http
from app.core.deps import DbDep, require_role
from app.esquemas.liquidacion import (
    CobrarLiquidacionIn, GenerarLiquidacionIn, LiquidacionDetalleOut, LiquidacionOut,
    RevertirCobroIn,
)
from app.modelos import Usuario
from app.servicios import liquidacion_export as export
from app.servicios import liquidacion_servicio as svc

router = APIRouter(prefix="/liquidaciones", tags=["liquidaciones"])

LecturaLiquidacionDep = Annotated[Usuario, Depends(require_role("admin", "odontologo"))]
OperacionLiquidacionDep = Annotated[Usuario, Depends(require_role("admin"))]


def get_liquidacion_repos(db: DbDep) -> svc.LiquidacionRepos:
    return svc.LiquidacionRepos.de_sesion(db)


LiquidacionReposDep = Annotated[svc.LiquidacionRepos, Depends(get_liquidacion_repos)]


@router.get("")
async def listar_liquidaciones(
    usuario: LecturaLiquidacionDep, repos: LiquidacionReposDep, db: DbDep
) -> list[LiquidacionOut]:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        return await svc.listar(repos, actor)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None


@router.post("", status_code=201)
async def generar_liquidacion(
    datos: GenerarLiquidacionIn, usuario: OperacionLiquidacionDep, repos: LiquidacionReposDep,
    db: DbDep,
) -> LiquidacionDetalleOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        liquidacion = await svc.generar(repos, actor, datos)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return liquidacion


@router.get("/{liquidacion_id}")
async def obtener_liquidacion(
    liquidacion_id: int, usuario: LecturaLiquidacionDep, repos: LiquidacionReposDep, db: DbDep
) -> LiquidacionDetalleOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        return await svc.obtener(repos, actor, liquidacion_id)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None


@router.post("/{liquidacion_id}/presentar")
async def presentar_liquidacion(
    liquidacion_id: int, usuario: OperacionLiquidacionDep, repos: LiquidacionReposDep, db: DbDep
) -> LiquidacionDetalleOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        liquidacion = await svc.presentar(repos, actor, liquidacion_id)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return liquidacion


@router.post("/{liquidacion_id}/descartar", status_code=204)
async def descartar_liquidacion(
    liquidacion_id: int, usuario: OperacionLiquidacionDep, repos: LiquidacionReposDep, db: DbDep
) -> Response:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        await svc.descartar(repos, actor, liquidacion_id)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return Response(status_code=204)


@router.post("/{liquidacion_id}/cobrar")
async def cobrar_liquidacion(
    liquidacion_id: int, datos: CobrarLiquidacionIn, usuario: OperacionLiquidacionDep,
    repos: LiquidacionReposDep, db: DbDep,
) -> LiquidacionDetalleOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        liquidacion = await svc.cobrar(repos, actor, liquidacion_id, datos.medio)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return liquidacion


@router.post("/{liquidacion_id}/revertir-cobro")
async def revertir_cobro_liquidacion(
    liquidacion_id: int, datos: RevertirCobroIn, usuario: OperacionLiquidacionDep,
    repos: LiquidacionReposDep, db: DbDep,
) -> LiquidacionDetalleOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        liquidacion = await svc.revertir_cobro(repos, actor, liquidacion_id, datos.motivo)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return liquidacion


@router.get("/{liquidacion_id}/export.csv")
async def exportar_csv(
    liquidacion_id: int, usuario: OperacionLiquidacionDep, repos: LiquidacionReposDep, db: DbDep
) -> Response:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        detalle = await svc.para_exportar(repos, actor, liquidacion_id)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    contenido = export.a_csv(export.construir_informe(detalle))
    return Response(
        content=contenido, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="liquidacion-{liquidacion_id}.csv"'},
    )


@router.get("/{liquidacion_id}/export.pdf")
async def exportar_pdf(
    liquidacion_id: int, usuario: OperacionLiquidacionDep, repos: LiquidacionReposDep, db: DbDep
) -> Response:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        detalle = await svc.para_exportar(repos, actor, liquidacion_id)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    # Armar el PDF es CPU puro y bloqueante: se corre fuera del loop (D-17).
    contenido = await asyncio.to_thread(export.a_pdf, export.construir_informe(detalle))
    return Response(
        content=contenido, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="liquidacion-{liquidacion_id}.pdf"'},
    )


__all__ = ["router"]
