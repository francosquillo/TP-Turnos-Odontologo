"""C-03 tasks 2.x: esquemas + endpoints /auth (unit con fakes + HTTP real)."""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: F401  (fixture PG real con skip sin Docker)


def test_login_in_rechaza_campo_extra():
    """Task 2.1 RED: LoginIn estricto (extra='forbid', sin hash en responses)."""
    from pydantic import ValidationError

    from app.esquemas.auth import LoginIn, MeOut, TokenOut

    bueno = LoginIn(email="a@demo.test", password="Secreta-123")
    assert bueno.email == "a@demo.test"
    with pytest.raises(ValidationError):
        LoginIn(email="a@demo.test", password="x", intruso="y")
    for esquema in (TokenOut, MeOut):
        with pytest.raises(ValidationError):
            esquema(intruso="y", **_ejemplo(esquema))
    assert "password_hash" not in MeOut.model_fields
    assert "password_hash" not in TokenOut.model_fields


def _ejemplo(esquema):
    if esquema.__name__ == "TokenOut":
        return {"access_token": "t", "token_type": "bearer"}
    return {"id": 1, "email": "a@demo.test", "nombre": "Ana", "rol": "admin"}


# ---------------------------------------------------------------------------
# Task 2.2: POST /auth/login (HTTP con overrides: FakeRepo + FakeStore)
# ---------------------------------------------------------------------------

def _app_con_fakes(repo, store):
    from httpx import ASGITransport, AsyncClient

    from app.core.deps import get_redis, get_usuario_repo
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_usuario_repo] = lambda: repo
    app.dependency_overrides[get_redis] = lambda: store
    transporte = ASGITransport(app=app)
    cliente = AsyncClient(transport=transporte, base_url="http://test")
    return app, cliente


def _refresh_de_set_cookie(respuesta) -> str | None:
    cabecera = respuesta.headers.get("set-cookie", "")
    for parte in cabecera.split(";"):
        parte = parte.strip()
        if parte.startswith("refresh_token="):
            return parte.split("=", 1)[1]
    return None


@pytest.mark.asyncio
async def test_login_ok_emite_access_y_cookie():
    """Task 2.2 RED: login valido -> 200 con access + cookie httpOnly."""
    import jwt as pyjwt

    from c03_fakes import FakeRepo, FakeStore, fabricar_usuario

    repo = FakeRepo([fabricar_usuario()])
    app, cliente = _app_con_fakes(repo, FakeStore())
    async with cliente:
        resp = await cliente.post(
            "/auth/login",
            json={"email": "SECRE@demo.test", "password": "Secreta-123"},
        )
    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    datos = pyjwt.decode(cuerpo["access_token"], options={"verify_signature": False})
    assert datos["sub"] == "1"
    assert datos["rol"] == "secretaria"
    assert cuerpo["token_type"] == "bearer"
    assert "password_hash" not in cuerpo
    assert _refresh_de_set_cookie(resp) is not None
    set_cookie = resp.headers["set-cookie"]
    assert "HttpOnly" in set_cookie


@pytest.mark.asyncio
async def test_login_email_inexistente_y_password_mala_mismo_401():
    """Task 2.2 RED: inexistente y mala password -> mismo 401 sin cookie."""
    from c03_fakes import FakeRepo, FakeStore, fabricar_usuario

    repo = FakeRepo([fabricar_usuario()])
    app, cliente = _app_con_fakes(repo, FakeStore())
    async with cliente:
        r1 = await cliente.post(
            "/auth/login", json={"email": "nadie@demo.test", "password": "x"}
        )
        r2 = await cliente.post(
            "/auth/login", json={"email": "secre@demo.test", "password": "mala-999"}
        )
    assert r1.status_code == 401
    assert r2.status_code == 401
    assert r1.json() == r2.json() == {"detail": "credenciales inválidas"}
    assert "set-cookie" not in r1.headers
    assert "set-cookie" not in r2.headers


@pytest.mark.asyncio
async def test_login_inactivo_401_generico():
    """Task 2.2 RED: usuario inactivo -> mismo 401 generico."""
    from c03_fakes import FakeRepo, FakeStore, fabricar_usuario

    repo = FakeRepo([fabricar_usuario(activo=False)])
    app, cliente = _app_con_fakes(repo, FakeStore())
    async with cliente:
        resp = await cliente.post(
            "/auth/login", json={"email": "secre@demo.test", "password": "Secreta-123"}
        )
    assert resp.status_code == 401
    assert resp.json() == {"detail": "credenciales inválidas"}


