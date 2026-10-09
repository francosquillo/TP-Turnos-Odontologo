"""Dependencias reutilizables con Annotated (nunca `...` como default).

C-03 suma: sesion DB async (motor cacheado), cliente Redis y repo usuarios
inyectable (los tests lo reemplazan via `dependency_overrides`).
"""
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.modelos import Usuario
from app.repos.usuario_repo import UsuarioRepository
from app.servicios.auth_servicio import SesionStore

SettingsDep = Annotated[Settings, Depends(get_settings)]

_motor: AsyncEngine | None = None
_cliente_redis: SesionStore | None = None


def _obtener_motor() -> AsyncEngine:
    """Motor async unico (se crea al primer request, no al importar)."""
    global _motor
    if _motor is None:
        _motor = create_async_engine(get_settings().database_url)
    return _motor


async def get_db() -> AsyncIterator[AsyncSession]:
    """Sesion async por request (los servicios reciben repos, nunca esto)."""
    fabrica = async_sessionmaker(_obtener_motor(), expire_on_commit=False)
    async with fabrica() as sesion:
        yield sesion


DbDep = Annotated[AsyncSession, Depends(get_db)]


def get_redis() -> SesionStore:
    """Cliente Redis unico (decode str; timeouts cortos para 503 rapido)."""
    global _cliente_redis
    if _cliente_redis is None:
        import redis.asyncio as aioredis

        _cliente_redis = aioredis.from_url(
            get_settings().redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _cliente_redis


StoreDep = Annotated[SesionStore, Depends(get_redis)]


def get_usuario_repo(db: DbDep) -> UsuarioRepository:
    """Repo usuarios sobre la sesion del request (mockeable en tests)."""
    return UsuarioRepository(db)


RepoDep = Annotated[UsuarioRepository, Depends(get_usuario_repo)]

EsquemaBearer = HTTPBearer(auto_error=False)
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(EsquemaBearer)]


async def get_current_user(repo: RepoDep, credenciales: BearerDep) -> Usuario:
    """Identidad del Bearer (401 sin/invalido/expirado/inactivo).

    `async def` porque lee la DB async (no bloqueante, cumple la regla).
    """
    from app.core.security import TokenError, TokenExpiradoError, verificar_access_token

    if credenciales is None or not credenciales.credentials:
        raise HTTPException(status_code=401, detail="no autenticado")
    try:
        datos = verificar_access_token(credenciales.credentials)
    except TokenExpiradoError:
        raise HTTPException(status_code=401, detail="sesión expirada") from None
    except TokenError:
        raise HTTPException(status_code=401, detail="no autenticado") from None
    usuario = await repo.obtener_con_rol(int(datos["sub"]))
    if usuario is None or usuario.activo is not True:
        raise HTTPException(status_code=401, detail="no autenticado")
    return usuario


CurrentUserDep = Annotated[Usuario, Depends(get_current_user)]


def require_role(*roles: str):
    """Factoria de guard por rol (D-03): 403 si el rol no esta incluido.

    Uso: `AdminDep = Annotated[Usuario, Depends(require_role("admin"))]`.
    `def` (no `async def`): no hace I/O, la DB la resolvio `get_current_user`.
    """

    def _guard(usuario: CurrentUserDep) -> Usuario:
        if usuario.rol.nombre not in roles:
            raise HTTPException(status_code=403, detail="sin permiso")
        return usuario

    return _guard


AdminDep = Annotated[Usuario, Depends(require_role("admin"))]
