"""C-09 task 6.4: ningún motivo ni dato de ítem llega a los logs (D-20, RN-CL-04).

`caplog` en DEBUG sobre el logger raíz, con marcadores ficticios en los motivos, en
éxito, 409 y 422. Incluye un control (el marcador emitido a propósito SÍ se captura) y
una defensa estática. Los mensajes de error de dominio son fijos: no contienen el
marcador. Nota: el 422 de validación de FastAPI devuelve `input` al propio cliente (no a
los logs); aquí se revisan los `msg`/`loc`, que son los textos propios del servicio.
"""
import logging
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente  # noqa: E402
from c09_helpers import sembrar_c09  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

M_RECHAZO = "ZZRECHAZO-3b19"
M_BAJA = "ZZBAJAPRES-77aa"
M_ANULA = "ZZANULACION-e02c"
M_422 = "ZZVALIDA9-51d8"
M_409 = "ZZCONFLICTO-c6f4"
MARCADORES = (M_RECHAZO, M_BAJA, M_ANULA, M_422, M_409)
CLINICOS = ("caries", "ausente", "oclusal", "mesial", "pieza", "hallazgo", "pieza_fdi")


def test_control_caplog_captura_un_marcador_emitido_a_proposito(caplog):
    caplog.set_level(logging.DEBUG)
    logging.getLogger("app.servicios.presupuesto_servicio").warning("fuga %s", M_RECHAZO)
    assert M_RECHAZO in caplog.text


def _textos_de_error(respuesta) -> str:
    """Solo los textos propios del servidor: `detail` fijo o `msg`/`loc` de validación."""
    detalle = respuesta.json().get("detail")
    if isinstance(detalle, str):
        return detalle
    return " ".join(f"{e.get('msg', '')} {e.get('loc', '')}" for e in detalle)


@pytest.mark.asyncio
async def test_flujo_de_presupuestos_no_loguea_motivos(sesion_pg, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    m = await sembrar_c09(sesion_pg)
    ana, h1, h2, con, pro = m.ana.id, m.h1.id, m.h2.id, m.trat["CON-001"].id, m.trat["PRO-001"].id
    cli, bearer, _ = await armar_cliente(sesion_pg)
    odo, admin, sec = bearer(m.odo_a, "odontologo"), bearer(m.admin, "admin"), bearer(m.secretaria, "secretaria")
    errores: list = []

    def item(h, t):
        return {"hallazgo_id": h, "tratamiento_id": t}

    async with cli:
        # éxito: rechazo, baja y anulación con marcador en el motivo
        p1 = (await cli.post("/presupuestos", json={"paciente_id": ana, "items": [item(h1, con)]}, headers=odo)).json()
        await cli.post(f"/presupuestos/{p1['id']}/presentar", headers=odo)
        assert (await cli.post(f"/presupuestos/{p1['id']}/rechazar", json={"motivo": M_RECHAZO}, headers=odo)).status_code == 200
        p2 = (await cli.post("/presupuestos", json={"paciente_id": ana, "items": [item(h1, con)]}, headers=odo)).json()
        assert (await cli.post(f"/presupuestos/{p2['id']}/baja", json={"motivo_baja": M_BAJA}, headers=odo)).status_code == 200
        p3 = (await cli.post("/presupuestos", json={"paciente_id": ana, "items": [item(h2, pro)]}, headers=odo)).json()
        await cli.post(f"/presupuestos/{p3['id']}/presentar", headers=odo)
        await cli.post(f"/presupuestos/{p3['id']}/aceptar", headers=odo)
        cargo = (await cli.get(f"/cuentas/{ana}", headers=sec)).json()["movimientos"][0]
        url = f"/cuentas/{ana}/movimientos/{cargo['id']}/anular"
        assert (await cli.post(url, json={"motivo": M_ANULA}, headers=admin)).status_code == 201

        # 409: repetir cada operación con marcador en el motivo
        errores.append(await cli.post(url, json={"motivo": M_409}, headers=admin))
        errores.append(await cli.post(f"/presupuestos/{p1['id']}/rechazar", json={"motivo": M_409}, headers=odo))
        errores.append(await cli.post(f"/presupuestos/{p3['id']}/baja", json={"motivo_baja": M_409}, headers=odo))
        errores.append(await cli.post(f"/presupuestos/{p3['id']}/aceptar", headers=odo))
        # 422: campo desconocido y motivos inválidos, todos con marcador
        errores.append(await cli.post(url, json={"motivo": M_422, "otro": M_422}, headers=admin))
        errores.append(await cli.post(f"/presupuestos/{p3['id']}/rechazar", json={"motivo": M_422, "x": 1}, headers=odo))
        errores.append(await cli.post(f"/presupuestos/{p3['id']}/baja", json={"motivo_baja": M_422, "x": 1}, headers=odo))
        errores.append(await cli.post("/presupuestos", json={"paciente_id": ana, "items": [item(h1, con)], "estado": M_422}, headers=odo))
        # 404 / 403
        errores.append(await cli.post("/cuentas/987654/movimientos/1/anular", json={"motivo": M_409}, headers=admin))
        errores.append(await cli.post(url, json={"motivo": M_409}, headers=sec))

    assert [e.status_code for e in errores] == [409, 409, 409, 409, 422, 422, 422, 422, 404, 403]
    for respuesta in errores:
        texto = _textos_de_error(respuesta)
        for marcador in MARCADORES:
            assert marcador not in texto, f"{marcador} en el mensaje de error"
    salida = capsys.readouterr()
    visible = caplog.text + salida.out + salida.err
    for marcador in MARCADORES:
        assert marcador not in visible, f"{marcador} apareció en logs/consola"
    # Datos clínicos del flujo (hallazgos 16 oclusal / 26 mesial / 36 ausente): tampoco salen.
    for clinico in CLINICOS:
        assert clinico not in visible.lower(), f"dato clínico {clinico!r} apareció en logs/consola"


def test_los_motivos_no_viajan_por_query():
    from app.main import create_app

    spec = create_app().openapi()
    for ruta, metodos in spec["paths"].items():
        if not ruta.startswith(("/presupuestos", "/cuentas")):
            continue
        for operacion in metodos.values():
            for parametro in operacion.get("parameters", []):
                if parametro["in"] == "query":
                    assert "motivo" not in parametro["name"], (ruta, parametro["name"])


def test_codigo_de_presupuestos_y_cuentas_no_usa_logging_ni_print():
    """Defensa estática: el flujo no tiene llamadas de log que interpolen motivos o ítems."""
    base = Path(__file__).resolve().parents[1]  # backend/app
    for ruta in ("servicios/presupuesto_servicio.py", "servicios/cuenta_servicio.py",
                 "api/presupuestos.py", "api/cuentas.py", "repos/presupuesto_repo.py",
                 "repos/cuenta_repo.py"):
        texto = (base / ruta).read_text(encoding="utf-8")
        for prohibido in ("logging", "_log.", "logger.", "print("):
            assert prohibido not in texto, f"{ruta} usa {prohibido!r}"
        assert "notificacion_servicio" not in texto, f"{ruta} toca el canal de notificaciones"
