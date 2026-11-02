"""C-12 9.1: exportacion total en ZIP (D-12).

Primera parte: funciones puras y wiring del endpoint (corre sin Postgres). Segunda parte:
exportacion real sobre Postgres (sin Postgres se saltea y debe reportarse como NO EJECUTADA).
"""
import csv
import io
import sys
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: E402, F401


def _leer_csv(contenido: bytes) -> list[list[str]]:
    texto = contenido.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(texto), delimiter=";"))


def _zip(contenido: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(contenido))


# --- funciones puras -------------------------------------------------------------------------------

def test_columnas_exportables_excluyen_hashes_de_contrasena_y_de_token():
    from app.modelos import Base
    from app.servicios.exportacion_servicio import columnas_exportables

    nombres = {
        (t.name, c.name) for t in Base.metadata.sorted_tables for c in columnas_exportables(t)
    }
    assert not [n for n in nombres if "hash" in n[1]]
    todas = {(t.name, c.name) for t in Base.metadata.sorted_tables for c in t.columns}
    excluidas = todas - nombres
    assert ("usuario", "password_hash") in excluidas
    assert ("turno", "token_confirmacion_hash") in excluidas
    assert ("espera_entry", "token_oferta_hash") in excluidas
    # El contenido de los mensajes puede llevar enlaces con token: tampoco sale.
    assert ("notificacion", "payload") in excluidas


def test_hay_una_tabla_para_cada_entidad_de_negocio_pedida():
    from app.modelos import Base
    from app.servicios.exportacion_servicio import columnas_exportables

    con_columnas = {t.name for t in Base.metadata.sorted_tables if columnas_exportables(t)}
    assert {"paciente", "turno", "presupuesto", "movimiento", "recibo", "caja", "usuario"} <= con_columnas


def test_armar_zip_un_csv_por_tabla_mas_leeme_que_declara_datos_ficticios():
    from app.servicios.exportacion_servicio import TablaExportada, armar_zip

    tablas = [
        TablaExportada("paciente", ["id", "nombre"], [(1, "Ana")]),
        TablaExportada("caja", ["id", "fecha"], []),
    ]
    z = _zip(armar_zip(tablas, fecha=date(2026, 11, 2)))
    assert sorted(z.namelist()) == ["LEEME.txt", "caja.csv", "paciente.csv"]
    assert "ficticios" in z.read("LEEME.txt").decode("utf-8").lower()
    assert _leer_csv(z.read("paciente.csv")) == [["id", "nombre"], ["1", "Ana"]]
    assert _leer_csv(z.read("caja.csv")) == [["id", "fecha"]]  # tabla vacia: solo encabezado


def test_armar_zip_neutraliza_celdas_que_una_planilla_ejecutaria():
    from app.servicios.exportacion_servicio import TablaExportada, armar_zip

    peligrosas = ["=SUMA(1+1)", "+54 11", "-cmd", "@usuario", "\tTab"]
    filas = [(i, valor) for i, valor in enumerate(peligrosas)] + [(9, "texto normal")]
    z = _zip(armar_zip([TablaExportada("paciente", ["id", "nombre"], filas)], fecha=date(2026, 11, 2)))
    celdas = [fila[1] for fila in _leer_csv(z.read("paciente.csv"))[1:]]
    assert celdas[:5] == ["'" + v for v in peligrosas]
    assert celdas[5] == "texto normal"


def test_armar_zip_formatea_tipos_sin_neutralizar_numeros_negativos():
    from app.servicios.exportacion_servicio import TablaExportada, armar_zip

    fila = (Decimal("-5.50"), -3, None, True, datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc),
            date(2026, 11, 2), {"clave": "valor"})
    z = _zip(armar_zip([TablaExportada("movimiento", list("abcdefg"), [fila])], fecha=date(2026, 11, 2)))
    assert _leer_csv(z.read("movimiento.csv"))[1] == [
        "-5.50", "-3", "", "true", "2026-11-02T15:00:00+00:00", "2026-11-02", '{"clave": "valor"}',
    ]


# --- wiring del endpoint (sin Postgres) ------------------------------------------------------------

def _cliente(rol: str | None):
    from app.core.deps import get_current_user
    from app.main import create_app

    app = create_app()
    if rol is not None:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=1, rol=SimpleNamespace(nombre=rol), activo=True)
    return app, AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
