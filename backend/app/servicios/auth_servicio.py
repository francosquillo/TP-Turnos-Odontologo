"""C-03: sesion access/refresh con rotacion (D-01, D-04, D-05).

Access JWT corto (stateless) + refresh opaco en Redis (revocable):
- Redis guarda solo el SHA-256 del refresh (`auth:refresh:<hex>`).
- Rotacion atomica GETDEL+SET; reuso -> 401 + invalida la familia (D-05).
- Login 401 generico con hash dummy si no hay hash (D-04).
- Redis caido -> SesionNoDisponibleError (el router lo mapea a 503).

El hash Argon2 es CPU sincrono: se corre en threadpool via
`run_in_threadpool` para no bloquear el event loop.
"""
import hashlib
import json
import secrets
from typing import Protocol

from app.core.security import crear_access_token

CUERPO_401 = "credenciales inválidas"
CUERPO_503 = "servicio de sesión no disponible"


class CredencialesInvalidasError(Exception):
    """Cualquier causa de login fallido (mismo 401 generico)."""


class RefreshInvalidoError(Exception):
    """Refresh ausente, vencido o ya rotado (401 sin emitir nada)."""


class SesionNoDisponibleError(Exception):
    """Redis caido (se mapea a 503 explicito)."""


class SesionStore(Protocol):
    """Superficie Redis que usa el servicio (real o fake en tests)."""

    async def get(self, key: str) -> str | None: ...
    async def getdel(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ex: int | None = ...) -> object: ...
    async def delete(self, *keys: str) -> int: ...
    async def ping(self) -> bool: ...


def _huella(token_plano: str) -> str:
    return hashlib.sha256(token_plano.encode()).hexdigest()


def _ttl_segundos(refresh_expire_days: int) -> int:
    return refresh_expire_days * 86400


def _clave_refresh(huella: str) -> str:
    return f"auth:refresh:{huella}"


def _clave_sesion(usuario_id: int, sesion_id: str) -> str:
    return f"auth:sesion:{usuario_id}:{sesion_id}"


def _clave_reuso(huella: str) -> str:
    return f"auth:reuso:{huella}"


async def _invalidar_familia(
    store: SesionStore, usuario_id: int, sesion_id: str
) -> None:
    """Borra el refresh vigente de la sesion comprometida (reuso, D-05)."""
    clave_sesion = _clave_sesion(usuario_id, sesion_id)
    vigente = await store.get(clave_sesion)
    if vigente is not None:
        await store.delete(_clave_refresh(vigente))
    await store.delete(clave_sesion)


async def emitir_sesion(
    store: SesionStore,
    usuario_id: int,
    rol: str,
    refresh_expire_days: int,
    sesion_id: str | None = None,
) -> tuple[str, str]:
    """Crea par (access, refresh_plano) y lo guarda en Redis con TTL.

    La rotacion reutiliza el `sesion_id` para que la familia sea trazable
    (el reuso invalida el refresh vigente, D-05).
    """
    access = crear_access_token(usuario_id, rol)
    refresh_plano = secrets.token_urlsafe(32)
    if sesion_id is None:
        sesion_id = secrets.token_urlsafe(16)
    ttl = _ttl_segundos(refresh_expire_days)
    valor = json.dumps({"u": usuario_id, "s": sesion_id})
    await store.set(_clave_refresh(_huella(refresh_plano)), valor, ex=ttl)
    await store.set(_clave_sesion(usuario_id, sesion_id), _huella(refresh_plano), ex=ttl)
    return access, refresh_plano


async def iniciar_sesion(
    repo, store: SesionStore, email: str, password: str, refresh_expire_days: int
) -> tuple[str, str]:
    """Login: valida y emite par; cualquier fallo -> error generico/503."""
    from fastapi.concurrency import run_in_threadpool

    from app.core.security import verificar_password

    try:
        usuario = await repo.obtener_por_email(email)
    except Exception as exc:
        raise SesionNoDisponibleError(CUERPO_503) from exc
    if usuario is None:
        await run_in_threadpool(verificar_password, password, _hash_dummy())
        raise CredencialesInvalidasError(CUERPO_401)
    coincide = await run_in_threadpool(verificar_password, password, usuario.password_hash)
    if not coincide or usuario.activo is not True:
        raise CredencialesInvalidasError(CUERPO_401)
    try:
        return await emitir_sesion(store, usuario.id, usuario.rol.nombre, refresh_expire_days)
    except Exception as exc:
        raise SesionNoDisponibleError(CUERPO_503) from exc


async def rotar_sesion(
    repo, store: SesionStore, refresh_plano: str, refresh_expire_days: int
) -> tuple[str, str]:
    """Refresh: emite par nuevo e invalida el anterior; reuso -> 401."""
    try:
        anterior = await store.getdel(_clave_refresh(_huella(refresh_plano)))
    except Exception as exc:
        raise SesionNoDisponibleError(CUERPO_503) from exc
    if anterior is None:
        await _castigar_reuso(store, refresh_plano)
        raise RefreshInvalidoError(CUERPO_401)
    try:
        datos = json.loads(anterior)
        usuario_id = int(datos["u"])
        sesion_id = str(datos["s"])
    except (ValueError, KeyError, TypeError) as exc:
        raise RefreshInvalidoError(CUERPO_401) from exc
    usuario = await repo.obtener_con_rol(usuario_id)
    if usuario is None or usuario.activo is not True:
        raise RefreshInvalidoError(CUERPO_401)
    try:
        access, nuevo_plano = await emitir_sesion(
            store, usuario_id, usuario.rol.nombre, refresh_expire_days,
            sesion_id=sesion_id,
        )
    except Exception as exc:
        raise SesionNoDisponibleError(CUERPO_503) from exc
    ttl = _ttl_segundos(refresh_expire_days)
    await store.set(
        _clave_reuso(_huella(refresh_plano)),
        json.dumps({"u": usuario_id, "s": sesion_id}),
        ex=ttl,
    )
    return access, nuevo_plano


async def _castigar_reuso(store: SesionStore, refresh_plano: str) -> None:
    """Ante reuso trazable, invalida la familia (D-05); si no, solo 401."""
    try:
        marca = await store.get(_clave_reuso(_huella(refresh_plano)))
    except Exception:
        return
    if marca is None:
        return
    try:
        datos = json.loads(marca)
        await _invalidar_familia(store, int(datos["u"]), str(datos["s"]))
    except (ValueError, KeyError, TypeError):
        return


async def cerrar_sesion(store: SesionStore, refresh_plano: str | None) -> None:
    """Logout: invalida el refresh (idempotente, siempre limpia cookie)."""
    if not refresh_plano:
        return
    try:
        anterior = await store.getdel(_clave_refresh(_huella(refresh_plano)))
    except Exception as exc:
        raise SesionNoDisponibleError(CUERPO_503) from exc
    if anterior is None:
        return
    try:
        datos = json.loads(anterior)
        await store.delete(_clave_sesion(int(datos["u"]), str(datos["s"])))
    except (ValueError, KeyError, TypeError):
        return


_dummy_hash: str | None = None


def _hash_dummy() -> str:
    """Hash Argon2 constante para igualar tiempos sin usuario (D-04)."""
    global _dummy_hash
    if _dummy_hash is None:
        from app.core.security import hashear_password

        _dummy_hash = hashear_password("dummy-d04-solo-igualar-tiempos")
    return _dummy_hash
