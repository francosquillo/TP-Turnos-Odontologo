"""C-09 task 6.3: matriz RBAC de presupuestos y cuentas + ausencia de rutas de cobro.

Los guards por rol se resuelven ANTES de mirar el recurso, así que los 403 usan ids
ficticios; las lecturas permitidas usan datos reales. Datos ficticios.
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

ESCRITURAS = [
    ("POST", "/presupuestos", {"paciente_id": 1, "items": [{"hallazgo_id": 1, "tratamiento_id": 1}]}),
    ("PUT", "/presupuestos/1", {"items": [{"hallazgo_id": 1, "tratamiento_id": 1}]}),
    ("POST", "/presupuestos/1/presentar", None),
    ("POST", "/presupuestos/1/aceptar", None),
    ("POST", "/presupuestos/1/rechazar", {"motivo": "x"}),
    ("POST", "/presupuestos/1/baja", {"motivo_baja": "x"}),
]


async def _mundo(sesion):
    m = await sembrar_c09(sesion)
    cli, bearer, app = await armar_cliente(sesion)
    hdr = {
        "odo": bearer(m.odo_a, "odontologo"), "sec": bearer(m.secretaria, "secretaria"),
        "admin": bearer(m.admin, "admin"),
    }
    return cli, hdr, app, m


@pytest.mark.asyncio
@pytest.mark.parametrize("rol", ["sec", "admin"])
@pytest.mark.parametrize("metodo,ruta,cuerpo", ESCRITURAS)
async def test_secretaria_y_admin_sin_escritura_403(sesion_pg, rol, metodo, ruta, cuerpo):
    cli, hdr, _, _ = await _mundo(sesion_pg)
    async with cli:
        r = await cli.request(metodo, ruta, json=cuerpo, headers=hdr[rol])
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_escritura_ajena_403_pero_lectura_del_colega_200(sesion_pg):
    """El odontólogo B (con vínculo) lee el presupuesto de A pero no lo acepta (D-10)."""
    from c08_helpers import crear_turno

    from app.core.security import crear_access_token

    m = await sembrar_c09(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_b, m.sillon)
    cli, bearer, _ = await armar_cliente(sesion_pg)
    a, b = bearer(m.odo_a, "odontologo"), bearer(m.odo_b, "odontologo")
    item = {"hallazgo_id": m.h1.id, "tratamiento_id": m.trat["CON-001"].id}
    async with cli:
        p = (await cli.post("/presupuestos", json={"paciente_id": m.ana.id, "items": [item]}, headers=a)).json()
        await cli.post(f"/presupuestos/{p['id']}/presentar", headers=a)
        lectura = await cli.get(f"/presupuestos/{p['id']}", headers=b)
        aceptar = await cli.post(f"/presupuestos/{p['id']}/aceptar", headers=b)
        baja = await cli.post(f"/presupuestos/{p['id']}/rechazar", json={"motivo": "x"}, headers=b)
        igual = await cli.get(f"/presupuestos/{p['id']}", headers=a)
    assert lectura.status_code == 200 and lectura.json()["es_propio"] is False
    assert aceptar.status_code == 403 and baja.status_code == 403
    assert igual.json()["estado"] == "presentado"  # nada cambió


@pytest.mark.asyncio
async def test_odontologo_sin_vinculo_no_lee_403(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    cli, bearer, _ = await armar_cliente(sesion_pg)
    sin_vinculo = bearer(m.odo_b, "odontologo")
    async with cli:
        r = await cli.get(f"/presupuestos?paciente_id={m.ana.id}", headers=sin_vinculo)
    assert r.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("rol,esperado", [("sec", 200), ("admin", 200), ("odo", 200)])
async def test_lectura_de_presupuestos_por_rol(sesion_pg, rol, esperado):
    cli, hdr, _, m = await _mundo(sesion_pg)
    async with cli:
        r = await cli.get(f"/presupuestos?paciente_id={m.ana.id}", headers=hdr[rol])
    assert r.status_code == esperado


@pytest.mark.asyncio
@pytest.mark.parametrize("metodo,ruta,cuerpo", [
    ("GET", "/cuentas/1", None),
    ("POST", "/cuentas/1/movimientos/1/anular", {"motivo": "x"}),
])
async def test_odontologo_en_cuentas_403(sesion_pg, metodo, ruta, cuerpo):
    cli, hdr, _, _ = await _mundo(sesion_pg)
    async with cli:
        r = await cli.request(metodo, ruta, json=cuerpo, headers=hdr["odo"])
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_secretaria_no_anula_403_y_nada_cambia(sesion_pg):
    cli, hdr, _, m = await _mundo(sesion_pg)
    item = {"hallazgo_id": m.h1.id, "tratamiento_id": m.trat["CON-001"].id}
    async with cli:
        p = (await cli.post("/presupuestos", json={"paciente_id": m.ana.id, "items": [item]}, headers=hdr["odo"])).json()
        await cli.post(f"/presupuestos/{p['id']}/presentar", headers=hdr["odo"])
        await cli.post(f"/presupuestos/{p['id']}/aceptar", headers=hdr["odo"])
        cuenta = (await cli.get(f"/cuentas/{m.ana.id}", headers=hdr["sec"])).json()
        cargo_id = cuenta["movimientos"][0]["id"]
        r = await cli.post(f"/cuentas/{m.ana.id}/movimientos/{cargo_id}/anular", json={"motivo": "x"}, headers=hdr["sec"])
        despues = (await cli.get(f"/cuentas/{m.ana.id}", headers=hdr["admin"])).json()
    assert r.status_code == 403
    assert despues["saldo"] == "1000.50" and len(despues["movimientos"]) == 1


@pytest.mark.asyncio
async def test_admin_si_anula_y_secretaria_y_admin_leen_la_cuenta(sesion_pg):
    cli, hdr, _, m = await _mundo(sesion_pg)
    item = {"hallazgo_id": m.h1.id, "tratamiento_id": m.trat["CON-001"].id}
    async with cli:
        p = (await cli.post("/presupuestos", json={"paciente_id": m.ana.id, "items": [item]}, headers=hdr["odo"])).json()
        await cli.post(f"/presupuestos/{p['id']}/presentar", headers=hdr["odo"])
        await cli.post(f"/presupuestos/{p['id']}/aceptar", headers=hdr["odo"])
        lee_sec = await cli.get(f"/cuentas/{m.ana.id}", headers=hdr["sec"])
        lee_admin = await cli.get(f"/cuentas/{m.ana.id}", headers=hdr["admin"])
        cargo_id = lee_sec.json()["movimientos"][0]["id"]
        anula = await cli.post(f"/cuentas/{m.ana.id}/movimientos/{cargo_id}/anular", json={"motivo": "x"}, headers=hdr["admin"])
    assert (lee_sec.status_code, lee_admin.status_code, anula.status_code) == (200, 200, 201)


# --- ausencia de rutas de cobro (C-10) -------------------------------------------------------

_PALABRAS_DE_COBRO = ("cobr", "pago", "recibo", "caja", "cobrar")


def test_no_existe_ruta_de_cobro():
    from app.main import create_app

    app = create_app()
    rutas = [(r.path, sorted(getattr(r, "methods", None) or [])) for r in app.routes]
    propias = [(p, mt) for p, mt in rutas if p.startswith(("/presupuestos", "/cuentas"))]
    assert propias, "el control no es vacuo: debe haber rutas de C-09"
    for path, metodos in propias:
        assert not any(palabra in path.lower() for palabra in _PALABRAS_DE_COBRO), path
    # En todo el árbol, la única ruta de cobros es el stub de C-01: solo GET.
    cobros = [(p, mt) for p, mt in rutas if "cobr" in p.lower() or "recibo" in p.lower() or "pago" in p.lower()]
    assert cobros == [("/cobros", ["GET"])], cobros
    # Ninguna ruta de cuentas permite crear movimientos: la única escritura es `anular`.
    escrituras = {p for p, mt in propias if p.startswith("/cuentas") and set(mt) - {"GET", "HEAD"}}
    assert escrituras == {"/cuentas/{paciente_id}/movimientos/{movimiento_id}/anular"}


def test_ninguna_ruta_de_presupuestos_escribe_estado_cobrado():
    from app.esquemas.presupuesto import PresupuestoIn, PresupuestoPut

    for modelo in (PresupuestoIn, PresupuestoPut):
        assert "estado" not in modelo.model_fields