@pytest.mark.parametrize("rol", ["secretaria", "odontologo"])
async def test_export_total_solo_admin_403(rol):
    _, cli = _cliente(rol)
    async with cli:
        r = await cli.get("/admin/export-total")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_export_total_sin_token_401():
    _, cli = _cliente(None)
    async with cli:
        r = await cli.get("/admin/export-total")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_export_total_admin_recibe_un_zip_adjunto_con_nombre_de_archivo(monkeypatch):
    from app.api import admin as admin_api
    from c12_fakes import FakeDb, override_auditoria
    from app.core.deps import get_db

    async def falso_exportar(_sesion) -> bytes:
        return b"PK-contenido"

    monkeypatch.setattr(admin_api, "exportar_total", falso_exportar)
    app, cli = _cliente("admin")

    async def _db():
        yield FakeDb()

    app.dependency_overrides[get_db] = _db
    override_auditoria(app)
    async with cli:
        r = await cli.get("/admin/export-total")
    assert r.status_code == 200 and r.content == b"PK-contenido"
    assert r.headers["content-type"] == "application/zip"
    assert r.headers["content-disposition"].startswith('attachment; filename="export-total-')
    assert r.headers["content-disposition"].endswith('.zip"')


# --- Postgres real ---------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pg_admin_descarga_zip_con_los_csv_de_negocio_que_coinciden_con_la_base(sesion_pg):
    import sqlalchemy as sa
    from c08_helpers import armar_cliente
    from c10_helpers import crear_caja, crear_recibo, sembrar_c10

    m = await sembrar_c10(sesion_pg)
    await crear_caja(sesion_pg, m, date(2026, 11, 2))
    await crear_recibo(sesion_pg, m, monto="100.00")
    cli, bearer, _ = await armar_cliente(sesion_pg)
    async with cli:
        r = await cli.get("/admin/export-total", headers=bearer(m.admin, "admin"))
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    z = _zip(r.content)
    nombres = set(z.namelist())
    assert {"paciente.csv", "turno.csv", "presupuesto.csv", "movimiento.csv", "recibo.csv",
            "caja.csv", "usuario.csv", "LEEME.txt"} <= nombres
    for tabla in ("paciente", "turno", "presupuesto", "movimiento", "recibo", "caja", "usuario"):
        filas = _leer_csv(z.read(f"{tabla}.csv"))
        en_base = await sesion_pg.scalar(sa.text(f"SELECT count(*) FROM {tabla}"))
        assert len(filas) - 1 == en_base, tabla
    assert "ficticios" in z.read("LEEME.txt").decode("utf-8").lower()


@pytest.mark.asyncio
async def test_pg_el_csv_de_usuarios_no_tiene_hash_ni_se_filtran_hashes_de_turno(sesion_pg):
    from c08_helpers import armar_cliente
    from c10_helpers import sembrar_c10

    m = await sembrar_c10(sesion_pg)
    cli, bearer, _ = await armar_cliente(sesion_pg)
    async with cli:
        r = await cli.get("/admin/export-total", headers=bearer(m.admin, "admin"))
    z = _zip(r.content)
    assert not any("hash" in col for nombre in z.namelist() if nombre.endswith(".csv")
                   for col in _leer_csv(z.read(nombre))[0])
    assert "no-login" not in b"".join(z.read(n) for n in z.namelist()).decode("utf-8")


@pytest.mark.asyncio
async def test_pg_una_celda_que_empieza_con_igual_sale_neutralizada(sesion_pg):
    from c08_helpers import armar_cliente
    from c10_helpers import sembrar_c10

    m = await sembrar_c10(sesion_pg)
    m.ana.apellido = "=HYPERLINK(\"http://x\")"
    await sesion_pg.flush()
    cli, bearer, _ = await armar_cliente(sesion_pg)
    async with cli:
        r = await cli.get("/admin/export-total", headers=bearer(m.admin, "admin"))
    filas = _leer_csv(_zip(r.content).read("paciente.csv"))
    columna = filas[0].index("apellido")
    assert "'=HYPERLINK(\"http://x\")" in [f[columna] for f in filas[1:]]


@pytest.mark.asyncio
async def test_pg_secretaria_403(sesion_pg):
    from c08_helpers import armar_cliente
    from c10_helpers import sembrar_c10

    m = await sembrar_c10(sesion_pg)
    cli, bearer, _ = await armar_cliente(sesion_pg)
    async with cli:
        r = await cli.get("/admin/export-total", headers=bearer(m.secretaria, "secretaria"))
    assert r.status_code == 403
