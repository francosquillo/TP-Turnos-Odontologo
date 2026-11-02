"""C-11 task 2.2: regla pura de cobertura (D-04). Sin base de datos."""
import sys
from decimal import Decimal
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _calc(arancel, precio, cantidad=1):
    from app.servicios.cobertura_servicio import calcular_cobertura

    return calcular_cobertura(
        None if arancel is None else Decimal(arancel), Decimal(precio), cantidad
    )


def test_cobertura_arancel_menor_al_precio_cubre_el_arancel():
    r = _calc("12600.00", "18000.00")
    assert (r.cubierto, r.a_cargo, r.porcentaje) == (
        Decimal("12600.00"), Decimal("5400.00"), Decimal("70.00"))


def test_cobertura_arancel_igual_al_precio_cubre_todo():
    r = _calc("18000.00", "18000.00")
    assert (r.cubierto, r.a_cargo, r.porcentaje) == (
        Decimal("18000.00"), Decimal("0.00"), Decimal("100.00"))


def test_cobertura_arancel_mayor_al_precio_se_topea_al_precio():
    r = _calc("25000.00", "18000.00")
    assert (r.cubierto, r.a_cargo, r.porcentaje) == (
        Decimal("18000.00"), Decimal("0.00"), Decimal("100.00"))


def test_cobertura_cantidad_mayor_a_uno_multiplica_el_tope_unitario():
    r = _calc("12600.00", "18000.00", cantidad=2)
    assert (r.cubierto, r.a_cargo) == (Decimal("25200.00"), Decimal("10800.00"))
    # El tope se aplica por unidad: con arancel mayor, cubre precio x cantidad.
    r = _calc("20000.00", "18000.00", cantidad=3)
    assert (r.cubierto, r.a_cargo) == (Decimal("54000.00"), Decimal("0.00"))


def test_cobertura_centavos_se_redondean_a_dos_decimales():
    r = _calc("33.33", "100.00", cantidad=3)
    assert (r.cubierto, r.a_cargo, r.porcentaje) == (
        Decimal("99.99"), Decimal("200.01"), Decimal("33.33"))


def test_cobertura_sin_arancel_es_cero_y_todo_a_cargo():
    r = _calc(None, "18000.00", cantidad=2)
    assert (r.cubierto, r.a_cargo, r.porcentaje) == (
        Decimal("0.00"), Decimal("36000.00"), Decimal("0.00"))


def test_cobertura_precio_cero_no_divide_por_cero():
    r = _calc("500.00", "0.00")
    assert (r.cubierto, r.a_cargo, r.porcentaje) == (
        Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))


@pytest.mark.parametrize("arancel,precio", [("-1.00", "10.00"), ("10.00", "-1.00")])
def test_cobertura_importes_negativos_son_un_error(arancel, precio):
    with pytest.raises(ValueError):
        _calc(arancel, precio)
