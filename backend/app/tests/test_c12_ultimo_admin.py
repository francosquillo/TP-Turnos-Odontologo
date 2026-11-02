"""C-12 2.3: resguardo del ultimo admin ampliado (D-03) y DELETE con historial (D-04).

Primera parte: repos falsos (corre sin Postgres). Segunda parte: Postgres real (lock
`FOR UPDATE`, FK RESTRICT reales, dos sesiones). Sin Postgres, la segunda parte se saltea y
debe reportarse como NO EJECUTADA.
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c12_fakes import FakeRepoAdmin, app_admin_con, fabricar_usuario  # noqa: E402
from db_utils import _engine_or_skip, sesion_pg  # noqa: E402, F401


def _repo_con_admins(cantidad: int, **extra) -> FakeRepoAdmin:
    usuarios = [
        fabricar_usuario(id=i, rol="admin", email=f"admin{i}@demo.test") for i in range(1, cantidad + 1)
    ]
    usuarios.append(fabricar_usuario(id=10, rol="secretaria", email="secre@demo.test"))
    return FakeRepoAdmin(usuarios, **extra)


# --- cambio de rol (repos falsos) ------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("rol_nuevo", ["secretaria", "odontologo"])
async def test_quitar_rol_admin_al_unico_admin_409_y_sigue_admin(rol_nuevo):
    repo = _repo_con_admins(1)
    _, cli, bearer, db = app_admin_con(repo)
    async with cli:
        r = await cli.patch("/admin/usuarios/1", json={"rol": rol_nuevo}, headers=bearer(1, "admin"))
    assert r.status_code == 409 and "admin" in r.json()["detail"]
    assert repo._usuarios[1].rol.nombre == "admin"
    assert db.rollbacks == 1 and db.commits == 0


@pytest.mark.asyncio
async def test_quitar_rol_admin_con_otro_admin_activo_200():
    repo = _repo_con_admins(2)
    _, cli, bearer, _ = app_admin_con(repo)
    async with cli:
        r = await cli.patch("/admin/usuarios/1", json={"rol": "secretaria"}, headers=bearer(2, "admin"))
    assert r.status_code == 200 and r.json()["rol"] == "secretaria"
    assert repo._usuarios[2].rol.nombre == "admin"


@pytest.mark.asyncio
async def test_el_otro_admin_inactivo_no_cuenta_como_respaldo():
    repo = FakeRepoAdmin([
        fabricar_usuario(id=1, rol="admin", email="a1@demo.test"),
        fabricar_usuario(id=2, rol="admin", email="a2@demo.test", activo=False),
    ])
    _, cli, bearer, _ = app_admin_con(repo)
    async with cli:
        r = await cli.patch("/admin/usuarios/1", json={"rol": "secretaria"}, headers=bearer(1, "admin"))
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_cambiar_rol_a_admin_o_mantenerlo_no_dispara_el_guard():
    repo = _repo_con_admins(1)
    _, cli, bearer, _ = app_admin_con(repo)
    async with cli:
        promover = await cli.patch("/admin/usuarios/10", json={"rol": "admin"}, headers=bearer(1, "admin"))
        mantener = await cli.patch("/admin/usuarios/1", json={"rol": "admin"}, headers=bearer(1, "admin"))
    assert promover.status_code == 200 and mantener.status_code == 200


# --- DELETE con historial (repos falsos) -----------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_con_turno_o_profesional_409_y_no_borra():
    repo = _repo_con_admins(1, con_historial={10})
    _, cli, bearer, db = app_admin_con(repo)
    async with cli:
        r = await cli.delete("/admin/usuarios/10", headers=bearer(1, "admin"))
    assert r.status_code == 409 and "desactivalo" in r.json()["detail"]
    assert 10 in repo._usuarios
    assert db.rollbacks == 1 and db.commits == 0


@pytest.mark.asyncio
async def test_delete_con_fk_restrict_responde_409_con_rollback_y_no_borra():
    repo = _repo_con_admins(1, con_fk={10})
    _, cli, bearer, db = app_admin_con(repo)
    async with cli:
        r = await cli.delete("/admin/usuarios/10", headers=bearer(1, "admin"))
    assert r.status_code == 409 and "desactivalo" in r.json()["detail"]
    assert 10 in repo._usuarios and db.rollbacks == 1


@pytest.mark.asyncio
async def test_delete_sin_historial_204_y_confirma():
    repo = _repo_con_admins(1)
    _, cli, bearer, db = app_admin_con(repo)
    async with cli:
        r = await cli.delete("/admin/usuarios/10", headers=bearer(1, "admin"))
    assert r.status_code == 204 and 10 not in repo._usuarios and db.commits == 1


@pytest.mark.asyncio
async def test_desactivar_confirma_la_transaccion_y_el_409_no():
    repo = _repo_con_admins(2)
    _, cli, bearer, db = app_admin_con(repo)
    async with cli:
        ok = await cli.patch("/admin/usuarios/10/desactivar", headers=bearer(1, "admin"))
        uno = await cli.patch("/admin/usuarios/2/desactivar", headers=bearer(1, "admin"))
        ultimo = await cli.patch("/admin/usuarios/1/desactivar", headers=bearer(1, "admin"))
    assert ok.status_code == 200 and uno.status_code == 200 and ultimo.status_code == 409
    assert db.commits == 2 and db.rollbacks == 1


# --- Postgres real ---------------------------------------------------------------------------------

@pytest_asyncio.fixture
async def fabrica_pg():
    """Fabrica de sesiones independientes sobre PG real (para probar concurrencia)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.modelos import Base

    engine = await _engine_or_skip()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


