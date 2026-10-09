"""C-03: endpoints de sesion (D-01, D-04). Sin rate-limit (D-06, deuda C-12)."""
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.core.deps import CurrentUserDep, RepoDep, SettingsDep, StoreDep
from app.esquemas.auth import LoginIn, MeOut, TokenOut
from app.servicios.auth_servicio import (
    CUERPO_401,
    CUERPO_503,
    CredencialesInvalidasError,
    RefreshInvalidoError,
    SesionNoDisponibleError,
    cerrar_sesion,
    iniciar_sesion,
    rotar_sesion,
)

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_REFRESH = "refresh_token"


def _cookie_segura(respuesta: JSONResponse, refresh_plano: str, dias: int) -> None:
    respuesta.set_cookie(
        COOKIE_REFRESH,
        refresh_plano,
        max_age=dias * 86400,
        path="/auth",
        httponly=True,
        samesite="lax",
    )


@router.post("/login")
async def login(
    datos: LoginIn, repo: RepoDep, store: StoreDep, settings: SettingsDep
) -> JSONResponse:
    """Emite access (cuerpo) + refresh (cookie httpOnly); resto -> 401/503."""
    try:
        access, refresh_plano = await iniciar_sesion(
            repo, store, datos.email, datos.password, settings.refresh_expire_days
        )
    except CredencialesInvalidasError:
        raise HTTPException(status_code=401, detail=CUERPO_401) from None
    except SesionNoDisponibleError:
        raise HTTPException(status_code=503, detail=CUERPO_503) from None
    cuerpo = TokenOut(access_token=access, token_type="bearer").model_dump()
    respuesta = JSONResponse(status_code=200, content=cuerpo)
    _cookie_segura(respuesta, refresh_plano, settings.refresh_expire_days)
    return respuesta


RefreshCookie = Annotated[str | None, Cookie(alias=COOKIE_REFRESH)]


@router.post("/refresh")
async def refresh(
    repo: RepoDep,
    store: StoreDep,
    settings: SettingsDep,
    refresh_token: RefreshCookie = None,
) -> JSONResponse:
    """Rota el par (GETDEL+SET); reuso/ausente/vencido -> 401 sin emitir."""
    if not refresh_token:
        raise HTTPException(status_code=401, detail=CUERPO_401)
    try:
        access, nuevo_plano = await rotar_sesion(
            repo, store, refresh_token, settings.refresh_expire_days
        )
    except RefreshInvalidoError:
        raise HTTPException(status_code=401, detail=CUERPO_401) from None
    except SesionNoDisponibleError:
        raise HTTPException(status_code=503, detail=CUERPO_503) from None
    cuerpo = TokenOut(access_token=access, token_type="bearer").model_dump()
    respuesta = JSONResponse(status_code=200, content=cuerpo)
    _cookie_segura(respuesta, nuevo_plano, settings.refresh_expire_days)
    return respuesta


@router.post("/logout")
async def logout(
    store: StoreDep, refresh_token: RefreshCookie = None
) -> JSONResponse:
    """Invalida el refresh y limpia la cookie (idempotente: siempre 200)."""
    caido = False
    try:
        await cerrar_sesion(store, refresh_token)
    except SesionNoDisponibleError:
        caido = True
    if caido:
        respuesta = JSONResponse(status_code=503, content={"detail": CUERPO_503})
    else:
        respuesta = JSONResponse(
            status_code=200, content={"detail": "sesión cerrada"}
        )
    respuesta.delete_cookie(COOKIE_REFRESH, path="/auth")
    return respuesta


@router.get("/me")
async def me(usuario: CurrentUserDep) -> MeOut:
    """Identidad del Bearer (cualquier rol autenticado, nunca el hash)."""
    return MeOut(
        id=usuario.id, email=usuario.email, nombre=usuario.nombre, rol=usuario.rol.nombre
    )
