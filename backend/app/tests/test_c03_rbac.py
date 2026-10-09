"""C-03 tasks 3.x: RBAC require_role + superficie admin minima."""
import sys
from pathlib import Path

import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: F401  (fixture PG real con skip sin Docker)

from app.core.deps import get_current_user, get_usuario_repo, require_role
from app.main import create_app
from c03_fakes import FakeRepo, FakeStore, fabricar_usuario


@pytest.mark.asyncio
async def test_ruta_admin_con_secretaria_403():
    """Task 3.1 RED: secretaria en ruta admin -> 403; admin -> 200."""
    app = create_app()
    guard = require_role("admin")

    @app.get("/solo-admin")
    def solo_admin(usuario=Depends(guard)) -> dict:
        return {"rol": usuario.rol.nombre}

    transporte = ASGITransport(app=app)
    app.dependency_overrides[get_current_user] = lambda: fabricar_usuario(
        rol="secretaria"
    )
    async with AsyncClient(transport=transporte, base_url="http://test") as cli:
        r403 = await cli.get("/solo-admin")
    assert r403.status_code == 403
    assert r403.json() == {"detail": "sin permiso"}

    app.dependency_overrides[get_current_user] = lambda: fabricar_usuario(rol="admin")
    async with AsyncClient(transport=transporte, base_url="http://test") as cli:
        r200 = await cli.get("/solo-admin")
    assert r200.status_code == 200
    assert r200.json() == {"rol": "admin"}


@pytest.mark.asyncio
async def test_bearer_expirado_401_con_freezegun():
    """Task 3.1 RED: Bearer vencido (freezegun) -> 401 via get_current_user."""
    from freezegun import freeze_time

    from app.core.security import crear_access_token

    app = create_app()
    app.dependency_overrides[get_usuario_repo] = lambda: FakeRepo(
        [fabricar_usuario()]
    )
    transporte = ASGITransport(app=app)
    with freeze_time("2026-10-01 12:00:00"):
        token = crear_access_token(1, "secretaria")
    with freeze_time("2026-10-01 12:31:00"):
        async with AsyncClient(
            transport=transporte, base_url="http://test"
        ) as cli:
            resp = await cli.get(
                "/auth/me", headers={"Authorization": f"Bearer {token}"}
            )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_usuario_desactivado_401():
    """Task 3.1 RED: usuario desactivado con Bearer valido -> 401."""
    from app.core.security import crear_access_token

    app = create_app()
    app.dependency_overrides[get_usuario_repo] = lambda: FakeRepo(
        [fabricar_usuario(activo=False)]
    )
    transporte = ASGITransport(app=app)
    token = crear_access_token(1, "secretaria")
    async with AsyncClient(transport=transporte, base_url="http://test") as cli:
        resp = await cli.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_guard_multirol_permite_incluido_y_bloquea_otro():
    """Triangulacion: require_role("admin", "odontologo") deja pasar odonto."""
    app = create_app()
    guard = require_role("admin", "odontologo")

    @app.get("/clinica-x")
    def clinica_x(usuario=Depends(guard)) -> dict:
        return {"rol": usuario.rol.nombre}

    transporte = ASGITransport(app=app)
    app.dependency_overrides[get_current_user] = lambda: fabricar_usuario(
        rol="odontologo"
    )
    async with AsyncClient(transport=transporte, base_url="http://test") as cli:
        ok = await cli.get("/clinica-x")
    assert ok.status_code == 200
    app.dependency_overrides[get_current_user] = lambda: fabricar_usuario(
        rol="secretaria"
    )
    async with AsyncClient(transport=transporte, base_url="http://test") as cli:
        bloqueado = await cli.get("/clinica-x")
    assert bloqueado.status_code == 403


# ---------------------------------------------------------------------------
# Task 3.2: superficie admin minima (HTTP con fakes + integracion PG real)
# ---------------------------------------------------------------------------

