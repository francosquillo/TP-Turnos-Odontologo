"""C-10 grupo 7.7: ningún motivo ni dato clínico llega a logs, URLs ni recibos (D-23, RN-CL-04).

`caplog` en DEBUG sobre el logger raíz, con marcadores ficticios en los motivos, en éxito,
409 y 422. Incluye un control (el marcador emitido a propósito SÍ se captura) y defensas
estáticas sobre el código de caja. Datos ficticios.
"""
import logging
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente  # noqa: E402
from c10_helpers import clave_nueva, crear_presupuesto_aceptado, sembrar_c10  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

M_CIERRE = "ZZCIERRE-4a1e"
M_ANULA = "ZZANULA-90bd"
M_422 = "ZZVALIDA-17c3"
M_409 = "ZZCONFLICTO-5d82"
MARCADORES = (M_CIERRE, M_ANULA, M_422, M_409)
CLINICOS = ("caries", "ausente", "oclusal", "mesial", "pieza", "hallazgo", "pieza_fdi")


def test_control_caplog_captura_un_marcador_emitido_a_proposito(caplog):
    caplog.set_level(logging.DEBUG)
    logging.getLogger("app.servicios.caja_servicio").warning("fuga %s", M_CIERRE)
    assert M_CIERRE in caplog.text


def _textos_de_error(respuesta) -> str:
    detalle = respuesta.json().get("detail")
    if isinstance(detalle, str):
        return detalle
    return " ".join(f"{e.get('msg', '')} {e.get('loc', '')}" for e in detalle)


@pytest.mark.asyncio
async def test_motivo_anulacion_fuera_de_logs(sesion_pg, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    m = await sembrar_c10(sesion_pg)
    p, _ = await crear_presupuesto_aceptado(sesion_pg, m, total="1000.00")
    pid = p.id
    cli, bearer, _ = await armar_cliente(sesion_pg)
    sec, admin = bearer(m.secretaria, "secretaria"), bearer(m.admin, "admin")
    errores = []
    async with cli:
        cobro = (await cli.post("/caja/cobrar", json={
            "presupuesto_id": pid, "monto": "400.00", "medio": "efectivo",
            "clave_idempotencia": clave_nueva()}, headers=sec)).json()
        url = f"/recibos/{cobro['id']}/anular"
        assert (await cli.post(url, json={"motivo": M_ANULA}, headers=admin)).status_code == 200
        errores.append(await cli.post(url, json={"motivo": M_409}, headers=admin))            # 409
        errores.append(await cli.post(url, json={"motivo": M_422, "otro": M_422}, headers=admin))  # 422
        errores.append(await cli.post("/recibos/987654/anular", json={"motivo": M_409}, headers=admin))  # 404
        errores.append(await cli.post(url, json={"motivo": M_409}, headers=sec))              # 403
    assert [e.status_code for e in errores] == [409, 422, 404, 403]
    _sin_marcadores(errores, caplog, capsys)


@pytest.mark.asyncio
async def test_motivo_diferencia_fuera_de_logs(sesion_pg, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    m = await sembrar_c10(sesion_pg)
    p, _ = await crear_presupuesto_aceptado(sesion_pg, m, total="1000.00")
    pid = p.id
    cli, bearer, _ = await armar_cliente(sesion_pg)
    sec = bearer(m.secretaria, "secretaria")
    errores = []
    async with cli:
        await cli.post("/caja/cobrar", json={
            "presupuesto_id": pid, "monto": "400.00", "medio": "efectivo",
            "clave_idempotencia": clave_nueva()}, headers=sec)
        caja_id = (await cli.get("/caja", headers=sec)).json()["caja"]["id"]
        errores.append(await cli.post(  # 422: diferencia con un campo de más (el motivo viaja igual)
            "/caja/cierre", json={"caja_id": caja_id, "total_contado": "300.00",
                                  "motivo_diferencia": M_422, "total_sistema": "1"}, headers=sec))
        ok = await cli.post("/caja/cierre", json={
            "caja_id": caja_id, "total_contado": "300.00", "motivo_diferencia": M_CIERRE}, headers=sec)
        errores.append(await cli.post("/caja/cierre", json={
            "caja_id": caja_id, "total_contado": "300.00", "motivo_diferencia": M_409}, headers=sec))  # 409
        errores.append(await cli.post("/caja/cierre", json={
            "caja_id": 987654, "total_contado": "1.00", "motivo_diferencia": M_409}, headers=sec))  # 404
    assert ok.status_code == 200 and ok.json()["motivo_diferencia"] == M_CIERRE  # el dato sí se guarda
    assert [e.status_code for e in errores] == [422, 409, 404]
    _sin_marcadores(errores, caplog, capsys)


def _sin_marcadores(errores, caplog, capsys):
    for respuesta in errores:
        texto = _textos_de_error(respuesta)
        for marcador in MARCADORES:
            assert marcador not in texto, f"{marcador} en el mensaje de error"
    salida = capsys.readouterr()
    visible = caplog.text + salida.out + salida.err
    for marcador in MARCADORES:
        assert marcador not in visible, f"{marcador} apareció en logs/consola"
    for clinico in CLINICOS:
        assert clinico not in visible.lower(), f"dato clínico {clinico!r} apareció en logs/consola"


def test_rutas_c10_sin_datos_en_url():
    from app.main import create_app

    spec = create_app().openapi()
    consultadas = 0
    for ruta, metodos in spec["paths"].items():
        if not ruta.startswith(("/caja", "/recibos")):
            continue
        for operacion in metodos.values():
            consultadas += 1
            for parametro in operacion.get("parameters", []):
                if parametro["in"] == "query":
                    # La única consulta permitida es la fecha operativa (no es dato clínico).
                    assert parametro["name"] == "fecha", (ruta, parametro["name"])
                if parametro["in"] == "path":
                    assert parametro["schema"]["type"] == "integer", (ruta, parametro["name"])
    assert consultadas >= 5


def test_recibo_out_sin_campos_clinicos():
    from app.esquemas.caja import CajaOut, CobroOut, ReciboOut

    prohibidos = ("hallazgo", "pieza", "cara", "tratamiento", "diagnostico", "alergia", "item")
    for modelo in (ReciboOut, CobroOut, CajaOut):
        for campo in modelo.model_fields:
            assert not any(p in campo for p in prohibidos), (modelo.__name__, campo)
    assert "clave_idempotencia" not in CobroOut.model_fields


def test_codigo_de_caja_no_usa_logging_ni_print():
    """Defensa estática: el flujo de caja no tiene llamadas de log que interpolen motivos."""
    base = Path(__file__).resolve().parents[1]  # backend/app
    for ruta in ("servicios/caja_servicio.py", "api/caja.py", "api/recibos.py",
                 "repos/caja_repo.py", "repos/recibo_repo.py", "esquemas/caja.py"):
        texto = (base / ruta).read_text(encoding="utf-8")
        for prohibido in ("logging", "_log.", "logger.", "print("):
            assert prohibido not in texto, f"{ruta} usa {prohibido!r}"
        assert "notificacion_servicio" not in texto, f"{ruta} toca el canal de notificaciones"
