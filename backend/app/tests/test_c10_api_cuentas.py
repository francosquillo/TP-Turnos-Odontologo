"""C-10 grupo 7.4: `pendientes` en GET /cuentas/:paciente_id (D-08, D-17) con HTTP + PG reales.

El importe pendiente es derivado de los movimientos y viaja como texto. Datos ficticios.
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente  # noqa: E402
from c10_helpers import clave_nueva, crear_presupuesto_aceptado, sembrar_c10  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401


async def _mundo(sesion):
    m = await sembrar_c10(sesion)
    p, _ = await crear_presupuesto_aceptado(sesion, m, total="1000.00")
    ids = {"p": p.id, "ana": m.ana.id, "beto": m.beto.id}
    cli, bearer, _ = await armar_cliente(sesion)
    hdr = {"sec": bearer(m.secretaria, "secretaria"), "admin": bearer(m.admin, "admin")}
    return cli, hdr, ids


async def _cobrar(cli, hdr, ids, monto):
    r = await cli.post("/caja/cobrar", json={
        "presupuesto_id": ids["p"], "monto": monto, "medio": "efectivo",
        "clave_idempotencia": clave_nueva()}, headers=hdr["sec"])
    assert r.status_code == 201, r.text
    return r.json()


async def _cuenta(cli, hdr, ids):
    r = await cli.get(f"/cuentas/{ids['ana']}", headers=hdr["sec"])
    assert r.status_code == 200
    return r.json()


@pytest.mark.asyncio
async def test_cuenta_pendiente_parcial(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        antes = await _cuenta(cli, hdr, ids)
        await _cobrar(cli, hdr, ids, "400.00")
        despues = await _cuenta(cli, hdr, ids)
    assert antes["pendientes"] == [{"presupuesto_id": ids["p"], "total": "1000.00", "pendiente": "1000.00"}]
    assert despues["pendientes"] == [{"presupuesto_id": ids["p"], "total": "1000.00", "pendiente": "600.00"}]
    assert despues["saldo"] == "600.00"
    pago = next(m for m in despues["movimientos"] if m["tipo"] == "pago")
    assert pago["concepto"] == "Recibo 1" and pago["recibo_id"] is not None


@pytest.mark.asyncio
async def test_cuenta_pendiente_repuesto_tras_anular(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        cobro = await _cobrar(cli, hdr, ids, "400.00")
        r = await cli.post(f"/recibos/{cobro['id']}/anular", json={"motivo": "error"}, headers=hdr["admin"])
        cuenta = await _cuenta(cli, hdr, ids)
    assert r.status_code == 200
    assert cuenta["pendientes"][0]["pendiente"] == "1000.00" and cuenta["saldo"] == "1000.00"


@pytest.mark.asyncio
async def test_cuenta_sin_pendiente_con_cargo_anulado(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        cuenta = await _cuenta(cli, hdr, ids)
        cargo = next(m for m in cuenta["movimientos"] if m["tipo"] == "cargo")
        r = await cli.post(
            f"/cuentas/{ids['ana']}/movimientos/{cargo['id']}/anular", json={"motivo": "error"},
            headers=hdr["admin"])
        despues = await _cuenta(cli, hdr, ids)
    assert r.status_code == 201 and despues["pendientes"] == [] and despues["saldo"] == "0.00"


@pytest.mark.asyncio
async def test_cuenta_sin_pendiente_cobrado(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        await _cobrar(cli, hdr, ids, "1000.00")
        cuenta = await _cuenta(cli, hdr, ids)
    assert cuenta["pendientes"] == [] and cuenta["saldo"] == "0.00"


@pytest.mark.asyncio
async def test_cuenta_sin_movimientos_lista_vacia(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.get(f"/cuentas/{ids['beto']}", headers=hdr["sec"])
    assert r.status_code == 200
    assert r.json() == {"paciente_id": ids["beto"], "saldo": "0.00", "movimientos": [], "pendientes": []}