def _app_admin_con(repo):
    from app.core.security import crear_access_token

    app = create_app()
    app.dependency_overrides[get_usuario_repo] = lambda: repo
    transporte = ASGITransport(app=app)
    cliente = AsyncClient(transport=transporte, base_url="http://test")

    def _bearer(usuario_id: int, rol: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {crear_access_token(usuario_id, rol)}"}

    return app, cliente, _bearer


@pytest.mark.asyncio
async def test_admin_lista_solo_admin_y_sin_hash():
    """Task 3.2 RED: secretaria -> 403; admin -> 200 sin password_hash."""
    repo = FakeRepo(
        [
            fabricar_usuario(id=1, rol="admin", email="admin@demo.test"),
            fabricar_usuario(id=2, rol="secretaria", email="secre@demo.test"),
        ]
    )
    app, cliente, bearer = _app_admin_con(repo)
    async with cliente as cli:
        r403 = await cli.get("/admin/usuarios", headers=bearer(2, "secretaria"))
        assert r403.status_code == 403
        r200 = await cli.get("/admin/usuarios", headers=bearer(1, "admin"))
        assert r200.status_code == 200, r200.text
        cuerpo = r200.json()
        assert len(cuerpo) == 2
        assert cuerpo[0]["rol"] == "admin"
        assert all("password_hash" not in u for u in cuerpo)
        sin_token = await cli.get("/admin/usuarios")
        assert sin_token.status_code == 401


@pytest.mark.asyncio
async def test_desactivar_unico_admin_via_http_409():
    """Task 3.2 RED: desactivar al unico admin -> 409 y sigue activo."""
    repo = FakeRepo([fabricar_usuario(id=1, rol="admin", email="admin@demo.test")])
    app, cliente, bearer = _app_admin_con(repo)
    async with cliente as cli:
        resp = await cli.patch(
            "/admin/usuarios/1/desactivar", headers=bearer(1, "admin")
        )
    assert resp.status_code == 409
    assert repo._usuarios[1].activo is True


@pytest.mark.asyncio
async def test_eliminar_unico_admin_via_http_409():
    """Task 3.2 RED: eliminar al unico admin -> 409 y sigue existiendo."""
    repo = FakeRepo([fabricar_usuario(id=1, rol="admin", email="admin@demo.test")])
    app, cliente, bearer = _app_admin_con(repo)
    async with cliente as cli:
        resp = await cli.delete("/admin/usuarios/1", headers=bearer(1, "admin"))
    assert resp.status_code == 409
    assert 1 in repo._usuarios


@pytest.mark.asyncio
async def test_con_dos_admins_desactivar_ok():
    """Task 3.2 RED: con 2 admins, desactivar uno -> 200 con activo=false."""
    repo = FakeRepo(
        [
            fabricar_usuario(id=1, rol="admin", email="uno@demo.test"),
            fabricar_usuario(id=2, rol="admin", email="dos@demo.test"),
        ]
    )
    app, cliente, bearer = _app_admin_con(repo)
    async with cliente as cli:
        resp = await cli.patch(
            "/admin/usuarios/1/desactivar", headers=bearer(2, "admin")
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["activo"] is False
    assert repo._usuarios[2].activo is True


@pytest.mark.asyncio
async def test_admin_usuario_inexistente_404():
    """Triangulacion: desactivar/eliminar id fantasma -> 404."""
    repo = FakeRepo([fabricar_usuario(id=1, rol="admin", email="uno@demo.test")])
    app, cliente, bearer = _app_admin_con(repo)
    async with cliente as cli:
        r1 = await cli.patch(
            "/admin/usuarios/999/desactivar", headers=bearer(1, "admin")
        )
        r2 = await cli.delete("/admin/usuarios/999", headers=bearer(1, "admin"))
    assert r1.status_code == 404
    assert r2.status_code == 404


# ---------------------------------------------------------------------------
# Task 3.2 integracion: PG real (skip sin Docker/compose)
# ---------------------------------------------------------------------------

async def _sembrar_admins_pg(sesion_pg, cantidad: int = 1):
    from sqlalchemy import select

    from app.core.security import hashear_password
    from app.modelos import Rol
    from app.repos import RolRepository, UsuarioRepository

    await RolRepository(sesion_pg).crear(nombre="admin")
    await RolRepository(sesion_pg).crear(nombre="odontologo")
    await RolRepository(sesion_pg).crear(nombre="secretaria")
    rol_admin = await sesion_pg.scalar(select(Rol).where(Rol.nombre == "admin"))
    ids = []
    for i in range(cantidad):
        usuario = await UsuarioRepository(sesion_pg).crear(
            nombre=f"Admin {i}",
            email=f"admin{i}@demo.test",
            password_hash=hashear_password("Secreta-123"),
            rol_id=rol_admin.id,
        )
        ids.append(usuario.id)
    await sesion_pg.commit()
    return ids


@pytest.mark.asyncio
async def test_desactivar_unico_admin_integracion_pg_409(sesion_pg):
    """Task 3.2 integracion: unico admin via HTTP -> 409 y sigue activo."""
    from app.core.deps import get_db
    from app.core.security import crear_access_token
    from app.repos import UsuarioRepository

    (admin_id,) = await _sembrar_admins_pg(sesion_pg, 1)
    app = create_app()

    async def _db():
        yield sesion_pg

    app.dependency_overrides[get_db] = _db
    transporte = ASGITransport(app=app)
    token = crear_access_token(admin_id, "admin")
    async with AsyncClient(transport=transporte, base_url="http://test") as cli:
        resp = await cli.patch(
            f"/admin/usuarios/{admin_id}/desactivar",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 409
    sesion_pg.expire_all()
    assert (await UsuarioRepository(sesion_pg).get(admin_id)).activo is True


@pytest.mark.asyncio
async def test_con_dos_admins_integracion_pg_ok(sesion_pg):
    """Task 3.2 integracion: con 2 admins, desactivar uno -> 200."""
    from app.core.deps import get_db
    from app.core.security import crear_access_token

    primero, segundo = await _sembrar_admins_pg(sesion_pg, 2)
    app = create_app()

    async def _db():
        yield sesion_pg

    app.dependency_overrides[get_db] = _db
    transporte = ASGITransport(app=app)
    token = crear_access_token(segundo, "admin")
    async with AsyncClient(transport=transporte, base_url="http://test") as cli:
        resp = await cli.patch(
            f"/admin/usuarios/{primero}/desactivar",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["activo"] is False
