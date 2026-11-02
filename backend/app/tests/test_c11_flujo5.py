"""C-11 task 7.1: Flujo 5 de punta a punta por HTTP, con saldos y totales exactos (US-040, US-041).

Plan del paciente -> presupuesto aceptado con cobertura -> cobro a cargo del paciente ->
liquidación (generar, presentar, exportar) -> cobro de la OS -> cierre de caja. Postgres real.
Datos ficticios.
"""
import csv
import io
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente  # noqa: E402
from c10_helpers import clave_nueva  # noqa: E402
from c11_helpers import sembrar_c11  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401


@pytest.mark.asyncio
async def test_flujo5_plan_cobertura_liquidacion_cobro_y_cierre(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    ids = {"ana": m.ana.id, "os": m.os.id, "base": m.plan_base.id, "h1": m.h1.id, "h2": m.h2.id,
           "obt": m.trat["OBT-001"].id, "pro": m.trat["PRO-001"].id}
    cli, bearer, _ = await armar_cliente(sesion_pg)
    admin, sec, odo = (bearer(m.admin, "admin"), bearer(m.secretaria, "secretaria"),
                       bearer(m.odo_a, "odontologo"))
    async with cli:
        # 1. La secretaria asigna el plan y consulta el validador antes del cobro.
        r = await cli.put(f"/pacientes/{ids['ana']}/plan", json={"plan_id": ids["base"]}, headers=sec)
        assert r.status_code == 200
        r = await cli.get(f"/validador-cobertura?paciente_id={ids['ana']}"
                          f"&tratamiento_id={ids['obt']}", headers=sec)
        assert (r.json()["cubierto"], r.json()["a_cargo"]) == ("10500.00", "4500.00")

        # 2. El odontólogo presupuesta dos prestaciones y el paciente acepta.
        r = await cli.post("/presupuestos", json={"paciente_id": ids["ana"], "items": [
            {"hallazgo_id": ids["h1"], "tratamiento_id": ids["obt"], "cantidad": 1},
            {"hallazgo_id": ids["h2"], "tratamiento_id": ids["pro"], "cantidad": 1}]}, headers=odo)
        assert r.status_code == 201, r.text
        pid = r.json()["id"]
        assert (await cli.post(f"/presupuestos/{pid}/presentar", headers=odo)).status_code == 200
        r = await cli.post(f"/presupuestos/{pid}/aceptar", headers=odo)
        assert r.status_code == 200 and r.json()["estado"] == "aceptado"

        # 3. Cuenta: cargo 15500.00 (15000.00 + 500.00 sin arancel); la cobertura de 10500.00
        #    deja 5000.00 a cargo del paciente.
        cuenta = (await cli.get(f"/cuentas/{ids['ana']}", headers=sec)).json()
        assert cuenta["saldo"] == "5000.00"
        assert cuenta["pendientes"] == [
            {"presupuesto_id": pid, "total": "15500.00", "pendiente": "5000.00"}]

        # 4. La secretaria cobra todo lo que queda a cargo del paciente; no se puede cobrar de más.
        r = await cli.post("/caja/cobrar", json={
            "presupuesto_id": pid, "monto": "5000.01", "medio": "efectivo",
            "clave_idempotencia": clave_nueva()}, headers=sec)
        assert r.status_code == 422
        r = await cli.post("/caja/cobrar", json={
            "presupuesto_id": pid, "monto": "5000.00", "medio": "efectivo",
            "clave_idempotencia": clave_nueva()}, headers=sec)
        assert r.status_code == 201 and r.json()["presupuesto_estado"] == "cobrado"
        assert (await cli.get(f"/cuentas/{ids['ana']}", headers=sec)).json()["saldo"] == "0.00"

        # 5. El admin genera la liquidación de octubre de la OS, la revisa y la presenta.
        r = await cli.post("/liquidaciones", json={"os_id": ids["os"], "periodo": _periodo_hoy()},
                           headers=admin)
        assert r.status_code == 201, r.text
        liq = r.json()
        assert liq["total"] == "10500.00" and liq["cantidad_items"] == 2
        assert liq["cantidad_revision"] == 1
        lid = liq["id"]
        r = await cli.post(f"/liquidaciones/{lid}/presentar", headers=admin)
        assert r.status_code == 200 and r.json()["estado"] == "presentada"

        # 6. Exporta el informe: el total del CSV es el de la liquidación.
        r = await cli.get(f"/liquidaciones/{lid}/export.csv", headers=admin)
        filas = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
        assert Decimal(next(f for f in filas if f and f[0] == "TOTAL")[6]) == Decimal("10500.00")
        assert (await cli.get(f"/liquidaciones/{lid}/export.pdf", headers=admin)
                ).content.startswith(b"%PDF")

        # 7. La OS paga: ingreso en la caja de hoy, junto al cobro en efectivo del paciente.
        r = await cli.post(f"/liquidaciones/{lid}/cobrar", json={"medio": "transferencia"},
                           headers=admin)
        assert r.status_code == 200 and r.json()["estado"] == "cobrada"
        estado = (await cli.get("/caja", headers=sec)).json()
        assert estado["caja"]["total_sistema"] == "15500.00"
        assert {d["medio"]: d["subtotal"] for d in estado["desglose"]} == {
            "efectivo": "5000.00", "transferencia": "10500.00"}
        assert [i["monto"] for i in estado["ingresos_liquidacion"]] == ["10500.00"]

        # 8. La secretaria cierra la caja sin diferencia.
        r = await cli.post("/caja/cierre", json={
            "caja_id": estado["caja"]["id"], "total_contado": "15500.00"}, headers=sec)
        assert r.status_code == 200 and r.json()["diferencia"] == "0.00"
        # Y el admin sigue sin poder cobrar ni cerrar por /caja.
        assert (await cli.post("/caja/cierre", json={"caja_id": 1, "total_contado": "0.00"},
                               headers=admin)).status_code == 403

    # Un solo ingreso de liquidación y un solo recibo en toda la base.
    assert await sesion_pg.scalar(sa.text(
        "SELECT count(*) FROM movimiento_caja WHERE liquidacion_id IS NOT NULL")) == 1
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM recibo")) == 1


def _periodo_hoy() -> str:
    """El presupuesto se aceptó hoy (reloj real del servidor): el período es el mes de hoy."""
    from app.servicios.caja_servicio import hoy_operativo

    return hoy_operativo().strftime("%Y-%m")
