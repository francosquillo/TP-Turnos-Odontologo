"""C-10 grupo 7.5: matriz RBAC de caja y recibos (D-16) con HTTP + PG reales.

Los guards por rol se resuelven ANTES de mirar el recurso, así que los 403 usan ids
ficticios. Para los roles permitidos se comprueba que NO sean 401/403 (el recurso ficticio
da 404/422/409). Datos ficticios.
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente  # noqa: E402
from c10_helpers import clave_nueva, contar, crear_presupuesto_aceptado, sembrar_c10  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

COBRO = {"presupuesto_id": 987654, "monto": "10.00", "medio": "efectivo",
         "clave_idempotencia": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"}

# (método, ruta, cuerpo, roles permitidos)
RUTAS = [
    ("POST", "/caja/cobrar", COBRO, {"sec"}),
    ("POST", "/caja/cierre", {"caja_id": 987654, "total_contado": "0"}, {"sec"}),
    ("POST", "/recibos/987654/anular", {"motivo": "x"}, {"admin"}),
    ("GET", "/caja", None, {"sec", "admin"}),
    ("GET", "/recibos?fecha=2026-10-31", None, {"sec", "admin"}),
]


async def _mundo(sesion):
    m = await sembrar_c10(sesion)
    cli, bearer, _ = await armar_cliente(sesion)
    hdr = {"sec": bearer(m.secretaria, "secretaria"), "admin": bearer(m.admin, "admin"),
           "odo": bearer(m.odo_a, "odontologo")}
    return cli, hdr, m


@pytest.mark.asyncio
@pytest.mark.parametrize("rol", ["sec", "admin", "odo"])
@pytest.mark.parametrize("metodo,ruta,cuerpo,permitidos", RUTAS)
async def test_matriz_de_roles_por_ruta(sesion_pg, rol, metodo, ruta, cuerpo, permitidos):
    cli, hdr, _ = await _mundo(sesion_pg)
    async with cli:
        r = await cli.request(metodo, ruta, json=cuerpo, headers=hdr[rol])
    if rol in permitidos:
        assert r.status_code not in (401, 403), (r.status_code, r.text)
    else:
        assert r.status_code == 403
    assert await contar(sesion_pg, "caja") == 0 and await contar(sesion_pg, "recibo") == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("metodo,ruta,cuerpo,permitidos", RUTAS)
async def test_sin_bearer_401(sesion_pg, metodo, ruta, cuerpo, permitidos):
    cli, _, _ = await _mundo(sesion_pg)
    async with cli:
        r = await cli.request(metodo, ruta, json=cuerpo)
        mal = await cli.request(metodo, ruta, json=cuerpo, headers={"Authorization": "Bearer roto"})
    assert r.status_code == 401 and mal.status_code == 401


@pytest.mark.asyncio
async def test_admin_no_cobra_403(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    p, _ = await crear_presupuesto_aceptado(sesion_pg, m)
    pid = p.id
    cli, bearer, _ = await armar_cliente(sesion_pg)
    cuerpo = {**COBRO, "presupuesto_id": pid, "clave_idempotencia": clave_nueva()}
    async with cli:
        r = await cli.post("/caja/cobrar", json=cuerpo, headers=bearer(m.admin, "admin"))
    assert r.status_code == 403
    assert await contar(sesion_pg, "recibo") == 0 and await contar(sesion_pg, "caja") == 0


@pytest.mark.asyncio
async def test_admin_reintento_de_clave_existente_403(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    p, _ = await crear_presupuesto_aceptado(sesion_pg, m)
    pid = p.id
    cli, bearer, _ = await armar_cliente(sesion_pg)
    cuerpo = {**COBRO, "presupuesto_id": pid, "clave_idempotencia": clave_nueva()}
    async with cli:
        creado = await cli.post("/caja/cobrar", json=cuerpo, headers=bearer(m.secretaria, "secretaria"))
        admin = await cli.post("/caja/cobrar", json=cuerpo, headers=bearer(m.admin, "admin"))
        odo = await cli.post("/caja/cobrar", json=cuerpo, headers=bearer(m.odo_a, "odontologo"))
    assert creado.status_code == 201
    assert admin.status_code == 403 and odo.status_code == 403
    assert "numero" not in admin.text and "monto" not in admin.text  # no revela el recibo


@pytest.mark.asyncio
async def test_admin_no_cierra_403(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    p, _ = await crear_presupuesto_aceptado(sesion_pg, m)
    pid = p.id
    cli, bearer, _ = await armar_cliente(sesion_pg)
    sec, admin = bearer(m.secretaria, "secretaria"), bearer(m.admin, "admin")
    async with cli:
        await cli.post("/caja/cobrar", json={**COBRO, "presupuesto_id": pid}, headers=sec)
        caja_id = (await cli.get("/caja", headers=sec)).json()["caja"]["id"]
        r = await cli.post("/caja/cierre", json={"caja_id": caja_id, "total_contado": "10.00"}, headers=admin)
        estado = (await cli.get("/caja", headers=sec)).json()["caja"]["estado"]
    assert r.status_code == 403 and estado == "abierta"


@pytest.mark.asyncio
async def test_secretaria_no_anula_403(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    p, _ = await crear_presupuesto_aceptado(sesion_pg, m)
    pid = p.id
    cli, bearer, _ = await armar_cliente(sesion_pg)
    sec = bearer(m.secretaria, "secretaria")
    async with cli:
        cobro = (await cli.post("/caja/cobrar", json={**COBRO, "presupuesto_id": pid}, headers=sec)).json()
        r = await cli.post(f"/recibos/{cobro['id']}/anular", json={"motivo": "x"}, headers=sec)
        lista = await cli.get("/recibos?fecha=2026-10-31", headers=sec)
    assert r.status_code == 403 and lista.status_code == 200
    assert await contar(sesion_pg, "movimiento_caja") == 1


@pytest.mark.asyncio
async def test_odontologo_sin_acceso_403(sesion_pg):
    cli, hdr, _ = await _mundo(sesion_pg)
    async with cli:
        respuestas = [
            await cli.request(metodo, ruta, json=cuerpo, headers=hdr["odo"])
            for metodo, ruta, cuerpo, _ in RUTAS
        ]
    assert [r.status_code for r in respuestas] == [403] * len(RUTAS)
