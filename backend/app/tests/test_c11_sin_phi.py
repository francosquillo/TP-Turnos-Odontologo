"""C-11 task 4.9: ningún motivo ni dato clínico llega a logs, URLs ni informes (RN-CL-04).

`caplog` en DEBUG con marcadores ficticios en los motivos de la reversión (éxito, 409, 422 y
403), más defensas estáticas que corren sin base de datos. Datos ficticios.
"""
import logging
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente  # noqa: E402
from c11_helpers import aceptar_presupuesto, sembrar_c11  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

M_REVERSION = "ZZREVERSION-3c9a"
M_422 = "ZZVALIDA-72e1"
M_409 = "ZZCONFLICTO-18fd"
MARCADORES = (M_REVERSION, M_422, M_409)
CLINICOS = ("caries", "ausente", "oclusal", "mesial", "pieza", "hallazgo", "pieza_fdi")
ARCHIVOS_C11 = (
    "servicios/liquidacion_servicio.py", "servicios/liquidacion_export.py",
    "servicios/obra_social_servicio.py", "servicios/cobertura_servicio.py",
    "api/liquidaciones.py", "api/obras_sociales.py", "api/planes.py", "api/aranceles.py",
    "api/cobertura.py", "repos/liquidacion_repo.py", "repos/obra_social_repo.py",
    "esquemas/liquidacion.py", "esquemas/obra_social.py",
)


def test_control_caplog_captura_un_marcador_emitido_a_proposito(caplog):
    caplog.set_level(logging.DEBUG)
    logging.getLogger("app.servicios.liquidacion_servicio").warning("fuga %s", M_REVERSION)
    assert M_REVERSION in caplog.text


def test_codigo_de_liquidaciones_no_usa_logging_ni_print():
    base = Path(__file__).resolve().parents[1]  # backend/app
    for ruta in ARCHIVOS_C11:
        texto = (base / ruta).read_text(encoding="utf-8")
        for prohibido in ("logging", "_log.", "logger.", "print("):
            assert prohibido not in texto, f"{ruta} usa {prohibido!r}"
        assert "notificacion_servicio" not in texto, f"{ruta} toca el canal de notificaciones"


def test_rutas_c11_sin_datos_del_paciente_en_url_ni_query_libre():
    from app.main import create_app

    permitidas = {"obra_social_id", "plan_id", "codigo", "paciente_id", "tratamiento_id"}
    consultadas = 0
    for ruta, metodos in create_app().openapi()["paths"].items():
        if not ruta.startswith(("/liquidaciones", "/obras-sociales", "/planes", "/aranceles",
                                "/validador-cobertura")):
            continue
        for operacion in metodos.values():
            consultadas += 1
            for parametro in operacion.get("parameters", []):
                if parametro["in"] == "query":
                    assert parametro["name"] in permitidas, (ruta, parametro["name"])
                if parametro["in"] == "path":
                    assert parametro["schema"]["type"] == "integer", (ruta, parametro["name"])
    assert consultadas >= 15


def test_esquemas_de_liquidacion_y_caja_sin_campos_clinicos():
    from app.esquemas.caja import IngresoLiquidacionOut
    from app.esquemas.liquidacion import (
        ItemLiquidacionOut, LiquidacionDetalleOut, LiquidacionOut, PlanLiquidacionOut,
    )

    prohibidos = ("hallazgo", "pieza", "cara", "diagnostico", "alergia", "nota", "antecedente")
    for modelo in (ItemLiquidacionOut, LiquidacionDetalleOut, LiquidacionOut,
                   PlanLiquidacionOut, IngresoLiquidacionOut):
        for campo in modelo.model_fields:
            assert not any(p in campo for p in prohibidos), (modelo.__name__, campo)
    # El ingreso en caja la ve la secretaria: sin datos de pacientes.
    assert not {c for c in IngresoLiquidacionOut.model_fields if "paciente" in c}


def test_la_consulta_de_filas_no_selecciona_pieza_ni_hallazgo():
    base = Path(__file__).resolve().parents[1]
    texto = (base / "repos/liquidacion_repo.py").read_text(encoding="utf-8")
    cuerpo = texto[texto.index("async def filas"):texto.index("async def eliminar_con_items")]
    for prohibido in ("pieza_fdi", "HallazgoOdontograma", "notas", "cara"):
        assert prohibido not in cuerpo, prohibido


@pytest.mark.asyncio
async def test_motivo_de_reversion_fuera_de_logs_y_de_errores(sesion_pg, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    os_id = m.os.id
    cli, bearer, _ = await armar_cliente(sesion_pg)
    admin, sec = bearer(m.admin, "admin"), bearer(m.secretaria, "secretaria")
    errores = []
    async with cli:
        lid = (await cli.post("/liquidaciones", json={"os_id": os_id, "periodo": "2026-10"},
                              headers=admin)).json()["id"]
        url = f"/liquidaciones/{lid}/revertir-cobro"
        errores.append(await cli.post(url, json={"motivo": M_409}, headers=admin))  # 409: borrador
        await cli.post(f"/liquidaciones/{lid}/presentar", headers=admin)
        await cli.post(f"/liquidaciones/{lid}/cobrar", json={"medio": "efectivo"}, headers=admin)
        ok = await cli.post(url, json={"motivo": M_REVERSION}, headers=admin)
        errores.append(await cli.post(url, json={"motivo": M_409}, headers=admin))  # 409: doble
        errores.append(await cli.post(url, json={"motivo": M_422, "otro": M_422}, headers=admin))
        errores.append(await cli.post(url, json={"motivo": M_409}, headers=sec))  # 403
    assert ok.status_code == 200
    assert [e.status_code for e in errores] == [409, 409, 422, 403]
    for respuesta in errores:
        detalle = respuesta.json().get("detail")
        texto = detalle if isinstance(detalle, str) else " ".join(
            f"{e.get('msg', '')} {e.get('loc', '')}" for e in detalle)
        for marcador in MARCADORES:
            assert marcador not in texto, f"{marcador} en el mensaje de error"
    salida = capsys.readouterr()
    visible = caplog.text + salida.out + salida.err
    for marcador in MARCADORES:
        assert marcador not in visible, f"{marcador} apareció en logs/consola"
    for clinico in CLINICOS:
        assert clinico not in visible.lower(), f"dato clínico {clinico!r} apareció en logs"
