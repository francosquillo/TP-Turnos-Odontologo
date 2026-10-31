"""C-10 grupo 7.1 a 7.3: API de caja y recibos (HTTP real + PG real) (D-12, D-16, D-17, D-25).

Códigos: 201 cobro nuevo, 200 reintento/lectura/cierre/anulación, 401 sin Bearer, 403 rol,
404 inexistente, 409 estado, 422 validación. Los ids se copian antes de la primera llamada
porque `a_http` hace rollback y expira los objetos de la sesión. Datos ficticios.
"""
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente  # noqa: E402
from c10_helpers import (  # noqa: E402
    clave_nueva, contar, crear_caja, crear_presupuesto_aceptado, sembrar_c10,
)
from db_utils import sesion_pg  # noqa: E402, F401


def _hoy():
    from app.servicios.caja_servicio import hoy_operativo

    return hoy_operativo()


async def _mundo(sesion, total="1000.00", caja_pendiente=False):
    m = await sembrar_c10(sesion)
    p, _ = await crear_presupuesto_aceptado(sesion, m, total=total)
    otro, _ = await crear_presupuesto_aceptado(sesion, m, total=total)
    if caja_pendiente:
        await crear_caja(sesion, m, _hoy() - timedelta(days=1))
    ids = {"p": p.id, "otro": otro.id, "ana": m.ana.id}
    cli, bearer, _ = await armar_cliente(sesion)
    hdr = {
        "sec": bearer(m.secretaria, "secretaria"), "admin": bearer(m.admin, "admin"),
        "odo": bearer(m.odo_a, "odontologo"),
    }
    return cli, hdr, ids


def _cobro(ids, monto="400.00", medio="efectivo", clave=None, presupuesto="p"):
    return {"presupuesto_id": ids[presupuesto], "monto": monto, "medio": medio,
            "clave_idempotencia": clave or clave_nueva()}


# --- 7.1 cobrar y cerrar -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_cobrar_201(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.post("/caja/cobrar", json=_cobro(ids), headers=hdr["sec"])
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["numero"] == 1 and cuerpo["monto"] == "400.00" and cuerpo["medio"] == "efectivo"
    assert cuerpo["fecha"] == _hoy().isoformat() and cuerpo["anulado"] is False
    assert cuerpo["paciente_nombre"] == "Ana Ficticia" and cuerpo["presupuesto_estado"] == "aceptado"
    assert "clave_idempotencia" not in cuerpo
    assert await contar(sesion_pg, "recibo") == 1


