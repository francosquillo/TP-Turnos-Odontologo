"""Servicio usuarios: alta/edicion y guard >=1 admin activo (RN-AU-03; C-02 D-03, C-12 D-02..D-04).

A nivel servicio, no DB: quitarle el rol, desactivar o eliminar al unico admin activo aborta con
UltimoAdminError (el endpoint lo mapea a 409). El guard toma el lock `FOR UPDATE` de los admins
activos (repo), asi que dos operaciones concurrentes se serializan. El servicio solo hace
flush; el router es dueno del commit y del rollback. Con `auditoria` y `actor_id` registra el
evento de la accion exitosa (R3): un error de dominio levanta antes y no deja evento.
"""
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.core.security import hashear_password
from app.repos.usuario_repo import UsuarioRepository
from app.servicios.auditoria_servicio import auditar


class UltimoAdminError(Exception):
    """Se intento dejar el sistema sin admins activos."""


class UsuarioNoEncontradoError(LookupError):
    """El usuario objetivo no existe."""


class EmailDuplicadoError(Exception):
    """Ya existe un usuario con ese email (sin distinguir mayusculas)."""


class UsuarioConHistorialError(Exception):
    """El usuario tiene historial referenciado: no se borra, se desactiva (RN-GL-01)."""


_MSG_HISTORIAL = "el usuario tiene historial (turnos, recibos u otros registros): desactivalo"


def _es_admin_activo(usuario) -> bool:
    rol = getattr(usuario, "rol", None)
    return getattr(usuario, "activo", False) is True and (
        getattr(rol, "nombre", None) == "admin"
    )


async def _exige_otro_admin(repo: UsuarioRepository, usuario_id: int, accion: str) -> None:
    """Toma el lock de los admins activos y exige que quede otro ademas del objetivo."""
    admins = await repo.listar_admins_activos()
    ids = {getattr(a, "id", None) for a in admins}
    # Si el objetivo ya no es admin activo (otra transaccion lo cambio), no hay nada que cuidar.
    if usuario_id in ids and not (ids - {usuario_id}):
        raise UltimoAdminError(
            f"no se puede {accion} al ultimo admin activo (RN-AU-03)"
        )


async def crear_usuario(
    repo: UsuarioRepository,
    *,
    nombre: str,
    email: str,
    password: str,
    rol: str,
    auditoria=None,
    actor_id: int | None = None,
):
    """Alta activa con hash Argon2. Email repetido (sin mayusculas) -> EmailDuplicadoError."""
    if await repo.obtener_por_email(email) is not None:
        raise EmailDuplicadoError("ya existe un usuario con ese email")
    rol_fila = await repo.obtener_rol(rol)
    if rol_fila is None:
        raise LookupError(f"rol {rol} inexistente: falta el seed de roles")
    password_hash = await run_in_threadpool(hashear_password, password)
    try:
        usuario = await repo.crear(
            nombre=nombre, email=email, password_hash=password_hash, rol=rol_fila
        )
    except IntegrityError:
        # Carrera: el indice unico uq_usuario_email_lower rechazo el segundo insert.
        raise EmailDuplicadoError("ya existe un usuario con ese email") from None
    await auditar(auditoria, actor_id, "usuario_alta", "usuario", usuario.id, {"rol": rol})
    return usuario


async def editar_usuario(
    repo: UsuarioRepository,
    usuario_id: int,
    *,
    nombre: str | None = None,
    rol: str | None = None,
    activo: bool | None = None,
    password: str | None = None,
    auditoria=None,
    actor_id: int | None = None,
):
    """Cambia solo los campos presentes. Quitar el rol admin al ultimo admin activo -> 409."""
    usuario = await repo.get(usuario_id)
    if usuario is None:
        raise UsuarioNoEncontradoError(f"usuario {usuario_id} inexistente")
    if rol is not None and rol != "admin" and _es_admin_activo(usuario):
        await _exige_otro_admin(repo, usuario_id, "quitar el rol admin")
    if rol is not None and rol != usuario.rol.nombre:
        rol_fila = await repo.obtener_rol(rol)
        if rol_fila is None:
            raise LookupError(f"rol {rol} inexistente: falta el seed de roles")
        await repo.cambiar_rol(usuario, rol_fila)
    cambios: dict[str, object] = {}
    if nombre is not None:
        cambios["nombre"] = nombre
    if activo is True:
        cambios["activo"] = True
    if password is not None:
        cambios["password_hash"] = await run_in_threadpool(hashear_password, password)
    if cambios:
        await repo.actualizar(usuario, **cambios)
    campos = [
        campo
        for campo, presente in (
            ("nombre", nombre is not None),
            ("rol", rol is not None),
            ("activo", activo is True),
            ("password", password is not None),
        )
        if presente
    ]
    if campos:
        detalle: dict[str, object] = {"campos": campos}
        if rol is not None:
            detalle["rol"] = rol
        await auditar(auditoria, actor_id, "usuario_edicion", "usuario", usuario_id, detalle)
    return usuario


async def desactivar_usuario(
    repo: UsuarioRepository,
    usuario_id: int,
    *,
    auditoria=None,
    actor_id: int | None = None,
):
    """Desactiva (activo=False); bloquea si es el ultimo admin activo."""
    usuario = await repo.get(usuario_id)
    if usuario is None:
        raise UsuarioNoEncontradoError(f"usuario {usuario_id} inexistente")
    if _es_admin_activo(usuario):
        await _exige_otro_admin(repo, usuario_id, "desactivar/eliminar")
    desactivado = await repo.actualizar(usuario, activo=False)
    await auditar(auditoria, actor_id, "usuario_desactivacion", "usuario", usuario_id)
    return desactivado


async def eliminar_usuario(
    repo: UsuarioRepository,
    usuario_id: int,
    *,
    auditoria=None,
    actor_id: int | None = None,
) -> None:
    """Elimina solo si no tiene historial; bloquea si es el ultimo admin activo (D-04)."""
    usuario = await repo.get(usuario_id)
    if usuario is None:
        raise UsuarioNoEncontradoError(f"usuario {usuario_id} inexistente")
    if _es_admin_activo(usuario):
        await _exige_otro_admin(repo, usuario_id, "desactivar/eliminar")
    if await repo.tiene_historial(usuario_id):
        raise UsuarioConHistorialError(_MSG_HISTORIAL)
    rol_anterior = usuario.rol.nombre
    try:
        await repo.eliminar(usuario)
    except IntegrityError:
        raise UsuarioConHistorialError(_MSG_HISTORIAL) from None
    await auditar(auditoria, actor_id, "usuario_eliminacion", "usuario", usuario_id, {"rol": rol_anterior})
