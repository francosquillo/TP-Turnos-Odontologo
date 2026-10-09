"""C-03: superficie admin minima (solo `admin`; el CRUD completo es C-12)."""
from fastapi import APIRouter, HTTPException

from app.core.deps import AdminDep, RepoDep
from app.esquemas.usuario import UsuarioAdminOut
from app.servicios.usuarios_servicio import (
    UltimoAdminError,
    UsuarioNoEncontradoError,
    desactivar_usuario,
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


@router.patch("/usuarios/{usuario_id}/desactivar")
async def desactivar(
    usuario_id: int, _admin: AdminDep, repo: RepoDep
) -> UsuarioAdminOut:
    """Desactiva (activo=false); ultimo admin -> 409 (RN-AU-03)."""
    try:
        return _a_out(await desactivar_usuario(repo, usuario_id))
    except UltimoAdminError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except UsuarioNoEncontradoError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.delete("/usuarios/{usuario_id}", status_code=204)
async def eliminar(usuario_id: int, _admin: AdminDep, repo: RepoDep) -> None:
    """Elimina; ultimo admin -> 409 (RN-AU-03)."""
    try:
        await eliminar_usuario(repo, usuario_id)
    except UltimoAdminError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except UsuarioNoEncontradoError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return None
