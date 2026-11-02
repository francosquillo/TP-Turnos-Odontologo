"""Superficie admin (solo `admin`): usuarios (C-03 + C-12), auditoria y exportacion total (C-12).

El servicio solo hace flush; este router es dueno del commit. Ante un error de dominio hace
rollback (libera el lock del guard de ultimo admin) y mapea a 404/409. Cada accion exitosa
registra su evento de auditoria en la misma transaccion; un 4xx no deja evento.
"""
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from app.core.deps import AdminDep, AuditoriaDep, DbDep, RepoDep
from app.esquemas.auditoria import EventoAuditoriaOut
from app.esquemas.usuario import UsuarioAdminOut, UsuarioAltaIn, UsuarioEdicionIn
from app.servicios.auditoria_servicio import auditar
from app.servicios.caja_servicio import hoy_operativo
from app.servicios.exportacion_servicio import exportar_total
from app.servicios.usuarios_servicio import (
    EmailDuplicadoError,
    UltimoAdminError,
    UsuarioConHistorialError,
    UsuarioNoEncontradoError,
    crear_usuario,
    desactivar_usuario,
    editar_usuario,
    eliminar_usuario,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _a_out(usuario) -> UsuarioAdminOut:
    return UsuarioAdminOut(
        id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        rol=usuario.rol.nombre,
        activo=usuario.activo,
    )


@router.get("/usuarios")
async def listar_usuarios(_admin: AdminDep, repo: RepoDep) -> list[UsuarioAdminOut]:
    """Listado de usuarios con rol (solo admin)."""
    return [_a_out(u) for u in await repo.listar_todos_con_rol()]


@router.post("/usuarios", status_code=201)
async def crear(
    datos: UsuarioAltaIn, admin: AdminDep, repo: RepoDep, auditoria: AuditoriaDep, db: DbDep
) -> UsuarioAdminOut:
    """Alta de usuario activo con uno de los tres roles; email repetido -> 409."""
    try:
        usuario = await crear_usuario(
            repo, nombre=datos.nombre, email=datos.email, password=datos.password, rol=datos.rol,
            auditoria=auditoria, actor_id=admin.id,
        )
        salida = _a_out(usuario)
    except EmailDuplicadoError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    await db.commit()
    return salida


@router.patch("/usuarios/{usuario_id}")
async def editar(
    usuario_id: int,
    datos: UsuarioEdicionIn,
    admin: AdminDep,
    repo: RepoDep,
    auditoria: AuditoriaDep,
    db: DbDep,
) -> UsuarioAdminOut:
    """Edita nombre, rol, contrasena o reactiva; quitar el rol al ultimo admin -> 409."""
    try:
        usuario = await editar_usuario(
            repo,
            usuario_id,
            nombre=datos.nombre,
            rol=datos.rol,
            activo=datos.activo,
            password=datos.password,
            auditoria=auditoria,
            actor_id=admin.id,
        )
        salida = _a_out(usuario)
    except UltimoAdminError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except UsuarioNoEncontradoError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from None
    await db.commit()
    return salida


@router.patch("/usuarios/{usuario_id}/desactivar")
async def desactivar(
    usuario_id: int, admin: AdminDep, repo: RepoDep, auditoria: AuditoriaDep, db: DbDep
) -> UsuarioAdminOut:
    """Desactiva (activo=false); ultimo admin -> 409 (RN-AU-03)."""
    try:
        usuario = await desactivar_usuario(repo, usuario_id, auditoria=auditoria, actor_id=admin.id)
        salida = _a_out(usuario)
    except UltimoAdminError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except UsuarioNoEncontradoError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from None
    await db.commit()
    return salida


@router.delete("/usuarios/{usuario_id}", status_code=204)
async def eliminar(
    usuario_id: int, admin: AdminDep, repo: RepoDep, auditoria: AuditoriaDep, db: DbDep
) -> None:
    """Elimina; ultimo admin o usuario con historial -> 409 (RN-AU-03, RN-GL-01)."""
    try:
        await eliminar_usuario(repo, usuario_id, auditoria=auditoria, actor_id=admin.id)
    except (UltimoAdminError, UsuarioConHistorialError) as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except UsuarioNoEncontradoError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from None
    await db.commit()
    return None


@router.get("/auditoria")
async def listar_auditoria(
    _admin: AdminDep,
    auditoria: AuditoriaDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[EventoAuditoriaOut]:
    """Eventos de auditoria del mas reciente al mas antiguo, paginados (solo admin)."""
    eventos = await auditoria.listar_recientes(limit=limit, offset=offset)
    return [EventoAuditoriaOut.model_validate(e, from_attributes=True) for e in eventos]


@router.get("/export-total")
async def exportacion_total(admin: AdminDep, auditoria: AuditoriaDep, db: DbDep) -> Response:
    """ZIP con un CSV por tabla y un LEEME (solo admin). Sin hashes ni secretos (D-12)."""
    contenido = await exportar_total(db)
    await auditar(auditoria, admin.id, "exportacion_total", "exportacion")
    await db.commit()
    nombre = f"export-total-{hoy_operativo().isoformat()}.zip"
    return Response(
        content=contenido,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