@pytest.mark.asyncio
async def test_login_in_rechaza_campo_extra_422():
    """Task 2.1 triangulacion HTTP: campo extra en login -> 422."""
    from c03_fakes import FakeRepo, FakeStore, fabricar_usuario

    repo = FakeRepo([fabricar_usuario()])
    app, cliente = _app_con_fakes(repo, FakeStore())
    async with cliente:
        resp = await cliente.post(
            "/auth/login",
            json={"email": "a@demo.test", "password": "x", "intruso": "y"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_redis_caido_503_explicito():
    """Task 2.2: Redis caido -> 503 con detail de sesion no disponible."""
    from c03_fakes import FakeRepo, FakeStore, fabricar_usuario

    roto = FakeStore()
    roto.roto = True
    repo = FakeRepo([fabricar_usuario()])
    app, cliente = _app_con_fakes(repo, roto)
    async with cliente:
        resp = await cliente.post(
            "/auth/login", json={"email": "secre@demo.test", "password": "Secreta-123"}
        )
    assert resp.status_code == 503
    assert resp.json() == {"detail": "servicio de sesión no disponible"}


# ---------------------------------------------------------------------------
# Task 2.2 integracion: PG + Redis reales (skip sin Docker/compose)
# ---------------------------------------------------------------------------

async def _redis_real_o_skip():
    import os

    import redis.asyncio as aioredis

    url = os.getenv("REDIS_URL_TEST", "redis://localhost:6379/0")
    cliente = aioredis.from_url(url, decode_responses=True, socket_timeout=3)
    try:
        await cliente.ping()
    except Exception as exc:
        await cliente.aclose()
        pytest.skip(f"Redis no reachable (¿compose down?): {exc}")
    return cliente


async def _sembrar_usuario_pg(sesion_pg, email="secre@demo.test", rol="secretaria"):
    from sqlalchemy import select

    from app.core.security import hashear_password
    from app.modelos import Rol
    from app.repos import RolRepository, UsuarioRepository

    rol_repo = RolRepository(sesion_pg)
    usu_repo = UsuarioRepository(sesion_pg)
    for nombre in ("admin", "odontologo", "secretaria"):
        await rol_repo.crear(nombre=nombre)
    rol_obj = await sesion_pg.scalar(select(Rol).where(Rol.nombre == rol))
    usuario = await usu_repo.crear(
        nombre="Secre Demo",
        email=email,
        password_hash=hashear_password("Secreta-123"),
        rol_id=rol_obj.id,
    )
    await sesion_pg.commit()
    return usuario


@pytest.mark.asyncio
async def test_login_ok_integracion_pg_redis(sesion_pg):
    """Task 2.2 integracion: login real emite access + cookie."""
    import jwt as pyjwt

    from app.core.deps import get_db, get_redis
    from app.main import create_app
    from httpx import ASGITransport, AsyncClient

    await _sembrar_usuario_pg(sesion_pg)
    redis_real = await _redis_real_o_skip()
    try:
        app = create_app()

        async def _db():
            yield sesion_pg

        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_redis] = lambda: redis_real
        transporte = ASGITransport(app=app)
        async with AsyncClient(transport=transporte, base_url="http://test") as cli:
            resp = await cli.post(
                "/auth/login",
                json={"email": "SECRE@demo.test", "password": "Secreta-123"},
            )
        assert resp.status_code == 200, resp.text
        datos = pyjwt.decode(
            resp.json()["access_token"], options={"verify_signature": False}
        )
        assert datos["rol"] == "secretaria"
        assert _refresh_de_set_cookie(resp) is not None
    finally:
        await redis_real.aclose()


@pytest.mark.asyncio
async def test_login_401_identico_integracion_pg_redis(sesion_pg):
    """Task 2.2 integracion: inexistente vs mala password, mismo 401."""
    from app.core.deps import get_db, get_redis
    from app.main import create_app
    from httpx import ASGITransport, AsyncClient

    await _sembrar_usuario_pg(sesion_pg)
    redis_real = await _redis_real_o_skip()
    try:
        app = create_app()

        async def _db():
            yield sesion_pg

        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_redis] = lambda: redis_real
        transporte = ASGITransport(app=app)
        async with AsyncClient(transport=transporte, base_url="http://test") as cli:
            r1 = await cli.post(
                "/auth/login", json={"email": "nadie@demo.test", "password": "x"}
            )
            r2 = await cli.post(
                "/auth/login",
                json={"email": "secre@demo.test", "password": "mala-999"},
            )
        assert r1.status_code == r2.status_code == 401
        assert r1.json() == r2.json() == {"detail": "credenciales inválidas"}
    finally:
        await redis_real.aclose()


