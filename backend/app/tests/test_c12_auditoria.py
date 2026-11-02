"""C-12 7.2: auditoria de acciones admin (R3, D-10) sobre repos falsos (corre sin Postgres).

Alta, edicion, desactivacion y eliminacion de usuario, importacion y exportacion registran un
evento sin contrasenas; un 4xx no registra; `GET /admin/auditoria` lista del mas reciente al mas
antiguo con paginacion. El repo real (orden, FK, inmutabilidad) se prueba en Postgres real
(`test_pg_*`; sin Postgres se saltean y deben reportarse como NO EJECUTADAS).
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c12_fakes import FakeDb, FakeRepoAdmin, app_admin_con, fabricar_usuario, override_auditoria  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

ALTA = {"nombre": "Sofía Nueva", "email": "sofia.nueva@example.com", "password": "Clave-1234", "rol": "secretaria"}


def _repo(admins: int = 2) -> FakeRepoAdmin:
    usuarios = [fabricar_usuario(id=i, rol="admin", email=f"admin{i}@demo.test") for i in range(1, admins + 1)]
    usuarios.append(fabricar_usuario(id=10, rol="secretaria", email="secre@demo.test"))
    return FakeRepoAdmin(usuarios)


# --- eventos de usuario ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_alta_registra_un_evento_con_el_admin_como_actor_y_sin_la_contrasena():
    _, cli, bearer, db = app_admin_con(_repo())
    async with cli:
        r = await cli.post("/admin/usuarios", json=ALTA, headers=bearer(1, "admin"))
    assert r.status_code == 201
    (evento,) = db.auditoria.eventos
    assert (evento.actor_id, evento.accion, evento.objeto_tipo) == (1, "usuario_alta", "usuario")
    assert evento.objeto_id == r.json()["id"] and evento.detalle == {"rol": "secretaria"}
    assert ALTA["password"] not in str(evento.__dict__)


@pytest.mark.asyncio
async def test_edicion_registra_los_campos_cambiados_pero_nunca_la_contrasena():
    _, cli, bearer, db = app_admin_con(_repo())
    async with cli:
        r = await cli.patch("/admin/usuarios/10", headers=bearer(1, "admin"),
                            json={"rol": "odontologo", "password": "Nueva-98765", "nombre": "Otro Nombre"})
    assert r.status_code == 200
    (evento,) = db.auditoria.eventos
    assert (evento.actor_id, evento.accion, evento.objeto_id) == (1, "usuario_edicion", 10)
    assert sorted(evento.detalle["campos"]) == ["nombre", "password", "rol"]
    assert evento.detalle["rol"] == "odontologo"
    assert "Nueva-98765" not in str(evento.__dict__)


@pytest.mark.asyncio
async def test_reactivar_se_registra_como_edicion_y_un_cuerpo_vacio_no_registra():
    repo = FakeRepoAdmin([
        fabricar_usuario(id=1, rol="admin", email="a@demo.test"),
        fabricar_usuario(id=2, rol="secretaria", email="s@demo.test", activo=False),
    ])
    _, cli, bearer, db = app_admin_con(repo)
    async with cli:
        await cli.patch("/admin/usuarios/2", json={}, headers=bearer(1, "admin"))
        await cli.patch("/admin/usuarios/2", json={"activo": True}, headers=bearer(1, "admin"))
    (evento,) = db.auditoria.eventos
    assert evento.accion == "usuario_edicion" and evento.detalle["campos"] == ["activo"]


@pytest.mark.asyncio
async def test_desactivar_y_eliminar_registran_su_evento():
    _, cli, bearer, db = app_admin_con(_repo())
    async with cli:
        d = await cli.patch("/admin/usuarios/10/desactivar", headers=bearer(1, "admin"))
        e = await cli.delete("/admin/usuarios/10", headers=bearer(1, "admin"))
    assert (d.status_code, e.status_code) == (200, 204)
    assert [(x.accion, x.objeto_id, x.actor_id) for x in db.auditoria.eventos] == [
        ("usuario_desactivacion", 10, 1), ("usuario_eliminacion", 10, 1)]


@pytest.mark.asyncio
async def test_acciones_rechazadas_no_registran_ningun_evento():
    repo = FakeRepoAdmin(
        [fabricar_usuario(id=1, rol="admin", email="a@demo.test"),
         fabricar_usuario(id=10, rol="secretaria", email="secre@demo.test")],
        con_historial={10},
    )
    _, cli, bearer, db = app_admin_con(repo)
    h = bearer(1, "admin")
    async with cli:
        ultimo_desactivar = await cli.patch("/admin/usuarios/1/desactivar", headers=h)
        ultimo_rol = await cli.patch("/admin/usuarios/1", json={"rol": "secretaria"}, headers=h)
        ultimo_borrar = await cli.delete("/admin/usuarios/1", headers=h)
        con_historial = await cli.delete("/admin/usuarios/10", headers=h)
        email_repetido = await cli.post("/admin/usuarios", json={**ALTA, "email": "SECRE@demo.test"}, headers=h)
        invalido = await cli.post("/admin/usuarios", json={**ALTA, "password": "corta"}, headers=h)
        inexistente = await cli.patch("/admin/usuarios/999", json={"nombre": "X"}, headers=h)
    assert [r.status_code for r in (ultimo_desactivar, ultimo_rol, ultimo_borrar, con_historial,
                                    email_repetido, invalido, inexistente)] == [409, 409, 409, 409, 409, 422, 404]
    assert db.auditoria.eventos == []


@pytest.mark.asyncio
async def test_secretaria_no_registra_nada_al_ser_rechazada_con_403():
    _, cli, bearer, db = app_admin_con(_repo())
    async with cli:
        r = await cli.post("/admin/usuarios", json=ALTA, headers=bearer(10, "secretaria"))
    assert r.status_code == 403 and db.auditoria.eventos == []


# --- GET /admin/auditoria --------------------------------------------------------------------------

async def _con_tres_eventos():
    _, cli, bearer, db = app_admin_con(_repo())
    h = bearer(1, "admin")
    async with cli:
        await cli.post("/admin/usuarios", json=ALTA, headers=h)
        await cli.patch("/admin/usuarios/10/desactivar", headers=h)
        await cli.patch("/admin/usuarios/10", json={"activo": True}, headers=h)
        return cli, h, db


@pytest.mark.asyncio
async def test_listado_ordena_del_mas_reciente_al_mas_antiguo_y_el_primero_es_la_ultima_accion():
    _, cli, bearer, _ = app_admin_con(_repo())
    h = bearer(1, "admin")
    async with cli:
        await cli.post("/admin/usuarios", json=ALTA, headers=h)
        await cli.patch("/admin/usuarios/10/desactivar", headers=h)
        lista = (await cli.get("/admin/auditoria", headers=h)).json()
    assert [e["accion"] for e in lista] == ["usuario_desactivacion", "usuario_alta"]
    assert set(lista[0]) == {"id", "actor_id", "accion", "objeto_tipo", "objeto_id", "detalle", "created_at"}


@pytest.mark.asyncio
async def test_listado_pagina_con_limit_y_offset():
    _, cli, bearer, _ = app_admin_con(_repo())
    h = bearer(1, "admin")
    async with cli:
        for i in range(5):
            await cli.post("/admin/usuarios", json={**ALTA, "email": f"n{i}@example.com"}, headers=h)
        pagina_1 = (await cli.get("/admin/auditoria?limit=2", headers=h)).json()
        pagina_2 = (await cli.get("/admin/auditoria?limit=2&offset=2", headers=h)).json()
        resto = (await cli.get("/admin/auditoria?limit=2&offset=4", headers=h)).json()
    assert [e["id"] for e in pagina_1] == [5, 4]
    assert [e["id"] for e in pagina_2] == [3, 2]
    assert [e["id"] for e in resto] == [1]


@pytest.mark.asyncio
@pytest.mark.parametrize("consulta", ["limit=0", "limit=201", "offset=-1", "limit=abc"])
async def test_listado_con_paginacion_invalida_422(consulta):
    _, cli, bearer, _ = app_admin_con(_repo())
    async with cli:
        r = await cli.get(f"/admin/auditoria?{consulta}", headers=bearer(1, "admin"))
    assert r.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("rol", ["secretaria", "odontologo"])
async def test_listado_solo_admin_403(rol):
    _, cli, bearer, _ = app_admin_con(_repo())
    async with cli:
        r = await cli.get("/admin/auditoria", headers=bearer(10, rol))
        sin = await cli.get("/admin/auditoria")
    assert r.status_code == 403 and sin.status_code == 401


# --- servicio de auditoria -------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("clave", ["password", "password_hash", "token", "contrasena"])
async def test_auditar_rechaza_un_detalle_con_claves_de_secretos(clave):
    from app.servicios.auditoria_servicio import auditar

    with pytest.raises(ValueError, match="secreto"):
        await auditar(override_auditoria_vacia(), 1, "usuario_alta", "usuario", 2, {clave: "x"})


def override_auditoria_vacia():
    from c12_fakes import FakeAuditoria

    return FakeAuditoria()


@pytest.mark.asyncio
async def test_auditar_sin_repo_no_hace_nada_y_con_repo_registra():
    from app.servicios.auditoria_servicio import auditar

    assert await auditar(None, 1, "usuario_alta", "usuario", 2, {"rol": "admin"}) is None
    repo = override_auditoria_vacia()
    await auditar(repo, 1, "usuario_alta", "usuario", 2, {"rol": "admin"})
    assert repo.eventos[0].detalle == {"rol": "admin"}


# --- importacion y exportacion ---------------------------------------------------------------------

def _app_con_fakes(rol: str):
    from app.api.turnos import get_paciente_repo
    from app.core.deps import get_current_user, get_db
    from app.main import create_app

    app = create_app()
    db = FakeDb()

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    auditoria = override_auditoria(app)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=7, rol=SimpleNamespace(nombre=rol), activo=True)
    return app, AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), db, auditoria, get_paciente_repo


@pytest.mark.asyncio
async def test_importacion_registra_un_evento_con_conteos_y_sin_filas():
    from test_c12_importacion import VALIDAS, FakePacientes, _csv

    app, cli, db, auditoria, get_paciente_repo = _app_con_fakes("secretaria")
    app.dependency_overrides[get_paciente_repo] = lambda: FakePacientes()
    contenido = _csv(*VALIDAS, "Dani,,,,")
    async with cli:
        r = await cli.post("/pacientes/import", files={"archivo": ("p.csv", contenido, "text/csv")})
    assert r.status_code == 200
    (evento,) = auditoria.eventos
    assert (evento.actor_id, evento.accion, evento.objeto_tipo) == (7, "pacientes_importacion", "importacion")
    assert evento.detalle == {"creados": 3, "rechazados": 1}
    assert "Ficticia" not in str(evento.__dict__) and "30111001" not in str(evento.__dict__)


@pytest.mark.asyncio
async def test_importacion_con_archivo_invalido_no_registra_evento():
    from test_c12_importacion import FakePacientes

    app, cli, db, auditoria, get_paciente_repo = _app_con_fakes("admin")
    app.dependency_overrides[get_paciente_repo] = lambda: FakePacientes()
    async with cli:
        r = await cli.post("/pacientes/import", files={"archivo": ("p.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 422 and auditoria.eventos == []


@pytest.mark.asyncio
async def test_exportacion_total_registra_un_evento_y_la_de_otro_rol_no():
    from app.api import admin as admin_api

    async def falso(_sesion) -> bytes:
        return b"PK"

    app, cli, db, auditoria, _ = _app_con_fakes("admin")
    admin_api_exportar = admin_api.exportar_total
    admin_api.exportar_total = falso
    try:
        async with cli:
            r = await cli.get("/admin/export-total")
    finally:
        admin_api.exportar_total = admin_api_exportar
    assert r.status_code == 200
    (evento,) = auditoria.eventos
    assert (evento.actor_id, evento.accion, evento.objeto_tipo) == (7, "exportacion_total", "exportacion")
    assert db.commits == 1

    _, cli, _, auditoria, _ = _app_con_fakes("secretaria")
    async with cli:
        r = await cli.get("/admin/export-total")
    assert r.status_code == 403 and auditoria.eventos == []


# --- /seguridad -----------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seguridad_lista_las_acciones_admin_porque_la_auditoria_existe():
    from app.main import create_app

    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as cli:
        cuerpo = (await cli.get("/seguridad")).json()
    assert any("Acciones de administración" in a for a in cuerpo["auditoria"])


# --- Postgres real ---------------------------------------------------------------------------------

async def _admin(sesion):
    from app.modelos import Rol, Usuario

    rol = Rol(nombre="admin")
    sesion.add(rol)
    await sesion.flush()
    admin = Usuario(nombre="Admin", email="a@demo.test", password_hash="no-login", rol_id=rol.id)
    sesion.add(admin)
    await sesion.flush()
    return admin


@pytest.mark.asyncio
async def test_pg_repo_registra_y_lista_del_mas_reciente_al_mas_antiguo_con_pagina(sesion_pg):
    from app.repos.auditoria_repo import AuditoriaRepository

    admin = await _admin(sesion_pg)
    repo = AuditoriaRepository(sesion_pg)
    for i in range(3):  # misma transaccion: created_at igual, el desempate es el id
        await repo.registrar(actor_id=admin.id, accion="usuario_alta", objeto_tipo="usuario",
                             objeto_id=i, detalle={"n": i})
    todos = await repo.listar_recientes(limit=10, offset=0)
    assert [e.objeto_id for e in todos] == [2, 1, 0]
    assert [e.objeto_id for e in await repo.listar_recientes(limit=1, offset=1)] == [1]


@pytest.mark.asyncio
async def test_pg_http_alta_audita_y_el_409_del_ultimo_admin_no(sesion_pg):
    import sqlalchemy as sa
    from c08_helpers import armar_cliente
    from c10_helpers import sembrar_c10

    m = await sembrar_c10(sesion_pg)
    admin_id = m.admin.id
    cli, bearer, _ = await armar_cliente(sesion_pg)
    h = bearer(m.admin, "admin")
    async with cli:
        creado = await cli.post("/admin/usuarios", json=ALTA, headers=h)
        bloqueado = await cli.patch(f"/admin/usuarios/{admin_id}/desactivar", headers=h)
        lista = (await cli.get("/admin/auditoria", headers=h)).json()
    assert creado.status_code == 201 and bloqueado.status_code == 409
    assert [(e["accion"], e["actor_id"]) for e in lista] == [("usuario_alta", admin_id)]
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM evento_auditoria")) == 1


@pytest.mark.asyncio
async def test_pg_el_borrado_de_un_actor_con_eventos_responde_409(sesion_pg):
    from c08_helpers import armar_cliente
    from c10_helpers import sembrar_c10

    m = await sembrar_c10(sesion_pg)
    otro_admin = (await _admin_extra(sesion_pg))
    cli, bearer, _ = await armar_cliente(sesion_pg)
    admin_id = m.admin.id
    h_admin, h_otro = bearer(m.admin, "admin"), bearer(otro_admin, "admin")  # antes de commitear
    async with cli:
        await cli.post("/admin/usuarios", json=ALTA, headers=h_admin)
        r = await cli.delete(f"/admin/usuarios/{admin_id}", headers=h_otro)
    assert r.status_code == 409


async def _admin_extra(sesion):
    from sqlalchemy import select

    from app.modelos import Rol, Usuario

    rol = await sesion.scalar(select(Rol).where(Rol.nombre == "admin"))
    otro = Usuario(nombre="Otro Admin", email="otro@demo.test", password_hash="no-login", rol_id=rol.id)
    sesion.add(otro)
    await sesion.flush()
    return otro