async def _sembrar_dos_admins(fabrica) -> tuple[int, int]:
    from app.modelos import Rol, Usuario

    async with fabrica() as sesion:
        roles = {n: Rol(nombre=n) for n in ("admin", "odontologo", "secretaria")}
        sesion.add_all(roles.values())
        await sesion.flush()
        admins = [
            Usuario(nombre=f"Admin {i}", email=f"admin{i}@demo.test", password_hash="no-login",
                    rol_id=roles["admin"].id)
            for i in (1, 2)
        ]
        sesion.add_all(admins)
        await sesion.flush()
        ids = (admins[0].id, admins[1].id)
        await sesion.commit()
    return ids


@pytest.mark.asyncio
async def test_pg_el_lock_serializa_dos_desactivaciones_y_la_segunda_ve_un_solo_admin(fabrica_pg):
    from app.repos import UsuarioRepository
    from app.servicios.usuarios_servicio import UltimoAdminError, desactivar_usuario

    id1, id2 = await _sembrar_dos_admins(fabrica_pg)
    async with fabrica_pg() as sesion_a, fabrica_pg() as sesion_b:
        await desactivar_usuario(UsuarioRepository(sesion_a), id1)  # A retiene el lock
        tarea_b = asyncio.create_task(desactivar_usuario(UsuarioRepository(sesion_b), id2))
        await asyncio.sleep(0.5)
        assert not tarea_b.done(), "B deberia esperar el lock FOR UPDATE de A"
        await sesion_a.commit()
        with pytest.raises(UltimoAdminError):
            await tarea_b
        await sesion_b.rollback()
    async with fabrica_pg() as sesion:
        activos = await UsuarioRepository(sesion).listar_admins_activos()
        assert [a.id for a in activos] == [id2]


