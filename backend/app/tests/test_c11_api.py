"""C-11 grupos 2, 4.7 y 5: API de catálogo, plan del paciente, validador, liquidaciones y export.

HTTP real sobre Postgres real (`armar_cliente`). Códigos: 200/201/204 éxito, 401 sin Bearer,
403 rol, 404 inexistente, 409 estado o duplicado, 422 validación. Los ids se copian antes de
la primera llamada porque `a_http` hace rollback y expira los objetos. Datos ficticios.
"""
import csv
import io
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente  # noqa: E402
from c11_helpers import aceptar_presupuesto, sembrar_c11  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401


async def _mundo(sesion):
    m = await sembrar_c11(sesion)
    ids = {
        "os": m.os.id, "base": m.plan_base.id, "plus": m.plan_plus.id, "ana": m.ana.id,
        "beto": m.beto.id, "obt": m.trat["OBT-001"].id, "con": m.trat["CON-001"].id,
        "pro": m.trat["PRO-001"].id, "ar_obt": m.ar_obt.id, "admin": m.admin.id,
    }
    cli, bearer, _ = await armar_cliente(sesion)
    hdr = {
        "admin": bearer(m.admin, "admin"), "sec": bearer(m.secretaria, "secretaria"),
        "odo": bearer(m.odo_a, "odontologo"), "odo_b": bearer(m.odo_b, "odontologo"),
    }
    return m, cli, hdr, ids


# --- 2.3 obras sociales y planes ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_crea_obra_social_y_plan_y_aparecen_en_los_listados(sesion_pg):
    _, cli, hdr, _ = await _mundo(sesion_pg)
    async with cli:
        r = await cli.post("/obras-sociales", json={"nombre": "OS Nueva"}, headers=hdr["admin"])
        assert r.status_code == 201 and r.json()["activa"] is True
        os_id = r.json()["id"]
        r = await cli.post("/planes", json={"obra_social_id": os_id, "nombre": "Plan Uno"},
                           headers=hdr["admin"])
        assert r.status_code == 201 and r.json()["obra_social_nombre"] == "OS Nueva"
        nombres = [o["nombre"] for o in (await cli.get("/obras-sociales", headers=hdr["sec"])).json()]
        planes = (await cli.get(f"/planes?obra_social_id={os_id}", headers=hdr["odo"])).json()
    assert "OS Nueva" in nombres and [p["nombre"] for p in planes] == ["Plan Uno"]


@pytest.mark.asyncio
async def test_nombre_de_plan_repetido_en_la_misma_os_409_y_en_otra_ok(sesion_pg):
    _, cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.post("/planes", json={"obra_social_id": ids["os"], "nombre": "Plan Base"},
                           headers=hdr["admin"])
        assert r.status_code == 409
        otra = (await cli.post("/obras-sociales", json={"nombre": "Otra"}, headers=hdr["admin"])).json()
        r = await cli.post("/planes", json={"obra_social_id": otra["id"], "nombre": "Plan Base"},
                           headers=hdr["admin"])
        assert r.status_code == 201
        r = await cli.post("/obras-sociales", json={"nombre": "OS Ficticia Demo"},
                           headers=hdr["admin"])
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_baja_logica_de_plan_persiste_la_fila(sesion_pg):
    _, cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.patch(f"/planes/{ids['base']}", json={"activo": False}, headers=hdr["admin"])
        assert r.status_code == 200 and r.json()["activo"] is False
        lista = (await cli.get("/planes", headers=hdr["admin"])).json()
    assert ids["base"] in [p["id"] for p in lista]


@pytest.mark.asyncio
async def test_campo_extra_422_y_escritura_sin_permiso_403_sin_cambios(sesion_pg):
    _, cli, hdr, _ = await _mundo(sesion_pg)
    antes = await sesion_pg.scalar(sa.text("SELECT count(*) FROM obra_social"))
    async with cli:
        r = await cli.post("/obras-sociales", json={"nombre": "X", "otro": 1}, headers=hdr["admin"])
        assert r.status_code == 422
        for rol in ("sec", "odo"):
            r = await cli.post("/obras-sociales", json={"nombre": "Y"}, headers=hdr[rol])
            assert r.status_code == 403
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM obra_social")) == antes


