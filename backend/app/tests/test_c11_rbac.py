"""C-11 tasks 2.3, 2.4, 4.7: permisos y superficie de rutas, sin base de datos.

El guard `require_role` rechaza antes de tocar la DB, así que los `401` y los `403` se prueban
con la app real y la identidad reemplazada. Los casos de éxito (200/201) viven en los tests de
API con Postgres. Datos ficticios.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

LIQ = "/liquidaciones"
COBRO = {"medio": "efectivo"}
GENERAR = {"os_id": 1, "periodo": "2026-10"}
MOTIVO = {"motivo": "error de carga"}
ARANCEL = {"plan_id": 1, "codigo_nomenclador": "N-1", "descripcion": "x", "precio": "10.00",
           "vigencia_desde": "2026-10-01"}

RUTAS_LIQ_ADMIN = [
    ("POST", LIQ, GENERAR),
    ("POST", f"{LIQ}/1/presentar", None),
    ("POST", f"{LIQ}/1/descartar", None),
    ("POST", f"{LIQ}/1/cobrar", COBRO),
    ("POST", f"{LIQ}/1/revertir-cobro", MOTIVO),
    ("GET", f"{LIQ}/1/export.csv", None),
    ("GET", f"{LIQ}/1/export.pdf", None),
]
RUTAS_LIQ_LECTURA = [("GET", LIQ, None), ("GET", f"{LIQ}/1", None)]
RUTAS_CATALOGO_ESCRITURA = [
    ("POST", "/obras-sociales", {"nombre": "OS"}),
    ("PATCH", "/obras-sociales/1", {"activa": False}),
    ("POST", "/planes", {"obra_social_id": 1, "nombre": "P"}),
    ("PATCH", "/planes/1", {"activo": False}),
    ("POST", "/aranceles", ARANCEL),
    ("PATCH", "/aranceles/1", {"vigencia_hasta": "2026-12-31"}),
]


@pytest.fixture
def app_con_rol():
    """Fábrica de clientes con la identidad reemplazada por un usuario del rol pedido."""
    from httpx import ASGITransport, AsyncClient

    from app.core.deps import get_current_user
    from app.main import create_app

    def _crear(rol: str | None):
        app = create_app()
        if rol is not None:
            usuario = SimpleNamespace(id=1, rol=SimpleNamespace(nombre=rol), activo=True)
            app.dependency_overrides[get_current_user] = lambda: usuario
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    return _crear


async def _llamar(cliente, metodo, url, cuerpo):
    async with cliente:
        return await cliente.request(metodo, url, json=cuerpo)


@pytest.mark.asyncio
@pytest.mark.parametrize("metodo,url,cuerpo", RUTAS_LIQ_ADMIN + RUTAS_LIQ_LECTURA)
async def test_liquidaciones_secretaria_recibe_403_en_todo_el_prefijo(
    app_con_rol, metodo, url, cuerpo
):
    r = await _llamar(app_con_rol("secretaria"), metodo, url, cuerpo)
    assert r.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("metodo,url,cuerpo", RUTAS_LIQ_ADMIN)
async def test_liquidaciones_odontologo_no_opera_ni_exporta(app_con_rol, metodo, url, cuerpo):
    r = await _llamar(app_con_rol("odontologo"), metodo, url, cuerpo)
    assert r.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metodo,url,cuerpo",
    RUTAS_LIQ_ADMIN + RUTAS_LIQ_LECTURA + RUTAS_CATALOGO_ESCRITURA
    + [("GET", "/obras-sociales", None), ("GET", "/planes", None), ("GET", "/aranceles", None),
       ("PUT", "/pacientes/1/plan", {"plan_id": None}),
       ("GET", "/validador-cobertura?paciente_id=1&tratamiento_id=1", None)],
)
async def test_sin_bearer_responde_401(app_con_rol, metodo, url, cuerpo):
    r = await _llamar(app_con_rol(None), metodo, url, cuerpo)
    assert r.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("rol", ["secretaria", "odontologo"])
@pytest.mark.parametrize("metodo,url,cuerpo", RUTAS_CATALOGO_ESCRITURA)
async def test_escritura_del_catalogo_solo_admin(app_con_rol, rol, metodo, url, cuerpo):
    r = await _llamar(app_con_rol(rol), metodo, url, cuerpo)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_odontologo_no_asigna_plan_ni_usa_el_validador(app_con_rol):
    r = await _llamar(app_con_rol("odontologo"), "PUT", "/pacientes/1/plan", {"plan_id": 1})
    assert r.status_code == 403
    r = await _llamar(app_con_rol("odontologo"), "GET",
                      "/validador-cobertura?paciente_id=1&tratamiento_id=1", None)
    assert r.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("url,cuerpo", [
    ("/caja/cobrar", {"presupuesto_id": 1, "monto": "1.00", "medio": "efectivo",
                      "clave_idempotencia": "00000000-0000-4000-8000-000000000000"}),
    ("/caja/cierre", {"caja_id": 1, "total_contado": "0.00"}),
])
async def test_admin_sigue_sin_poder_cobrar_ni_cerrar_por_caja(app_con_rol, url, cuerpo):
    r = await _llamar(app_con_rol("admin"), "POST", url, cuerpo)
    assert r.status_code == 403


def test_no_hay_rutas_para_editar_importes_ni_borrar():
    from app.main import create_app

    rutas = {(m, r.path) for r in create_app().routes if hasattr(r, "methods")
             for m in r.methods}
    for prefijo in ("/liquidaciones", "/aranceles", "/obras-sociales", "/planes"):
        modificadoras = {(m, p) for m, p in rutas
                         if p.startswith(prefijo) and m in ("PUT", "DELETE")}
        assert modificadoras == set(), modificadoras
    # PATCH de aranceles es la única edición, y solo declara vigencia_hasta.
    assert ("PATCH", "/liquidaciones/{liquidacion_id}") not in rutas
    assert not any(p.startswith("/os") and not p.startswith("/obras") for _, p in rutas)