@pytest.mark.asyncio
async def test_pg_dos_desactivaciones_concurrentes_por_http_una_200_otra_409_y_queda_un_admin(fabrica_pg):
    from httpx import ASGITransport, AsyncClient

    from app.core.deps import get_current_user, get_db
    from app.main import create_app
    from app.repos import UsuarioRepository

    id1, id2 = await _sembrar_dos_admins(fabrica_pg)
    async def pedir_desactivar(objetivo: int, actor_id: int) -> int:
        # El actor debe existir: la auditoria referencia `usuario.id` por FK.
        quien_llama = SimpleNamespace(id=actor_id, rol=SimpleNamespace(nombre="admin"), activo=True)
        app = create_app()
        async with fabrica_pg() as sesion:
            async def _db():
                yield sesion

            app.dependency_overrides[get_db] = _db
            app.dependency_overrides[get_current_user] = lambda: quien_llama
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cli:
                r = await cli.patch(f"/admin/usuarios/{objetivo}/desactivar")
            return r.status_code

    estados = sorted(await asyncio.gather(pedir_desactivar(id1, id2), pedir_desactivar(id2, id1)))
    assert estados == [200, 409]
    async with fabrica_pg() as sesion:
        assert len(await UsuarioRepository(sesion).listar_admins_activos()) == 1


@pytest.mark.asyncio
async def test_pg_quitar_rol_al_unico_admin_409_y_sigue_siendo_admin(sesion_pg):
    from c08_helpers import armar_cliente
    from c10_helpers import sembrar_c10

    m = await sembrar_c10(sesion_pg)
    admin_id = m.admin.id
    cli, bearer, _ = await armar_cliente(sesion_pg)
    h = bearer(m.admin, "admin")  # antes del 1er request: el commit expira `m.admin`
    async with cli:
        r = await cli.patch(f"/admin/usuarios/{admin_id}", json={"rol": "secretaria"},
                            headers=h)
        lista = await cli.get("/admin/usuarios", headers=h)
    assert r.status_code == 409
    assert [u["rol"] for u in lista.json() if u["id"] == admin_id] == ["admin"]


@pytest.mark.asyncio
async def test_pg_delete_de_usuario_con_recibo_409_y_nada_se_borra(sesion_pg):
    from c08_helpers import armar_cliente
    from c10_helpers import crear_recibo, sembrar_c10

    m = await sembrar_c10(sesion_pg)
    secretaria_id = m.secretaria.id
    await crear_recibo(sesion_pg, m)  # emitido_por = secretaria (FK RESTRICT)
    cli, bearer, _ = await armar_cliente(sesion_pg)
    h = bearer(m.admin, "admin")  # antes del 1er request: el commit expira `m.admin`
    async with cli:
        r = await cli.delete(f"/admin/usuarios/{secretaria_id}", headers=h)
        lista = await cli.get("/admin/usuarios", headers=h)
    assert r.status_code == 409 and "desactivalo" in r.json()["detail"]
    assert secretaria_id in [u["id"] for u in lista.json()]


@pytest.mark.asyncio
async def test_pg_delete_de_usuario_que_creo_un_turno_409_y_conserva_la_autoria(sesion_pg):
    from c08_helpers import armar_cliente, crear_turno
    from c10_helpers import sembrar_c10

    m = await sembrar_c10(sesion_pg)
    creador_id = m.odo_sin_prof.id
    turno = await crear_turno(sesion_pg, m.ana, m.prof_a, m.sillon)
    turno.creado_por = creador_id
    turno_id = turno.id
    await sesion_pg.flush()
    cli, bearer, _ = await armar_cliente(sesion_pg)
    async with cli:
        r = await cli.delete(f"/admin/usuarios/{creador_id}", headers=bearer(m.admin, "admin"))
    assert r.status_code == 409
    from app.modelos import Turno

    sesion_pg.expire_all()
    assert (await sesion_pg.get(Turno, turno_id)).creado_por == creador_id


@pytest.mark.asyncio
async def test_pg_delete_de_usuario_sin_historial_204(sesion_pg):
    from c08_helpers import armar_cliente
    from c10_helpers import sembrar_c10

    m = await sembrar_c10(sesion_pg)
    libre_id = m.odo_sin_prof.id
    cli, bearer, _ = await armar_cliente(sesion_pg)
    async with cli:
        r = await cli.delete(f"/admin/usuarios/{libre_id}", headers=bearer(m.admin, "admin"))
        lista = await cli.get("/admin/usuarios", headers=bearer(m.admin, "admin"))
    assert r.status_code == 204
    assert libre_id not in [u["id"] for u in lista.json()]