# --- 2.4 aranceles ---------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nueva_version_de_arancel_cerrar_y_crear_con_autor_y_fecha(sesion_pg):
    _, cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.patch(f"/aranceles/{ids['ar_obt']}", json={"vigencia_hasta": "2026-09-30"},
                            headers=hdr["admin"])
        assert r.status_code == 200
        cerrado = r.json()
        assert cerrado["cerrado_por"] == ids["admin"] and cerrado["cerrado_at"] is not None
        r = await cli.post("/aranceles", json={
            "plan_id": ids["base"], "codigo_nomenclador": "N-003", "descripcion": "Obturación",
            "precio": "11000.00", "vigencia_desde": "2026-10-01"}, headers=hdr["admin"])
        assert r.status_code == 201 and r.json()["creado_por"] == ids["admin"]
        lista = (await cli.get(f"/aranceles?plan_id={ids['base']}&codigo=N-003",
                               headers=hdr["sec"])).json()
    assert [a["precio"] for a in lista] == ["10500.00", "11000.00"]


@pytest.mark.asyncio
async def test_arancel_superpuesto_409_y_precio_inmutable_422(sesion_pg):
    _, cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.post("/aranceles", json={
            "plan_id": ids["base"], "codigo_nomenclador": "N-003", "descripcion": "x",
            "precio": "1.00", "vigencia_desde": "2026-06-01"}, headers=hdr["admin"])
        assert r.status_code == 409
        r = await cli.patch(f"/aranceles/{ids['ar_obt']}", json={"precio": "999.00"},
                            headers=hdr["admin"])
        assert r.status_code == 422
        r = await cli.patch(f"/aranceles/{ids['ar_obt']}",
                            json={"vigencia_hasta": "2025-12-31"}, headers=hdr["admin"])
        assert r.status_code == 422
        r = await cli.request("DELETE", f"/aranceles/{ids['ar_obt']}", headers=hdr["admin"])
        assert r.status_code == 405


# --- 2.5 plan del paciente ----------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_asignar_y_quitar_plan(sesion_pg):
    _, cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        r = await cli.put(f"/pacientes/{ids['ana']}/plan", json={"plan_id": ids["base"]},
                          headers=hdr["sec"])
        assert r.status_code == 200
        assert r.json()["plan_nombre"] == "Plan Base" and r.json()["obra_social_nombre"] == "OS Ficticia Demo"
        r = await cli.put(f"/pacientes/{ids['ana']}/plan", json={"plan_id": None}, headers=hdr["sec"])
        assert r.status_code == 200 and r.json()["plan_id"] is None
        stub = await cli.get("/pacientes")
    assert stub.status_code == 200 and stub.json()["status"] == "stub C-01"


@pytest.mark.asyncio
async def test_plan_inexistente_o_inactivo_409_paciente_inexistente_404_odontologo_403(sesion_pg):
    m, cli, hdr, ids = await _mundo(sesion_pg)
    m.plan_plus.activo = False
    await sesion_pg.commit()
    async with cli:
        r = await cli.put(f"/pacientes/{ids['ana']}/plan", json={"plan_id": ids["plus"]},
                          headers=hdr["sec"])
        assert r.status_code == 409
        r = await cli.put(f"/pacientes/{ids['ana']}/plan", json={"plan_id": 999999},
                          headers=hdr["sec"])
        assert r.status_code == 409
        r = await cli.put("/pacientes/999999/plan", json={"plan_id": None}, headers=hdr["sec"])
        assert r.status_code == 404
        r = await cli.put(f"/pacientes/{ids['ana']}/plan", json={"plan_id": None},
                          headers=hdr["odo"])
        assert r.status_code == 403
    assert await sesion_pg.scalar(sa.text(
        "SELECT plan_id FROM paciente WHERE id = :i"), {"i": ids["ana"]}) is None


# --- 2.6 validador ---------------------------------------------------------------------------------------------

async def _validar(cli, hdr, ana, trat, rol="sec"):
    return await cli.get(f"/validador-cobertura?paciente_id={ana}&tratamiento_id={trat}",
                         headers=hdr[rol])


@pytest.mark.asyncio
async def test_validador_cubierto_parcial_y_arancel_mayor_al_precio(sesion_pg):
    m, cli, hdr, ids = await _mundo(sesion_pg)
    m.ana.plan_id = ids["base"]
    await sesion_pg.commit()
    async with cli:
        parcial = (await _validar(cli, hdr, ids["ana"], ids["obt"])).json()
        mayor = (await _validar(cli, hdr, ids["ana"], ids["con"])).json()
    assert (parcial["estado"], parcial["cubierto"], parcial["a_cargo"], parcial["porcentaje"]) == (
        "cubierto", "10500.00", "4500.00", "70.00")
    assert (mayor["cubierto"], mayor["a_cargo"], mayor["porcentaje"]) == (
        "1000.50", "0.00", "100.00")


