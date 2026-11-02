"""C-11 tasks 2.1 y 4.x: esquemas estrictos de obras sociales y liquidaciones (sin DB)."""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _arancel(**cambios):
    from app.esquemas.obra_social import ArancelIn

    datos = {"plan_id": 1, "codigo_nomenclador": "N-001", "descripcion": "Consulta",
             "precio": "1500.50", "vigencia_desde": "2026-10-01"}
    datos.update(cambios)
    return ArancelIn(**datos)


def test_arancel_in_acepta_precio_con_dos_decimales_y_rango_abierto():
    a = _arancel()
    assert a.precio == Decimal("1500.50") and a.vigencia_hasta is None


@pytest.mark.parametrize("precio", ["0", "0.00", "-1", "1.005", "NaN", "Infinity"])
def test_arancel_in_rechaza_precios_invalidos(precio):
    with pytest.raises(ValidationError):
        _arancel(precio=precio)


def test_arancel_in_rechaza_vigencia_hasta_anterior_a_desde():
    with pytest.raises(ValidationError):
        _arancel(vigencia_hasta="2026-09-30")
    # Un solo día de vigencia es válido (rango cerrado en ambos extremos).
    assert _arancel(vigencia_hasta="2026-10-01").vigencia_hasta == date(2026, 10, 1)


def test_esquemas_rechazan_campos_extra():
    from app.esquemas.obra_social import ArancelPatch, ObraSocialIn, PlanIn

    with pytest.raises(ValidationError):
        _arancel(extra="x")
    with pytest.raises(ValidationError):
        ObraSocialIn(nombre="OS", otro=1)
    with pytest.raises(ValidationError):
        PlanIn(obra_social_id=1, nombre="P", precio=1)
    with pytest.raises(ValidationError):
        ArancelPatch(vigencia_hasta="2026-12-31", precio="1.00")


def test_arancel_patch_solo_admite_vigencia_hasta_y_la_exige():
    from app.esquemas.obra_social import ArancelPatch

    assert set(ArancelPatch.model_fields) == {"vigencia_hasta"}
    with pytest.raises(ValidationError):
        ArancelPatch()


def test_nombre_vacio_o_solo_espacios_rechazado():
    from app.esquemas.obra_social import ObraSocialIn

    for nombre in ("", "   "):
        with pytest.raises(ValidationError):
            ObraSocialIn(nombre=nombre)
    assert ObraSocialIn(nombre="  OS Ficticia  ").nombre == "OS Ficticia"


def test_plan_paciente_exige_plan_id_explicito_aunque_sea_null():
    from app.esquemas.obra_social import PlanPacienteIn

    assert PlanPacienteIn(plan_id=None).plan_id is None
    assert PlanPacienteIn(plan_id=3).plan_id == 3
    with pytest.raises(ValidationError):
        PlanPacienteIn()


@pytest.mark.parametrize("periodo,ok", [
    ("2026-10", True), ("2026-01", True), ("2026-12", True),
    ("2026-13", False), ("2026-00", False), ("2026-1", False), ("202610", False),
    ("2026-10-01", False),
])
def test_generar_liquidacion_valida_periodo_yyyy_mm(periodo, ok):
    from app.esquemas.liquidacion import GenerarLiquidacionIn

    if ok:
        assert GenerarLiquidacionIn(os_id=1, periodo=periodo).periodo == date.fromisoformat(
            periodo + "-01")
    else:
        with pytest.raises(ValidationError):
            GenerarLiquidacionIn(os_id=1, periodo=periodo)


def test_cobrar_liquidacion_exige_medio_del_catalogo():
    from app.esquemas.liquidacion import CobrarLiquidacionIn

    assert CobrarLiquidacionIn(medio="transferencia").medio == "transferencia"
    with pytest.raises(ValidationError):
        CobrarLiquidacionIn(medio="bitcoin")
    with pytest.raises(ValidationError):
        CobrarLiquidacionIn(medio="efectivo", monto="10.00")


def test_revertir_cobro_exige_motivo_no_vacio():
    from app.esquemas.liquidacion import RevertirCobroIn

    with pytest.raises(ValidationError):
        RevertirCobroIn(motivo="  ")
    with pytest.raises(ValidationError):
        RevertirCobroIn()
    assert RevertirCobroIn(motivo=" error de carga ").motivo == "error de carga"
