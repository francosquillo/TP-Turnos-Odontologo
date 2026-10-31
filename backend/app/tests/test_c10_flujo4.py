"""C-10 grupo 7.8: Flujo 4 de punta a punta (HTTP + PG reales) (US-031, RN-CO-01..04).

Día 1: aceptar, cobrar parcial y saldo (cobrado), cierre con diferencia. Día 2: un cobro
deja la caja abierta. Día 3: la caja pendiente bloquea cobrar y anular; se cierra y la
anulación del recibo del día 1 cae en la caja del día 3 sin tocar la del día 1.
`freezegun` mueve el reloj; los tokens se emiten dentro de cada día. Datos ficticios.
"""
import sys
from pathlib import Path

import pytest
from freezegun import freeze_time

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente  # noqa: E402
from c09_helpers import sembrar_c09  # noqa: E402
from c10_helpers import clave_nueva, contar  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

DIA1 = "2026-11-02 15:00:00"   # 12:00 en Buenos Aires
DIA2 = "2026-11-03 15:00:00"
DIA3 = "2026-11-04 15:00:00"


def _dia(instante):
    return freeze_time(instante, tz_offset=0, real_asyncio=True)


def _cobro(presupuesto_id, monto, medio="efectivo"):
    return {"presupuesto_id": presupuesto_id, "monto": monto, "medio": medio,
            "clave_idempotencia": clave_nueva()}