@pytest.mark.asyncio
async def test_validador_sin_plan_sin_arancel_y_plan_inactivo(sesion_pg):
    m, cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        sin_plan = (await _validar(cli, hdr, ids["ana"], ids["obt"])).json()
        m.ana.plan_id = ids["base"]
        await sesion_pg.commit()
        sin_arancel = (await _validar(cli, hdr, ids["ana"], ids["pro"])).json()
        m.plan_base.activo = False
        await sesion_pg.commit()
        inactivo = (await _validar(cli, hdr, ids["ana"], ids["obt"])).json()
    assert sin_plan["estado"] == "sin_plan" and sin_plan["a_cargo"] == "15000.00"
    assert sin_arancel["estado"] == "sin_arancel" and sin_arancel["cubierto"] == "0.00"
    assert inactivo["estado"] == "sin_plan"


@pytest.mark.asyncio
async def test_validador_usa_la_version_vigente_hoy_y_no_crea_filas(sesion_pg):
    from freezegun import freeze_time

    m, cli, hdr, ids = await _mundo(sesion_pg)
    m.ana.plan_id = ids["base"]
    m.ar_obt.vigencia_hasta = date(2026, 9, 30)
    from c11_helpers import crear_arancel

    await crear_arancel(sesion_pg, m.plan_base, "N-003", "12000.00", desde=date(2026, 10, 1))
    await sesion_pg.commit()
    antes = {t: await sesion_pg.scalar(sa.text(f"SELECT count(*) FROM {t}"))
             for t in ("arancel", "movimiento", "presupuesto", "liquidacion")}
    from app.core.security import crear_access_token

    sec_id = m.secretaria.id

    def hdr_congelado():
        # El token se acuña DENTRO del freeze: con el reloj en el pasado, un `iat` del reloj
        # real quedaría en el futuro y verificar_access_token respondería 401.
        return {"sec": {"Authorization": f"Bearer {crear_access_token(sec_id, 'secretaria')}"}}

    async with cli:
        with freeze_time("2026-09-15 15:00:00"):
            vieja = (await _validar(cli, hdr_congelado(), ids["ana"], ids["obt"])).json()
        with freeze_time("2026-10-20 15:00:00"):
            nueva = (await _validar(cli, hdr_congelado(), ids["ana"], ids["obt"])).json()
    assert (vieja["arancel"], nueva["arancel"]) == ("10500.00", "12000.00")
    despues = {t: await sesion_pg.scalar(sa.text(f"SELECT count(*) FROM {t}")) for t in antes}
    assert despues == antes


@pytest.mark.asyncio
async def test_validador_404_odontologo_403_admin_permitido(sesion_pg):
    _, cli, hdr, ids = await _mundo(sesion_pg)
    async with cli:
        assert (await _validar(cli, hdr, 999999, ids["obt"])).status_code == 404
        assert (await _validar(cli, hdr, ids["ana"], 999999)).status_code == 404
        assert (await _validar(cli, hdr, ids["ana"], ids["obt"], "odo")).status_code == 403
        assert (await _validar(cli, hdr, ids["ana"], ids["obt"], "admin")).status_code == 200


# --- 4.7 liquidaciones por HTTP --------------------------------------------------------------------------------

async def _con_liquidacion(sesion):
    m, cli, hdr, ids = await _mundo(sesion)
    await aceptar_presupuesto(sesion, m, [(m.h1, "OBT-001", 1), (m.h2, "PRO-001", 1)],
                              plan=m.plan_base)
    await sesion.commit()
    return m, cli, hdr, ids


@pytest.mark.asyncio
async def test_flujo_http_generar_presentar_cobrar_y_consultar(sesion_pg):
    m, cli, hdr, ids = await _con_liquidacion(sesion_pg)
    async with cli:
        r = await cli.post("/liquidaciones", json={"os_id": ids["os"], "periodo": "2026-10"},
                           headers=hdr["admin"])
        assert r.status_code == 201, r.text
        liq = r.json()
        assert liq["estado"] == "borrador" and liq["total"] == "10500.00"
        assert liq["cantidad_revision"] == 1 and liq["planes"][0]["plan_nombre"] == "Plan Base"
        lid = liq["id"]
        assert (await cli.post(f"/liquidaciones/{lid}/presentar", headers=hdr["admin"])
                ).status_code == 200
        r = await cli.post(f"/liquidaciones/{lid}/cobrar", json={"medio": "transferencia"},
                           headers=hdr["admin"])
        assert r.status_code == 200 and r.json()["estado"] == "cobrada"
        assert (await cli.post(f"/liquidaciones/{lid}/cobrar", json={"medio": "efectivo"},
                               headers=hdr["admin"])).status_code == 409
        lista = (await cli.get("/liquidaciones", headers=hdr["admin"])).json()
        odo = (await cli.get(f"/liquidaciones/{lid}", headers=hdr["odo"])).json()
    assert [x["id"] for x in lista] == [lid]
    assert odo["cantidad_items"] == 2


