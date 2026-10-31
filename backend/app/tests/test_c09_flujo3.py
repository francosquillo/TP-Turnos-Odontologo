"""C-09 task 6.5: Flujo 3 de punta a punta (HTTP real + PG real), parte presupuesto y cuenta.

Turno `asistido` -> historia -> hallazgo -> presupuesto -> presentar -> aceptar -> saldo ->
anular -> saldo cero; y la variante con rechazo sin movimientos. Datos ficticios.
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente, crear_turno, sembrar_mundo  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401


async def _preparar(sesion):
    from app.db.seed import seed_tratamientos

    m = await sembrar_mundo(sesion)
    await crear_turno(sesion, m.ana, m.prof_a, m.sillon, estado="asistido")
    await seed_tratamientos(sesion)
    cli, bearer, _ = await armar_cliente(sesion)
    hdr = {"odo": bearer(m.odo_a, "odontologo"), "sec": bearer(m.secretaria, "secretaria"),
           "admin": bearer(m.admin, "admin")}
    return cli, hdr, m.ana.id


async def _hallazgos(cli, hdr, ana_id):
    hc = (await cli.post("/historias", json={"paciente_id": ana_id}, headers=hdr["odo"])).json()
    base = f"/odontograma/{hc['id']}/hallazgos"
    caries = (await cli.post(base, json={"pieza_fdi": 16, "cara": "oclusal", "estado": "caries"}, headers=hdr["odo"])).json()["hallazgo"]
    ausente = (await cli.post(base, json={"pieza_fdi": 36, "cara": "pieza_completa", "estado": "ausente"}, headers=hdr["odo"])).json()["hallazgo"]
    return caries, ausente


@pytest.mark.asyncio
async def test_flujo3_presupuesto_cuenta_corriente_y_anulacion(sesion_pg):
    cli, hdr, ana_id = await _preparar(sesion_pg)
    async with cli:
        caries, ausente = await _hallazgos(cli, hdr, ana_id)
        catalogo = {t["codigo"]: t for t in (await cli.get("/tratamientos", headers=hdr["odo"])).json()}
        obt, cor = catalogo["OBT-001"], catalogo["COR-001"]  # 18000.00 y 120000.00

        # el odontólogo arma el presupuesto desde los hallazgos
        r = await cli.post("/presupuestos", json={"paciente_id": ana_id, "items": [
            {"hallazgo_id": caries["id"], "tratamiento_id": obt["id"], "cantidad": 2},
            {"hallazgo_id": ausente["id"], "tratamiento_id": cor["id"]},
        ]}, headers=hdr["odo"])
        assert r.status_code == 201
        p = r.json()
        assert p["estado"] == "borrador" and p["total"] == "156000.00"
        assert [i["subtotal"] for i in p["items"]] == ["36000.00", "120000.00"]

        # la secretaria lo ve (con pieza y cara), el admin con vista financiera
        sec = (await cli.get(f"/presupuestos/{p['id']}", headers=hdr["sec"])).json()
        assert (sec["items"][0]["pieza_fdi"], sec["items"][0]["cara"]) == (16, "oclusal")
        adm = (await cli.get(f"/presupuestos/{p['id']}", headers=hdr["admin"])).json()
        assert adm["items"][0]["pieza_fdi"] is None and adm["total"] == "156000.00"

        # aún no hay deuda: el presupuesto es un borrador
        assert (await cli.get(f"/cuentas/{ana_id}", headers=hdr["sec"])).json()["saldo"] == "0.00"

        # presentar y aceptar generan el cargo
        assert (await cli.post(f"/presupuestos/{p['id']}/presentar", headers=hdr["odo"])).json()["estado"] == "presentado"
        aceptado = (await cli.post(f"/presupuestos/{p['id']}/aceptar", headers=hdr["odo"])).json()
        assert aceptado["estado"] == "aceptado" and aceptado["cargo_anulado"] is False
        cuenta = (await cli.get(f"/cuentas/{ana_id}", headers=hdr["sec"])).json()
        assert cuenta["saldo"] == "156000.00"
        cargo = cuenta["movimientos"][0]
        assert (cargo["tipo"], cargo["monto"], cargo["concepto"]) == ("cargo", "156000.00", f"Presupuesto {p['id']}")
        assert cargo["presupuesto_id"] == p["id"] and cargo["anulado"] is False

        # el admin anula el cargo: saldo cero, presupuesto aceptado con la marca derivada
        anul = await cli.post(f"/cuentas/{ana_id}/movimientos/{cargo['id']}/anular",
                              json={"motivo": "Presupuesto aceptado por error"}, headers=hdr["admin"])
        assert anul.status_code == 201 and anul.json()["monto"] == "-156000.00"
        cuenta = (await cli.get(f"/cuentas/{ana_id}", headers=hdr["admin"])).json()
        assert cuenta["saldo"] == "0.00" and len(cuenta["movimientos"]) == 2
        final = (await cli.get(f"/presupuestos/{p['id']}", headers=hdr["odo"])).json()
        assert final["estado"] == "aceptado" and final["cargo_anulado"] is True

        # los mismos hallazgos se presupuestan de nuevo y generan un cargo nuevo
        otro = (await cli.post("/presupuestos", json={"paciente_id": ana_id, "items": [
            {"hallazgo_id": caries["id"], "tratamiento_id": obt["id"]}]}, headers=hdr["odo"])).json()
        await cli.post(f"/presupuestos/{otro['id']}/presentar", headers=hdr["odo"])
        assert (await cli.post(f"/presupuestos/{otro['id']}/aceptar", headers=hdr["odo"])).status_code == 200
        assert (await cli.get(f"/cuentas/{ana_id}", headers=hdr["sec"])).json()["saldo"] == "18000.00"


@pytest.mark.asyncio
async def test_flujo3_variante_rechazo_sin_movimientos(sesion_pg):
    cli, hdr, ana_id = await _preparar(sesion_pg)
    async with cli:
        caries, _ = await _hallazgos(cli, hdr, ana_id)
        obt = {t["codigo"]: t for t in (await cli.get("/tratamientos", headers=hdr["odo"])).json()}["OBT-001"]
        p = (await cli.post("/presupuestos", json={"paciente_id": ana_id, "items": [
            {"hallazgo_id": caries["id"], "tratamiento_id": obt["id"]}]}, headers=hdr["odo"])).json()
        await cli.post(f"/presupuestos/{p['id']}/presentar", headers=hdr["odo"])
        rech = await cli.post(f"/presupuestos/{p['id']}/rechazar", json={"motivo": "Prefiere esperar"}, headers=hdr["odo"])
        assert rech.status_code == 200 and rech.json()["estado"] == "rechazado"
        cuenta = (await cli.get(f"/cuentas/{ana_id}", headers=hdr["sec"])).json()
        assert cuenta == {"paciente_id": ana_id, "saldo": "0.00", "movimientos": [], "pendientes": []}
        # el historial lo conserva para recupero (US-022)
        historial = (await cli.get(f"/presupuestos?paciente_id={ana_id}&estado=rechazado", headers=hdr["odo"])).json()
        assert [x["id"] for x in historial] == [p["id"]]
        assert historial[0]["motivo_rechazo"] == "Prefiere esperar"
        # un rechazado es final
        assert (await cli.post(f"/presupuestos/{p['id']}/aceptar", headers=hdr["odo"])).status_code == 409
        assert (await cli.get(f"/cuentas/{ana_id}", headers=hdr["sec"])).json()["movimientos"] == []