@pytest.mark.asyncio
async def test_post_cobrar_reintento_200_mismo_cuerpo(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    cuerpo = _cobro(ids)
    async with cli:
        primero = await cli.post("/caja/cobrar", json=cuerpo, headers=hdr["sec"])
        segundo = await cli.post("/caja/cobrar", json=cuerpo, headers=hdr["sec"])
    assert (primero.status_code, segundo.status_code) == (201, 200)
    assert segundo.json() == primero.json()
    assert await contar(sesion_pg, "recibo") == 1 and await contar(sesion_pg, "movimiento_caja") == 1


@pytest.mark.asyncio
async def test_post_cobrar_otro_contenido_409(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    clave = clave_nueva()
    async with cli:
        await cli.post("/caja/cobrar", json=_cobro(ids, clave=clave), headers=hdr["sec"])
        r = await cli.post("/caja/cobrar", json=_cobro(ids, monto="401.00", clave=clave), headers=hdr["sec"])
        nuevo = await cli.post("/caja/cobrar", json=_cobro(ids), headers=hdr["sec"])
    assert r.status_code == 409
    assert nuevo.json()["numero"] == 2


@pytest.mark.asyncio
async def test_post_cobrar_sin_clave_422(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    cuerpo = _cobro(ids)
    del cuerpo["clave_idempotencia"]
    async with cli:
        r = await cli.post("/caja/cobrar", json=cuerpo, headers=hdr["sec"])
    assert r.status_code == 422 and await contar(sesion_pg, "recibo") == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("medio", ["tarjeta", "mercadopago", "TARJETA_SIMULADA"])
async def test_post_cobrar_medio_invalido_422(sesion_pg, medio):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.post("/caja/cobrar", json=_cobro(ids, medio=medio), headers=hdr["sec"])
    assert r.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("extra", [{"fecha": "2026-10-31"}, {"paciente_id": 1}, {"numero": 9}])
async def test_post_cobrar_campos_reservados_422(sesion_pg, extra):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.post("/caja/cobrar", json={**_cobro(ids), **extra}, headers=hdr["sec"])
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_cobrar_error_hace_rollback(sesion_pg):
    """Un 422 de dominio llega después de abrir la caja: el rollback no deja ninguna fila."""
    cli, hdr, ids = await _mundo(sesion_pg, total="500.00")
    async with cli:
        r = await cli.post("/caja/cobrar", json=_cobro(ids, monto="500.01"), headers=hdr["sec"])
        inexistente = await cli.post(
            "/caja/cobrar", json={**_cobro(ids), "presupuesto_id": 987654}, headers=hdr["sec"])
    assert (r.status_code, inexistente.status_code) == (422, 404)
    assert await contar(sesion_pg, "caja") == 0 and await contar(sesion_pg, "recibo") == 0
    assert await contar(sesion_pg, "movimiento_caja") == 0


@pytest.mark.asyncio
async def test_post_cobrar_total_deja_el_presupuesto_cobrado(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg, total="300.00")
    async with cli:
        r = await cli.post("/caja/cobrar", json=_cobro(ids, monto="300.00"), headers=hdr["sec"])
    assert r.status_code == 201 and r.json()["presupuesto_estado"] == "cobrado"


@pytest.mark.asyncio
async def test_post_cierre_200(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        await cli.post("/caja/cobrar", json=_cobro(ids, monto="1000.00"), headers=hdr["sec"])
        estado = (await cli.get("/caja", headers=hdr["sec"])).json()
        r = await cli.post(
            "/caja/cierre", json={"caja_id": estado["caja"]["id"], "total_contado": "1000.00"},
            headers=hdr["sec"])
        otra = await cli.post(
            "/caja/cierre", json={"caja_id": estado["caja"]["id"], "total_contado": "1000.00"},
            headers=hdr["sec"])
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "cerrada" and cuerpo["diferencia"] == "0.00"
    assert cuerpo["total_sistema"] == "1000.00" and otra.status_code == 409


@pytest.mark.asyncio
async def test_post_cierre_sin_motivo_422(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        await cli.post("/caja/cobrar", json=_cobro(ids, monto="1000.00"), headers=hdr["sec"])
        caja_id = (await cli.get("/caja", headers=hdr["sec"])).json()["caja"]["id"]
        r = await cli.post("/caja/cierre", json={"caja_id": caja_id, "total_contado": "900.00"},
                           headers=hdr["sec"])
        ok = await cli.post(
            "/caja/cierre",
            json={"caja_id": caja_id, "total_contado": "900.00", "motivo_diferencia": "faltante"},
            headers=hdr["sec"])
    assert r.status_code == 422
    assert ok.status_code == 200 and ok.json()["diferencia"] == "-100.00"


@pytest.mark.asyncio
@pytest.mark.parametrize("campo", ["total_sistema", "diferencia"])
async def test_post_cierre_con_campos_calculados_422(sesion_pg, campo):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        await cli.post("/caja/cobrar", json=_cobro(ids), headers=hdr["sec"])
        caja_id = (await cli.get("/caja", headers=hdr["sec"])).json()["caja"]["id"]
        r = await cli.post(
            "/caja/cierre", json={"caja_id": caja_id, "total_contado": "400.00", campo: "0.00"},
            headers=hdr["sec"])
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_cierre_caja_inexistente_404_y_contado_negativo_422(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r404 = await cli.post("/caja/cierre", json={"caja_id": 987654, "total_contado": "0"},
                              headers=hdr["sec"])
        r422 = await cli.post("/caja/cierre", json={"caja_id": 1, "total_contado": "-1"},
                              headers=hdr["sec"])
    assert (r404.status_code, r422.status_code) == (404, 422)


# --- 7.2 GET /caja -----------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_caja_sin_movimientos_no_crea_filas(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.get("/caja", headers=hdr["sec"])
        admin = await cli.get("/caja", headers=hdr["admin"])
    cuerpo = r.json()
    assert r.status_code == 200 and admin.status_code == 200
    assert cuerpo["caja"] is None and cuerpo["operable"] is True and cuerpo["bloqueo"] is None
    assert cuerpo["fecha"] == cuerpo["hoy"] == _hoy().isoformat() and cuerpo["desglose"] == []
    assert await contar(sesion_pg, "caja") == 0


@pytest.mark.asyncio
async def test_get_caja_con_desglose(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg, total="2000.00")
    async with cli:
        await cli.post("/caja/cobrar", json=_cobro(ids, monto="300.00"), headers=hdr["sec"])
        await cli.post("/caja/cobrar", json=_cobro(ids, monto="200.00", medio="transferencia"), headers=hdr["sec"])
        await cli.post("/caja/cobrar", json=_cobro(ids, monto="100.50"), headers=hdr["sec"])
        r = await cli.get("/caja", headers=hdr["sec"])
    cuerpo = r.json()
    assert cuerpo["caja"]["estado"] == "abierta" and cuerpo["caja"]["total_sistema"] == "600.50"
    assert cuerpo["desglose"] == [
        {"medio": "efectivo", "subtotal": "400.50"}, {"medio": "transferencia", "subtotal": "200.00"}]
    assert cuerpo["operable"] is True


@pytest.mark.asyncio
async def test_get_caja_pendiente_no_operable(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg, caja_pendiente=True)
    ayer = (_hoy() - timedelta(days=1)).isoformat()
    async with cli:
        r = await cli.get("/caja", headers=hdr["sec"])
        cobro = await cli.post("/caja/cobrar", json=_cobro(ids), headers=hdr["sec"])
    cuerpo = r.json()
    assert cuerpo["operable"] is False and cuerpo["bloqueo"] == "caja_pendiente"
    assert cuerpo["caja"]["fecha"] == ayer == cuerpo["fecha"] and cuerpo["hoy"] == _hoy().isoformat()
    assert cobro.status_code == 409 and await contar(sesion_pg, "caja") == 1


@pytest.mark.asyncio
async def test_get_caja_hoy_cerrada_no_operable(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        await cli.post("/caja/cobrar", json=_cobro(ids), headers=hdr["sec"])
        caja_id = (await cli.get("/caja", headers=hdr["sec"])).json()["caja"]["id"]
        await cli.post("/caja/cierre", json={"caja_id": caja_id, "total_contado": "400.00"},
                       headers=hdr["sec"])
        r = await cli.get("/caja", headers=hdr["sec"])
        cobro = await cli.post("/caja/cobrar", json=_cobro(ids), headers=hdr["sec"])
    cuerpo = r.json()
    assert cuerpo["operable"] is False and cuerpo["bloqueo"] == "caja_cerrada"
    assert cuerpo["caja"]["estado"] == "cerrada" and cobro.status_code == 409


@pytest.mark.asyncio
async def test_get_caja_fecha_cerrada_con_totales(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        await cli.post("/caja/cobrar", json=_cobro(ids), headers=hdr["sec"])
        caja_id = (await cli.get("/caja", headers=hdr["sec"])).json()["caja"]["id"]
        await cli.post(
            "/caja/cierre",
            json={"caja_id": caja_id, "total_contado": "350.00", "motivo_diferencia": "faltante"},
            headers=hdr["sec"])
        r = await cli.get(f"/caja?fecha={_hoy().isoformat()}", headers=hdr["admin"])
    caja = r.json()["caja"]
    assert caja["total_sistema"] == "400.00" and caja["total_contado"] == "350.00"
    assert caja["diferencia"] == "-50.00" and caja["motivo_diferencia"] == "faltante"
    assert r.json()["desglose"] == [{"medio": "efectivo", "subtotal": "400.00"}]


@pytest.mark.asyncio
async def test_get_caja_fecha_sin_caja(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.get("/caja?fecha=2026-01-15", headers=hdr["sec"])
        mal = await cli.get("/caja?fecha=no-es-fecha", headers=hdr["sec"])
    assert r.status_code == 200 and r.json()["caja"] is None and r.json()["fecha"] == "2026-01-15"
    assert mal.status_code == 422
    assert await contar(sesion_pg, "caja") == 0


# --- 7.3 recibos -------------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_recibos_del_dia(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg, total="2000.00")
    async with cli:
        a = (await cli.post("/caja/cobrar", json=_cobro(ids, monto="300.00"), headers=hdr["sec"])).json()
        b = (await cli.post("/caja/cobrar", json=_cobro(ids, monto="200.00", medio="tarjeta_simulada"), headers=hdr["sec"])).json()
        await cli.post(f"/recibos/{a['id']}/anular", json={"motivo": "error"}, headers=hdr["admin"])
        r = await cli.get(f"/recibos?fecha={_hoy().isoformat()}", headers=hdr["sec"])
        vacio = await cli.get("/recibos?fecha=2026-01-15", headers=hdr["admin"])
    filas = r.json()
    assert r.status_code == 200 and [f["numero"] for f in filas] == [2, 1]
    assert filas[0]["id"] == b["id"] and filas[0]["medio"] == "tarjeta_simulada"
    assert filas[1]["anulado"] is True and filas[1]["motivo_anulacion"] == "error"
    assert all("clave_idempotencia" not in f for f in filas)
    assert vacio.status_code == 200 and vacio.json() == []


@pytest.mark.asyncio
async def test_get_recibos_sin_fecha_422(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.get("/recibos", headers=hdr["sec"])
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_anular_200(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        cobro = (await cli.post("/caja/cobrar", json=_cobro(ids), headers=hdr["sec"])).json()
        r = await cli.post(f"/recibos/{cobro['id']}/anular", json={"motivo": "cobro duplicado"}, headers=hdr["admin"])
        otra = await cli.post(f"/recibos/{cobro['id']}/anular", json={"motivo": "otra vez"}, headers=hdr["admin"])
        inexistente = await cli.post("/recibos/987654/anular", json={"motivo": "x"}, headers=hdr["admin"])
    cuerpo = r.json()
    assert r.status_code == 200 and cuerpo["anulado"] is True and cuerpo["numero"] == 1
    assert cuerpo["motivo_anulacion"] == "cobro duplicado" and cuerpo["monto"] == "400.00"
    assert (otra.status_code, inexistente.status_code) == (409, 404)


@pytest.mark.asyncio
async def test_post_anular_sin_motivo_422(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        cobro = (await cli.post("/caja/cobrar", json=_cobro(ids), headers=hdr["sec"])).json()
        vacio = await cli.post(f"/recibos/{cobro['id']}/anular", json={}, headers=hdr["admin"])
        blanco = await cli.post(f"/recibos/{cobro['id']}/anular", json={"motivo": "   "}, headers=hdr["admin"])
    assert (vacio.status_code, blanco.status_code) == (422, 422)
    assert await sesion_pg.scalar(sa.text("SELECT anulado FROM recibo")) is False
    assert await contar(sesion_pg, "movimiento_caja") == 1


@pytest.mark.asyncio
async def test_post_anular_con_caja_pendiente_409(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    p, _ = await crear_presupuesto_aceptado(sesion_pg, m)
    ids = {"p": p.id}
    cli, bearer, _ = await armar_cliente(sesion_pg)
    sec, admin = bearer(m.secretaria, "secretaria"), bearer(m.admin, "admin")
    async with cli:
        cobro = (await cli.post("/caja/cobrar", json=_cobro(ids), headers=sec)).json()
        # La caja de hoy pasa a ser "de ayer" por SQL: simula un día sin cierre.
        await sesion_pg.execute(sa.text("UPDATE caja SET fecha = fecha - 1"))
        await sesion_pg.commit()
        r = await cli.post(f"/recibos/{cobro['id']}/anular", json={"motivo": "x"}, headers=admin)
    assert r.status_code == 409
    assert await sesion_pg.scalar(sa.text("SELECT anulado FROM recibo")) is False
    assert await contar(sesion_pg, "caja") == 1
