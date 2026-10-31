"""C-10 grupo 7.6: el bloqueo por caja pendiente alcanza solo a mover caja (D-06).

Con una caja abierta de ayer, la agenda, aceptar un presupuesto y anular un cargo siguen
respondiendo como siempre. Datos ficticios; HTTP + PG reales.
"""
import sys
from datetime import timedelta
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente  # noqa: E402
from c09_helpers import sembrar_c09  # noqa: E402
from c10_helpers import clave_nueva, crear_caja, crear_presupuesto_aceptado  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401


def _ayer():
    from app.servicios.caja_servicio import hoy_operativo

    return hoy_operativo() - timedelta(days=1)


async def _mundo(sesion):
    m = await sembrar_c09(sesion)
    await crear_caja(sesion, m, _ayer())  # caja pendiente
    ids = {"ana": m.ana.id, "prof": m.prof_a.id, "sillon": m.sillon.id, "h1": m.h1.id,
           "con": m.trat["CON-001"].id}
    cli, bearer, _ = await armar_cliente(sesion)
    hdr = {"sec": bearer(m.secretaria, "secretaria"), "admin": bearer(m.admin, "admin"),
           "odo": bearer(m.odo_a, "odontologo")}
    return cli, hdr, ids, m


async def _verificar_bloqueo_activo(cli, hdr, ids):
    """Control: el bloqueo existe de verdad (un cobro sí responde 409)."""
    cobro = await cli.post("/caja/cobrar", json={
        "presupuesto_id": 987654, "monto": "1.00", "medio": "efectivo",
        "clave_idempotencia": clave_nueva()}, headers=hdr["sec"])
    estado = (await cli.get("/caja", headers=hdr["sec"])).json()
    assert estado["bloqueo"] == "caja_pendiente" and estado["operable"] is False
    return cobro


@pytest.mark.asyncio
async def test_caja_pendiente_no_bloquea_crear_turno(sesion_pg):
    cli, hdr, ids, _ = await _mundo(sesion_pg)
    cuerpo = {"paciente_id": ids["ana"], "profesional_id": ids["prof"], "sillon_id": ids["sillon"],
              "inicio": "2026-11-10T11:00:00+00:00", "fin": "2026-11-10T11:30:00+00:00"}
    async with cli:
        await _verificar_bloqueo_activo(cli, hdr, ids)
        r = await cli.post("/turnos", json=cuerpo, headers=hdr["sec"])
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_caja_pendiente_no_bloquea_aceptar_presupuesto(sesion_pg):
    cli, hdr, ids, _ = await _mundo(sesion_pg)
    item = {"hallazgo_id": ids["h1"], "tratamiento_id": ids["con"]}
    async with cli:
        p = (await cli.post("/presupuestos", json={"paciente_id": ids["ana"], "items": [item]}, headers=hdr["odo"])).json()
        await cli.post(f"/presupuestos/{p['id']}/presentar", headers=hdr["odo"])
        await _verificar_bloqueo_activo(cli, hdr, ids)
        r = await cli.post(f"/presupuestos/{p['id']}/aceptar", headers=hdr["odo"])
        cuenta = await cli.get(f"/cuentas/{ids['ana']}", headers=hdr["sec"])
    assert r.status_code == 200 and r.json()["estado"] == "aceptado"
    assert [mv["tipo"] for mv in cuenta.json()["movimientos"]] == ["cargo"]


@pytest.mark.asyncio
async def test_caja_pendiente_no_bloquea_anular_cargo(sesion_pg):
    cli, hdr, ids, m = await _mundo(sesion_pg)
    await crear_presupuesto_aceptado(sesion_pg, m, total="1000.00")
    await sesion_pg.commit()
    async with cli:
        cuenta = (await cli.get(f"/cuentas/{ids['ana']}", headers=hdr["sec"])).json()
        cargo = next(mv for mv in cuenta["movimientos"] if mv["tipo"] == "cargo")
        cobro = await _verificar_bloqueo_activo(cli, hdr, ids)
        r = await cli.post(
            f"/cuentas/{ids['ana']}/movimientos/{cargo['id']}/anular", json={"motivo": "error"},
            headers=hdr["admin"])
    assert cobro.status_code == 409
    assert r.status_code == 201 and r.json()["tipo"] == "ajuste"
