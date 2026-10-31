"""C-09 grupo 6: API de presupuestos y cuentas (HTTP real + PG real) (D-03, D-09, D-15, D-19).

Códigos: 201 alta, 200 lectura/transición, 401 sin Bearer, 403 rol/vínculo/autoría,
404 inexistente o baja, 405 sin DELETE/PUT/PATCH, 409 estado inválido, 422 validación.
Datos ficticios.
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
    ids = {"ana": m.ana.id, "h1": m.h1.id, "h2": m.h2.id, "h3": m.h3.id,
           "con": m.trat["CON-001"].id, "pro": m.trat["PRO-001"].id,
           "obt": m.trat["OBT-001"].id, "gratis": m.trat["GRATIS"].id}
    cli, bearer, _ = await armar_cliente(sesion)
    hdr = {
        "odo": bearer(m.odo_a, "odontologo"), "otro": bearer(m.odo_b, "odontologo"),
        "sec": bearer(m.secretaria, "secretaria"), "admin": bearer(m.admin, "admin"),
    }
    return cli, hdr, ids


def _alta(ids, items=None):
    items = items if items is not None else [
        {"hallazgo_id": ids["h1"], "tratamiento_id": ids["con"], "cantidad": 2}]
    return {"paciente_id": ids["ana"], "items": items}


async def _crear(cli, hdr, ids, items=None):
    r = await cli.post("/presupuestos", json=_alta(ids, items), headers=hdr["odo"])
    assert r.status_code == 201, r.text
    return r.json()


async def _presentado(cli, hdr, ids, items=None):
    p = await _crear(cli, hdr, ids, items)
    r = await cli.post(f"/presupuestos/{p['id']}/presentar", headers=hdr["odo"])
    assert r.status_code == 200, r.text
    return r.json()


# --- alta ------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_alta_201(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.post("/presupuestos", json=_alta(ids), headers=hdr["odo"])
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["estado"] == "borrador" and cuerpo["total"] == "2001.00"
    assert cuerpo["items"][0]["precio"] == "1000.50" and cuerpo["items"][0]["subtotal"] == "2001.00"
    assert cuerpo["items"][0]["pieza_fdi"] == 16 and cuerpo["items"][0]["tratamiento_nombre"] == "Trat CON-001"
    assert cuerpo["es_propio"] is True and cuerpo["cargo_anulado"] is False


@pytest.mark.asyncio
async def test_alta_item_sin_hallazgo_422(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.post("/presupuestos", json=_alta(ids, [{"tratamiento_id": ids["con"]}]), headers=hdr["odo"])
        vacio = await cli.post("/presupuestos", json=_alta(ids, []), headers=hdr["odo"])
        lista = await cli.get(f"/presupuestos?paciente_id={ids['ana']}", headers=hdr["odo"])
    assert r.status_code == 422 and vacio.status_code == 422
    assert lista.json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("campo,valor", [
    ("profesional_id", 1), ("estado", "aceptado"), ("estado", "cobrado"), ("total", "1.00"),
])
async def test_alta_campos_reservados_422(sesion_pg, campo, valor):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.post("/presupuestos", json={**_alta(ids), campo: valor}, headers=hdr["odo"])
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_alta_item_con_precio_422(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    item = {"hallazgo_id": ids["h1"], "tratamiento_id": ids["con"], "precio": "1.00"}
    async with cli:
        r = await cli.post("/presupuestos", json=_alta(ids, [item]), headers=hdr["odo"])
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_alta_paciente_inexistente_404_y_hallazgo_ajeno_422(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r404 = await cli.post("/presupuestos", json={**_alta(ids), "paciente_id": 987654}, headers=hdr["odo"])
        item = {"hallazgo_id": 987654, "tratamiento_id": ids["con"]}
        r422 = await cli.post("/presupuestos", json=_alta(ids, [item]), headers=hdr["odo"])
    assert (r404.status_code, r422.status_code) == (404, 422)


# --- lectura ---------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_listado_sin_paciente_422(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.get("/presupuestos", headers=hdr["odo"])
        mal = await cli.get(f"/presupuestos?paciente_id={ids['ana']}&estado=anulado", headers=hdr["odo"])
    assert r.status_code == 422 and mal.status_code == 422


@pytest.mark.asyncio
async def test_listado_filtra_por_estado(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        borrador = await _crear(cli, hdr, ids)
        presentado = await _presentado(cli, hdr, ids, [{"hallazgo_id": ids["h2"], "tratamiento_id": ids["pro"]}])
        todos = (await cli.get(f"/presupuestos?paciente_id={ids['ana']}", headers=hdr["sec"])).json()
        solo = (await cli.get(f"/presupuestos?paciente_id={ids['ana']}&estado=presentado", headers=hdr["sec"])).json()
    assert [p["id"] for p in todos] == [presentado["id"], borrador["id"]]
    assert [p["id"] for p in solo] == [presentado["id"]]


@pytest.mark.asyncio
async def test_detalle_200_y_404(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        p = await _crear(cli, hdr, ids)
        ok = await cli.get(f"/presupuestos/{p['id']}", headers=hdr["sec"])
        no = await cli.get("/presupuestos/987654", headers=hdr["sec"])
    assert ok.status_code == 200 and ok.json()["id"] == p["id"]
    assert ok.json()["es_propio"] is False
    assert no.status_code == 404


# --- PUT --------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_put_200_y_409(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    nuevos = {"items": [{"hallazgo_id": ids["h2"], "tratamiento_id": ids["pro"], "cantidad": 3}]}
    async with cli:
        p = await _crear(cli, hdr, ids)
        ok = await cli.put(f"/presupuestos/{p['id']}", json=nuevos, headers=hdr["odo"])
        await cli.post(f"/presupuestos/{p['id']}/presentar", headers=hdr["odo"])
        conflicto = await cli.put(f"/presupuestos/{p['id']}", json=nuevos, headers=hdr["odo"])
        reservado = await cli.put(f"/presupuestos/{p['id']}", json={**nuevos, "estado": "cobrado"}, headers=hdr["odo"])
    assert ok.status_code == 200 and ok.json()["total"] == "1500.00"
    assert conflicto.status_code == 409 and reservado.status_code == 422


# --- transiciones -------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_presentar_200_409_y_422_total_cero(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    gratis = [{"hallazgo_id": ids["h1"], "tratamiento_id": ids["gratis"]}]
    async with cli:
        p = await _crear(cli, hdr, ids)
        ok = await cli.post(f"/presupuestos/{p['id']}/presentar", headers=hdr["odo"])
        otra = await cli.post(f"/presupuestos/{p['id']}/presentar", headers=hdr["odo"])
        cero = await _crear(cli, hdr, ids, gratis)
        r422 = await cli.post(f"/presupuestos/{cero['id']}/presentar", headers=hdr["odo"])
    assert ok.status_code == 200 and ok.json()["estado"] == "presentado" and ok.json()["presentado_at"]
    assert otra.status_code == 409 and r422.status_code == 422


@pytest.mark.asyncio
async def test_aceptar_200_409_y_cargo_en_la_cuenta(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        p = await _presentado(cli, hdr, ids)
        ok = await cli.post(f"/presupuestos/{p['id']}/aceptar", headers=hdr["odo"])
        otra = await cli.post(f"/presupuestos/{p['id']}/aceptar", headers=hdr["odo"])
        borrador = await _crear(cli, hdr, ids, [{"hallazgo_id": ids["h2"], "tratamiento_id": ids["pro"]}])
        r409 = await cli.post(f"/presupuestos/{borrador['id']}/aceptar", headers=hdr["odo"])
        cuenta = await cli.get(f"/cuentas/{ids['ana']}", headers=hdr["sec"])
    assert ok.status_code == 200 and ok.json()["estado"] == "aceptado"
    assert otra.status_code == 409 and r409.status_code == 409
    assert cuenta.json()["saldo"] == "2001.00" and len(cuenta.json()["movimientos"]) == 1
    assert cuenta.json()["movimientos"][0]["concepto"] == f"Presupuesto {p['id']}"


@pytest.mark.asyncio
async def test_rechazar_200_422_409(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        p = await _presentado(cli, hdr, ids)
        sin_motivo = await cli.post(f"/presupuestos/{p['id']}/rechazar", json={}, headers=hdr["odo"])
        vacio = await cli.post(f"/presupuestos/{p['id']}/rechazar", json={"motivo": "  "}, headers=hdr["odo"])
        ok = await cli.post(f"/presupuestos/{p['id']}/rechazar", json={"motivo": "Muy caro"}, headers=hdr["odo"])
        otra = await cli.post(f"/presupuestos/{p['id']}/rechazar", json={"motivo": "Otra"}, headers=hdr["odo"])
        historial = await cli.get(f"/presupuestos?paciente_id={ids['ana']}&estado=rechazado", headers=hdr["odo"])
    assert sin_motivo.status_code == 422 and vacio.status_code == 422
    assert ok.status_code == 200 and ok.json()["motivo_rechazo"] == "Muy caro"
    assert otra.status_code == 409
    assert [x["id"] for x in historial.json()] == [p["id"]]


@pytest.mark.asyncio
async def test_baja_200_409_404(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        borrador = await _crear(cli, hdr, ids)
        sin_motivo = await cli.post(f"/presupuestos/{borrador['id']}/baja", json={}, headers=hdr["odo"])
        ok = await cli.post(f"/presupuestos/{borrador['id']}/baja", json={"motivo_baja": "Duplicado"}, headers=hdr["odo"])
        despues = await cli.get(f"/presupuestos/{borrador['id']}", headers=hdr["odo"])
        presentado = await _presentado(cli, hdr, ids, [{"hallazgo_id": ids["h2"], "tratamiento_id": ids["pro"]}])
        r409 = await cli.post(f"/presupuestos/{presentado['id']}/baja", json={"motivo_baja": "x"}, headers=hdr["odo"])
    assert sin_motivo.status_code == 422
    assert ok.status_code == 200 and despues.status_code == 404
    assert r409.status_code == 409


@pytest.mark.asyncio
async def test_delete_405(sesion_pg):
    cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        p = await _crear(cli, hdr, ids)
        r = await cli.delete(f"/presupuestos/{p['id']}", headers=hdr["odo"])
        patch = await cli.patch(f"/presupuestos/{p['id']}", json={}, headers=hdr["odo"])
    assert r.status_code == 405 and patch.status_code == 405


@pytest.mark.asyncio
@pytest.mark.parametrize("metodo,ruta", [
    ("POST", "/presupuestos"), ("GET", "/presupuestos?paciente_id=1"), ("GET", "/presupuestos/1"),
    ("PUT", "/presupuestos/1"), ("POST", "/presupuestos/1/presentar"),
    ("POST", "/presupuestos/1/aceptar"), ("POST", "/presupuestos/1/rechazar"),
    ("POST", "/presupuestos/1/baja"),
])
async def test_sin_bearer_401(sesion_pg, metodo, ruta):
    cli, _, _ = await _mundo(sesion_pg)
    async with cli:
        r = await cli.request(metodo, ruta, json={})
    assert r.status_code == 401