@pytest.mark.asyncio
async def test_flujo4_cobro_cierre_bloqueo_y_anulacion(sesion_pg):
    from app.core.security import crear_access_token

    m = await sembrar_c09(sesion_pg)
    ids = {"ana": m.ana.id, "h1": m.h1.id, "h2": m.h2.id, "con": m.trat["CON-001"].id,
           "pro": m.trat["PRO-001"].id}
    usuarios = {"odo": (m.odo_a.id, "odontologo"), "sec": (m.secretaria.id, "secretaria"),
                "admin": (m.admin.id, "admin")}
    cli, _, _ = await armar_cliente(sesion_pg)

    def hdr(rol):  # el token se emite en el día congelado vigente
        uid, nombre = usuarios[rol]
        return {"Authorization": f"Bearer {crear_access_token(uid, nombre)}"}

    async with cli:
        # --- Día 1: aceptar dos presupuestos, cobrar parcial y saldo, cerrar con diferencia ---
        with _dia(DIA1):
            p1 = (await cli.post("/presupuestos", json={"paciente_id": ids["ana"], "items": [
                {"hallazgo_id": ids["h1"], "tratamiento_id": ids["con"], "cantidad": 2}]},
                headers=hdr("odo"))).json()
            p2 = (await cli.post("/presupuestos", json={"paciente_id": ids["ana"], "items": [
                {"hallazgo_id": ids["h2"], "tratamiento_id": ids["pro"]}]}, headers=hdr("odo"))).json()
            for p in (p1, p2):
                await cli.post(f"/presupuestos/{p['id']}/presentar", headers=hdr("odo"))
                aceptado = await cli.post(f"/presupuestos/{p['id']}/aceptar", headers=hdr("odo"))
                assert aceptado.status_code == 200
            assert (p1["total"], p2["total"]) == ("2001.00", "500.00")

            r1 = await cli.post("/caja/cobrar", json=_cobro(p1["id"], "1000.00"), headers=hdr("sec"))
            parcial = (await cli.get(f"/cuentas/{ids['ana']}", headers=hdr("sec"))).json()
            r2 = await cli.post("/caja/cobrar", json=_cobro(p1["id"], "1001.00", "transferencia"), headers=hdr("sec"))
            assert (r1.status_code, r2.status_code) == (201, 201)
            assert (r1.json()["numero"], r2.json()["numero"]) == (1, 2)
            assert r1.json()["presupuesto_estado"] == "aceptado" and r2.json()["presupuesto_estado"] == "cobrado"
            assert {x["presupuesto_id"]: x["pendiente"] for x in parcial["pendientes"]} == {
                p1["id"]: "1001.00", p2["id"]: "500.00"}
            sobrepago = await cli.post("/caja/cobrar", json=_cobro(p2["id"], "500.01"), headers=hdr("sec"))
            assert sobrepago.status_code == 422

            estado1 = (await cli.get("/caja", headers=hdr("admin"))).json()
            assert estado1["fecha"] == "2026-11-02" and estado1["caja"]["total_sistema"] == "2001.00"
            assert estado1["desglose"] == [
                {"medio": "efectivo", "subtotal": "1000.00"}, {"medio": "transferencia", "subtotal": "1001.00"}]
            caja1_id = estado1["caja"]["id"]
            sin_motivo = await cli.post(
                "/caja/cierre", json={"caja_id": caja1_id, "total_contado": "2000.00"}, headers=hdr("sec"))
            cierre1 = await cli.post("/caja/cierre", json={
                "caja_id": caja1_id, "total_contado": "2000.00", "motivo_diferencia": "faltante"},
                headers=hdr("sec"))
            assert sin_motivo.status_code == 422 and cierre1.status_code == 200
            assert cierre1.json()["diferencia"] == "-1.00"
            cobro_tarde = await cli.post("/caja/cobrar", json=_cobro(p2["id"], "100.00"), headers=hdr("sec"))
            assert cobro_tarde.status_code == 409  # la caja de hoy ya está cerrada

        # --- Día 2: otro cobro abre una caja nueva que NO se cierra ---
        with _dia(DIA2):
            r3 = await cli.post("/caja/cobrar", json=_cobro(p2["id"], "100.00"), headers=hdr("sec"))
            assert r3.status_code == 201 and r3.json()["numero"] == 3 and r3.json()["fecha"] == "2026-11-03"

        # --- Día 3: la caja del día 2 sigue abierta y bloquea cobrar y anular ---
        with _dia(DIA3):
            estado3 = (await cli.get("/caja", headers=hdr("sec"))).json()
            assert estado3["bloqueo"] == "caja_pendiente" and estado3["operable"] is False
            assert estado3["fecha"] == "2026-11-03" and estado3["hoy"] == "2026-11-04"
            caja2_id = estado3["caja"]["id"]
            bloqueado = await cli.post("/caja/cobrar", json=_cobro(p2["id"], "50.00"), headers=hdr("sec"))
            anula_bloqueada = await cli.post(
                f"/recibos/{r1.json()['id']}/anular", json={"motivo": "cobro erróneo"}, headers=hdr("admin"))
            assert (bloqueado.status_code, anula_bloqueada.status_code) == (409, 409)
            assert await contar(sesion_pg, "recibo") == 3 and await contar(sesion_pg, "caja") == 2

            cierre2 = await cli.post(
                "/caja/cierre", json={"caja_id": caja2_id, "total_contado": "100.00"}, headers=hdr("sec"))
            assert cierre2.status_code == 200 and cierre2.json()["fecha"] == "2026-11-03"
            assert (await cli.get("/caja", headers=hdr("sec"))).json()["operable"] is True

            # La anulación del recibo del día 1 cae en la caja de HOY (día 3).
            anulada = await cli.post(
                f"/recibos/{r1.json()['id']}/anular", json={"motivo": "cobro erróneo"}, headers=hdr("admin"))
            assert anulada.status_code == 200 and anulada.json()["anulado"] is True
            assert anulada.json()["fecha"] == "2026-11-02" and anulada.json()["numero"] == 1

            caja1 = (await cli.get("/caja?fecha=2026-11-02", headers=hdr("admin"))).json()
            caja3 = (await cli.get("/caja?fecha=2026-11-04", headers=hdr("admin"))).json()
            assert caja1["caja"]["total_sistema"] == "2001.00" and caja1["caja"]["diferencia"] == "-1.00"
            assert caja1["caja"]["estado"] == "cerrada"
            assert caja3["caja"]["estado"] == "abierta" and caja3["caja"]["total_sistema"] == "-1000.00"
            assert caja3["caja"]["abierta_por"] == usuarios["admin"][0]
            assert caja3["desglose"] == [{"medio": "efectivo", "subtotal": "-1000.00"}]

            recibos_dia1 = (await cli.get("/recibos?fecha=2026-11-02", headers=hdr("sec"))).json()
            assert [(r["numero"], r["anulado"]) for r in recibos_dia1] == [(2, False), (1, True)]
            presupuestos = {p["id"]: p["estado"] for p in (await cli.get(
                f"/presupuestos?paciente_id={ids['ana']}", headers=hdr("sec"))).json()}
            assert presupuestos[p1["id"]] == "aceptado"  # volvió de cobrado por la anulación
            cuenta = (await cli.get(f"/cuentas/{ids['ana']}", headers=hdr("sec"))).json()
            assert {x["presupuesto_id"]: x["pendiente"] for x in cuenta["pendientes"]} == {
                p1["id"]: "1000.00", p2["id"]: "400.00"}
            assert cuenta["saldo"] == "1400.00"

            siguiente = await cli.post("/caja/cobrar", json=_cobro(p1["id"], "1000.00"), headers=hdr("sec"))
            assert siguiente.status_code == 201 and siguiente.json()["numero"] == 4
            assert siguiente.json()["presupuesto_estado"] == "cobrado"