# ---------------------------------------------------------------------------
# Task 2.3: refresh rotativo + logout + me (HTTP con fakes)
# ---------------------------------------------------------------------------

async def _login_y_refresh(cli) -> tuple[str, str]:
    """Login con la usuaria fake; retorna (access, refresh_plano)."""
    resp = await cli.post(
        "/auth/login", json={"email": "secre@demo.test", "password": "Secreta-123"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"], _refresh_de_set_cookie(resp)


@pytest.mark.asyncio
async def test_refresh_rota_e_invalida_anterior():
    """Task 2.3 RED: refresh valido -> par nuevo y cookie distinta."""
    from c03_fakes import FakeRepo, FakeStore, fabricar_usuario

    repo = FakeRepo([fabricar_usuario()])
    app, cliente = _app_con_fakes(repo, FakeStore())
    async with cliente as cli:
        _, refresh_viejo = await _login_y_refresh(cli)
        r = await cli.post("/auth/refresh", headers={"Cookie": f"refresh_token={refresh_viejo}"})
        assert r.status_code == 200, r.text
        refresh_nuevo = _refresh_de_set_cookie(r)
        assert refresh_nuevo is not None
        assert refresh_nuevo != refresh_viejo
        assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_reuso_refresh_rotado_401():
    """Task 2.3 RED: reusar el rotado -> 401 e invalida la familia (D-05)."""
    from c03_fakes import FakeRepo, FakeStore, fabricar_usuario

    repo = FakeRepo([fabricar_usuario()])
    app, cliente = _app_con_fakes(repo, FakeStore())
    async with cliente as cli:
        _, refresh_viejo = await _login_y_refresh(cli)
        primero = await cli.post(
            "/auth/refresh", headers={"Cookie": f"refresh_token={refresh_viejo}"}
        )
        assert primero.status_code == 200
        refresh_nuevo = _refresh_de_set_cookie(primero)
        segundo = await cli.post(
            "/auth/refresh", headers={"Cookie": f"refresh_token={refresh_viejo}"}
        )
        assert segundo.status_code == 401
        assert "set-cookie" not in segundo.headers
        # La familia quedo invalidada: ni el nuevo sirve.
        tercero = await cli.post(
            "/auth/refresh", headers={"Cookie": f"refresh_token={refresh_nuevo}"}
        )
        assert tercero.status_code == 401


@pytest.mark.asyncio
async def test_logout_invalida_refresh():
    """Task 2.3 RED: logout -> 200 + limpia cookie; refresh posterior 401."""
    from c03_fakes import FakeRepo, FakeStore, fabricar_usuario

    repo = FakeRepo([fabricar_usuario()])
    app, cliente = _app_con_fakes(repo, FakeStore())
    async with cliente as cli:
        _, refresh = await _login_y_refresh(cli)
        salida = await cli.post("/auth/logout", headers={"Cookie": f"refresh_token={refresh}"})
        assert salida.status_code == 200
        assert "refresh_token=" in salida.headers.get("set-cookie", "")
        posterior = await cli.post(
            "/auth/refresh", headers={"Cookie": f"refresh_token={refresh}"}
        )
        assert posterior.status_code == 401


@pytest.mark.asyncio
async def test_me_retorna_identidad_sin_hash():
    """Task 2.3 RED: GET /me con Bearer -> {id,email,nombre,rol}."""
    from c03_fakes import FakeRepo, FakeStore, fabricar_usuario

    repo = FakeRepo([fabricar_usuario(id=4, rol="odontologo")])
    app, cliente = _app_con_fakes(repo, FakeStore())
    async with cliente as cli:
        access, _ = await _login_y_refresh(cli)
        ok = await cli.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert ok.status_code == 200, ok.text
        assert ok.json() == {
            "id": 4,
            "email": "secre@demo.test",
            "nombre": "Usuaria 4",
            "rol": "odontologo",
        }
        sin = await cli.get("/auth/me")
        assert sin.status_code == 401
