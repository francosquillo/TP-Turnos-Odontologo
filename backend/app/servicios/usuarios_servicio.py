"""Servicio usuarios: guard >=1 admin activo (RN-AU-03, D-03).

A nivel servicio, no DB: desactivar/eliminar el unico admin activo aborta
con UltimoAdminError (el endpoint C-03 lo mapea a 409/422).
"""
from app.repos.usuario_repo import UsuarioRepository


class UltimoAdminError(Exception):
    """Se intento dejar el sistema sin admins activos."""


class UsuarioNoEncontradoError(LookupError):
    """El usuario objetivo no existe."""


def _es_admin_activo(usuario) -> bool:
    rol = getattr(usuario, "rol", None)
    return getattr(usuario, "activo", False) is True and (
        getattr(rol, "nombre", None) == "admin"
    )


async def _exige_otro_admin(repo: UsuarioRepository, usuario_id: int) -> None:
    admins = await repo.listar_admins_activos()
    restantes = [a for a in admins if getattr(a, "id", None) != usuario_id]
    if not restantes:
        raise UltimoAdminError(
            "no se puede desactivar/eliminar al ultimo admin activo (RN-AU-03)"
        )


async def desactivar_usuario(repo: UsuarioRepository, usuario_id: int):
    """Desactiva (activo=False); bloquea si es el ultimo admin activo."""
    usuario = await repo.get(usuario_id)
    if usuario is None:
        raise UsuarioNoEncontradoError(f"usuario {usuario_id} inexistente")
    if _es_admin_activo(usuario):
        await _exige_otro_admin(repo, usuario_id)
    return await repo.actualizar(usuario, activo=False)


async def eliminar_usuario(repo: UsuarioRepository, usuario_id: int) -> None:
    """Elimina; bloquea si es el ultimo admin activo."""
    usuario = await repo.get(usuario_id)
    if usuario is None:
        raise UsuarioNoEncontradoError(f"usuario {usuario_id} inexistente")
    if _es_admin_activo(usuario):
        await _exige_otro_admin(repo, usuario_id)
    await repo.eliminar(usuario)
