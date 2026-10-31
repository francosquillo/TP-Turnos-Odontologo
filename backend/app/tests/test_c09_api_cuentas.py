"""C-09 task 6.2: API de cuentas corrientes (HTTP real + PG real) (D-11, D-14, D-15).

Datos ficticios. Las pruebas de la matriz por rol viven en `test_c09_rbac.py`.
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente  # noqa: E402
from c09_helpers import sembrar_c09  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401


async def _mundo(sesion):
    m = await sembrar_c09(sesion)
    ids = {"ana": m.ana.id, "beto": m.beto.id, "h1": m.h1.id, "con": m.trat["CON-001"].id}
    cli, bearer, _ = await armar_cliente(sesion)
    hdr = {
        "odo": bearer(m.odo_a, "odontologo"), "sec": bearer(m.secretaria, "secretaria"),
        "admin": bearer(m.admin, "admin"),
    }
    return cli, hdr, ids


async def _con_cargo(cli, hdr, ids):
    """Presupuesto aceptado de 2001.00; devuelve (presupuesto, cargo)."""
    p = (await cli.post("/presupuestos", json={"paciente_id": ids["ana"], "items": [
        {"hallazgo_id": ids["h1"], "tratamiento_id": ids["con"], "cantidad": 2}]}, headers=hdr["odo"])).json()
    await cli.post(f"/presupuestos/{p['id']}/presentar", headers=hdr["odo"])
    assert (await cli.post(f"/presupuestos/{p['id']}/aceptar", headers=hdr["odo"])).status_code == 200
    cuenta = (await cli.get(f"/cuentas/{ids['ana']}", headers=hdr["sec"])).json()
    return p, cuenta["movimientos"][0]


@pytest.mark.asyncio
async def test_get_cuenta_200_vacia_y_con_cargo(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        vacia = await cli.get(f"/cuentas/{ids['ana']}", headers=hdr["sec"])
        p, cargo = await _con_cargo(cli, hdr, ids)
        con = await cli.get(f"/cuentas/{ids['ana']}", headers=hdr["admin"])
    assert vacia.status_code == 200 and vacia.json() == {
        "paciente_id": ids["ana"], "saldo": "0.00", "movimientos": []}
    assert con.status_code == 200 and con.json()["saldo"] == "2001.00"
    assert (cargo["tipo"], cargo["monto"], cargo["presupuesto_id"]) == ("cargo", "2001.00", p["id"])
    assert cargo["anulado"] is False and cargo["anula_a_id"] is None


@pytest.mark.asyncio
async def test_get_cuenta_404_paciente_inexistente(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.get("/cuentas/987654", headers=hdr["sec"])
    assert r.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("metodo", ["PUT", "PATCH", "DELETE"])
async def test_put_y_patch_cuenta_405(sesion_pg, metodo):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.request(metodo, f"/cuentas/{ids['ana']}", json={"saldo": "0.00"}, headers=hdr["admin"])
    assert r.status_code == 405


@pytest.mark.asyncio
async def test_post_movimientos_404(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    cuerpo = {"tipo": "pago", "monto": "-10.00", "concepto": "x"}
    async with cli:
        r = await cli.post(f"/cuentas/{ids['ana']}/movimientos", json=cuerpo, headers=hdr["admin"])
        otro = await cli.post(f"/cuentas/{ids['ana']}/pagos", json=cuerpo, headers=hdr["admin"])
    assert r.status_code in (404, 405) and otro.status_code == 404
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_anular_201_crea_contramovimiento_y_saldo_cero(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        p, cargo = await _con_cargo(cli, hdr, ids)
        r = await cli.post(
            f"/cuentas/{ids['ana']}/movimientos/{cargo['id']}/anular",
            json={"motivo": "Cargado por error"}, headers=hdr["admin"])
        cuenta = (await cli.get(f"/cuentas/{ids['ana']}", headers=hdr["sec"])).json()
        presupuesto = (await cli.get(f"/presupuestos/{p['id']}", headers=hdr["sec"])).json()
    assert r.status_code == 201
    assert (r.json()["tipo"], r.json()["monto"], r.json()["anula_a_id"]) == ("ajuste", "-2001.00", cargo["id"])
    assert cuenta["saldo"] == "0.00" and len(cuenta["movimientos"]) == 2
    assert {m["id"]: m["anulado"] for m in cuenta["movimientos"]}[cargo["id"]] is True
    assert presupuesto["estado"] == "aceptado" and presupuesto["cargo_anulado"] is True


@pytest.mark.asyncio
async def test_anular_409_dos_veces_pago_y_ajuste(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        _, cargo = await _con_cargo(cli, hdr, ids)
        url = f"/cuentas/{ids['ana']}/movimientos/{cargo['id']}/anular"
        ok = await cli.post(url, json={"motivo": "Error"}, headers=hdr["admin"])
        otra = await cli.post(url, json={"motivo": "Otra"}, headers=hdr["admin"])
        sobre_ajuste = await cli.post(
            f"/cuentas/{ids['ana']}/movimientos/{ok.json()['id']}/anular",
            json={"motivo": "x"}, headers=hdr["admin"])
    assert ok.status_code == 201 and otra.status_code == 409 and sobre_ajuste.status_code == 409


@pytest.mark.asyncio
async def test_anular_404_movimiento_de_otra_cuenta_o_inexistente(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        _, cargo = await _con_cargo(cli, hdr, ids)
        ajeno = await cli.post(
            f"/cuentas/{ids['beto']}/movimientos/{cargo['id']}/anular",
            json={"motivo": "x"}, headers=hdr["admin"])
        inexistente = await cli.post(
            f"/cuentas/{ids['ana']}/movimientos/987654/anular",
            json={"motivo": "x"}, headers=hdr["admin"])
    assert ajeno.status_code == 404 and inexistente.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("cuerpo", [{}, {"motivo": ""}, {"motivo": "   "}, {"motivo": "x", "monto": "1.00"}])
async def test_anular_422_motivo_obligatorio_y_sin_extras(sesion_pg, cuerpo):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        _, cargo = await _con_cargo(cli, hdr, ids)
        r = await cli.post(
            f"/cuentas/{ids['ana']}/movimientos/{cargo['id']}/anular", json=cuerpo, headers=hdr["admin"])
        cuenta = (await cli.get(f"/cuentas/{ids['ana']}", headers=hdr["admin"])).json()
    assert r.status_code == 422
    assert len(cuenta["movimientos"]) == 1  # no se creó ninguna fila


@pytest.mark.asyncio
@pytest.mark.parametrize("metodo,ruta", [
    ("GET", "/cuentas/1"), ("POST", "/cuentas/1/movimientos/1/anular"),
])
async def test_sin_bearer_401(sesion_pg, metodo, ruta):
    cli, _, _ = await _mundo(sesion_pg)
    async with cli:
        r = await cli.request(metodo, ruta, json={"motivo": "x"})
    assert r.status_code == 401
