"""C-08 grupo 7: ningún dato clínico llega a los logs (D-12, RN-CL-04).

`caplog` en DEBUG sobre el logger raíz, con marcadores ficticios en
antecedentes, alergias y motivos, en éxito y en 422. Incluye un control: el
mismo marcador emitido a propósito SÍ se captura (el test no es vacuo).
"""
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente, crear_turno, sembrar_mundo  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

M_ANTEC = "ZZANTECEDENTE-9f3a"
M_ALERG = "ZZALERGIA-71bc"
M_MOT_HC = "ZZMOTIVOHC-5d20"
M_MOT_COR = "ZZMOTIVOCORR-c44e"
M_MOT_BAJA = "ZZMOTIVOBAJA-08ad"
M_422 = "ZZVALIDACION-e1f7"
MARCADORES = (M_ANTEC, M_ALERG, M_MOT_HC, M_MOT_COR, M_MOT_BAJA, M_422)


def test_control_caplog_captura_un_marcador_emitido_a_proposito(caplog):
    caplog.set_level(logging.DEBUG)
    logging.getLogger("app.servicios.clinica_servicio").warning("fuga %s", M_ALERG)
    assert M_ALERG in caplog.text


@pytest.mark.asyncio
async def test_flujo_clinico_no_loguea_phi(sesion_pg, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    m = await sembrar_mundo(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_a, m.sillon)
    cli, bearer, _ = await armar_cliente(sesion_pg)
    odo, sec = bearer(m.odo_a, "odontologo"), bearer(m.secretaria, "secretaria")
    ana_id = m.ana.id
    async with cli:
        hc = (await cli.post("/historias", json={
            "paciente_id": ana_id, "antecedentes": M_ANTEC, "alergias": M_ALERG}, headers=odo)).json()
        assert (await cli.patch(f"/historias/{hc['id']}", json={"alergias": M_ALERG + "-v2"}, headers=odo)).status_code == 200
        base = f"/odontograma/{hc['id']}/hallazgos"
        h1 = (await cli.post(base, json={"pieza_fdi": 16, "cara": "oclusal", "estado": "caries"}, headers=odo)).json()["hallazgo"]
        corr = await cli.put(f"{base}/{h1['id']}", json={
            "pieza_fdi": 16, "cara": "mesial", "estado": "caries", "motivo": M_MOT_COR}, headers=odo)
        assert corr.status_code == 200
        assert (await cli.post(f"{base}/{corr.json()['hallazgo']['id']}/baja", json={"motivo_baja": M_MOT_BAJA}, headers=odo)).status_code == 200
        assert (await cli.get(base + "?incluir_anulados=true", headers=sec)).status_code == 200
        # 422: campo desconocido, pieza inválida y estado fuera de catálogo, todos con marcador.
        assert (await cli.post("/historias", json={"paciente_id": ana_id, "alergias": M_422, "x": M_422}, headers=odo)).status_code == 422
        assert (await cli.post(base, json={"pieza_fdi": 19, "cara": "oclusal", "estado": M_422}, headers=odo)).status_code == 422
        assert (await cli.post(base, json={"pieza_fdi": 16, "cara": "oclusal", "estado": M_422}, headers=odo)).status_code == 422
        assert (await cli.put(f"{base}/{h1['id']}", json={"pieza_fdi": 16, "cara": "oclusal", "estado": "caries", "motivo": M_422, "otro": 1}, headers=odo)).status_code == 422
        assert (await cli.post(f"/historias/{hc['id']}/baja", json={"motivo_baja": M_MOT_HC}, headers=odo)).status_code == 200
    salida = capsys.readouterr()
    visible = caplog.text + salida.out + salida.err
    for marcador in MARCADORES:
        assert marcador not in visible, f"{marcador} apareció en logs/consola"


def test_servicios_y_routers_clinicos_no_usan_logging_ni_print():
    """Defensa estática: el flujo clínico no tiene llamadas de log que interpolen PHI."""
    base = Path(__file__).resolve().parents[1]  # backend/app
    for ruta in ("servicios/clinica_servicio.py", "api/historias.py", "api/odontograma.py",
                 "api/tratamientos.py", "api/clinica_comun.py", "repos/historia_repo.py",
                 "repos/hallazgo_repo.py"):
        texto = (base / ruta).read_text(encoding="utf-8")
        for prohibido in ("logging", "_log.", "logger.", "print("):
            assert prohibido not in texto, f"{ruta} usa {prohibido!r}"
        assert "notificacion_servicio" not in texto, f"{ruta} toca el canal de notificaciones"