@pytest.mark.asyncio
async def test_generar_periodo_invalido_422_sin_prestaciones_409_descartar_204(sesion_pg):
    m, cli, hdr, ids = await _con_liquidacion(sesion_pg)
    async with cli:
        for malo in ("2026-13", "octubre", "2026-10-01"):
            r = await cli.post("/liquidaciones", json={"os_id": ids["os"], "periodo": malo},
                               headers=hdr["admin"])
            assert r.status_code == 422, malo
        vacio = await cli.post("/liquidaciones", json={"os_id": ids["os"], "periodo": "2025-01"},
                               headers=hdr["admin"])
        assert vacio.status_code == 409
        lid = (await cli.post("/liquidaciones", json={"os_id": ids["os"], "periodo": "2026-10"},
                              headers=hdr["admin"])).json()["id"]
        assert (await cli.post(f"/liquidaciones/{lid}/descartar", headers=hdr["admin"])
                ).status_code == 204
        assert (await cli.get(f"/liquidaciones/{lid}", headers=hdr["admin"])).status_code == 404


@pytest.mark.asyncio
async def test_odontologo_ve_solo_lo_suyo_y_no_opera_secretaria_403(sesion_pg):
    m, cli, hdr, ids = await _con_liquidacion(sesion_pg)
    async with cli:
        lid = (await cli.post("/liquidaciones", json={"os_id": ids["os"], "periodo": "2026-10"},
                              headers=hdr["admin"])).json()["id"]
        # El otro odontólogo no tiene filas propias: la liquidación no existe para él.
        assert (await cli.get(f"/liquidaciones/{lid}", headers=hdr["odo_b"])).status_code == 404
        assert (await cli.get("/liquidaciones", headers=hdr["odo_b"])).json() == []
        assert (await cli.post(f"/liquidaciones/{lid}/presentar", headers=hdr["odo"])
                ).status_code == 403
        assert (await cli.get("/liquidaciones", headers=hdr["sec"])).status_code == 403


@pytest.mark.asyncio
async def test_revertir_cobro_http_exige_motivo_y_deja_presentada(sesion_pg):
    m, cli, hdr, ids = await _con_liquidacion(sesion_pg)
    async with cli:
        lid = (await cli.post("/liquidaciones", json={"os_id": ids["os"], "periodo": "2026-10"},
                              headers=hdr["admin"])).json()["id"]
        await cli.post(f"/liquidaciones/{lid}/presentar", headers=hdr["admin"])
        await cli.post(f"/liquidaciones/{lid}/cobrar", json={"medio": "efectivo"},
                       headers=hdr["admin"])
        assert (await cli.post(f"/liquidaciones/{lid}/revertir-cobro", json={},
                               headers=hdr["admin"])).status_code == 422
        r = await cli.post(f"/liquidaciones/{lid}/revertir-cobro",
                           json={"motivo": "cobro duplicado"}, headers=hdr["admin"])
        assert r.status_code == 200 and r.json()["estado"] == "presentada"
        assert r.json()["revertida"] is True


# --- 5.2 / 5.3 exportación -----------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_csv_adjunto_utf8_total_coincide_y_403_por_rol(sesion_pg):
    m, cli, hdr, ids = await _con_liquidacion(sesion_pg)
    async with cli:
        liq = (await cli.post("/liquidaciones", json={"os_id": ids["os"], "periodo": "2026-10"},
                              headers=hdr["admin"])).json()
        r = await cli.get(f"/liquidaciones/{liq['id']}/export.csv", headers=hdr["admin"])
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert "attachment" in r.headers["content-disposition"]
        for rol in ("sec", "odo"):
            assert (await cli.get(f"/liquidaciones/{liq['id']}/export.csv",
                                  headers=hdr[rol])).status_code == 403
    filas = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    total = next(f for f in filas if f and f[0] == "TOTAL")
    assert Decimal(total[6]) == Decimal(liq["total"])
    assert any("NO LIQUIDADA" in "".join(f) for f in filas)


@pytest.mark.asyncio
async def test_export_pdf_empieza_con_pdf_y_es_adjunto(sesion_pg):
    m, cli, hdr, ids = await _con_liquidacion(sesion_pg)
    async with cli:
        liq = (await cli.post("/liquidaciones", json={"os_id": ids["os"], "periodo": "2026-10"},
                              headers=hdr["admin"])).json()
        r = await cli.get(f"/liquidaciones/{liq['id']}/export.pdf", headers=hdr["admin"])
        assert (await cli.get(f"/liquidaciones/{liq['id']}/export.pdf",
                              headers=hdr["sec"])).status_code == 403
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
