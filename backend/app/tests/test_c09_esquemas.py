"""C-09 grupo 2: esquemas Pydantic estrictos de presupuesto y cuenta (D-04, D-06, D-09).

Puro (sin DB): siempre corre. Datos ficticios.
"""
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

ITEM = {"hallazgo_id": 1, "tratamiento_id": 2, "cantidad": 1}
ALTA = {"paciente_id": 7, "items": [ITEM]}
AHORA = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


# --- 2.1 presupuesto ---------------------------------------------------------------

def test_presupuesto_valido_aceptado():
    from app.esquemas.presupuesto import PresupuestoIn

    p = PresupuestoIn(**ALTA)
    assert p.paciente_id == 7 and p.items[0].cantidad == 1


def test_presupuesto_sin_items_invalido():
    from app.esquemas.presupuesto import PresupuestoIn

    with pytest.raises(ValidationError):
        PresupuestoIn(paciente_id=7, items=[])


@pytest.mark.parametrize("n,valido", [(50, True), (51, False)])
def test_presupuesto_tope_de_items(n, valido):
    from app.esquemas.presupuesto import PresupuestoIn

    items = [{"hallazgo_id": i, "tratamiento_id": 2} for i in range(1, n + 1)]
    if valido:
        assert len(PresupuestoIn(paciente_id=7, items=items).items) == 50
    else:
        with pytest.raises(ValidationError):
            PresupuestoIn(paciente_id=7, items=items)


def test_presupuesto_51_items_invalido():
    from app.esquemas.presupuesto import PresupuestoIn

    items = [{"hallazgo_id": i, "tratamiento_id": 2} for i in range(1, 52)]
    with pytest.raises(ValidationError):
        PresupuestoIn(paciente_id=7, items=items)


@pytest.mark.parametrize("faltante", ["hallazgo_id", "tratamiento_id"])
def test_item_sin_hallazgo_o_tratamiento_invalido(faltante):
    from app.esquemas.presupuesto import ItemIn

    datos = {k: v for k, v in ITEM.items() if k != faltante}
    with pytest.raises(ValidationError):
        ItemIn(**datos)


def test_item_sin_hallazgo_invalido():
    from app.esquemas.presupuesto import ItemIn

    with pytest.raises(ValidationError):
        ItemIn(tratamiento_id=2, cantidad=1)


def test_item_sin_tratamiento_invalido():
    from app.esquemas.presupuesto import ItemIn

    with pytest.raises(ValidationError):
        ItemIn(hallazgo_id=1, cantidad=1)


@pytest.mark.parametrize("cantidad", [0, 100, -1])
def test_item_cantidad_fuera_de_rango_invalida(cantidad):
    from app.esquemas.presupuesto import ItemIn

    with pytest.raises(ValidationError):
        ItemIn(**{**ITEM, "cantidad": cantidad})


def test_item_cantidad_100_invalida():
    from app.esquemas.presupuesto import ItemIn

    with pytest.raises(ValidationError):
        ItemIn(**{**ITEM, "cantidad": 100})


@pytest.mark.parametrize("cantidad", [1, 99])
def test_item_cantidad_en_los_bordes_valida(cantidad):
    from app.esquemas.presupuesto import ItemIn

    assert ItemIn(**{**ITEM, "cantidad": cantidad}).cantidad == cantidad


def test_item_cantidad_por_defecto_es_uno():
    from app.esquemas.presupuesto import ItemIn

    assert ItemIn(hallazgo_id=1, tratamiento_id=2).cantidad == 1


def test_item_con_precio_invalido():
    from app.esquemas.presupuesto import ItemIn

    with pytest.raises(ValidationError):
        ItemIn(**ITEM, precio="1.00")


@pytest.mark.parametrize("campo,valor", [
    ("total", "10.00"), ("estado", "aceptado"), ("profesional_id", 3),
    ("motivo_rechazo", "x"),
])
def test_presupuesto_con_campos_reservados_al_servidor_invalido(campo, valor):
    from app.esquemas.presupuesto import PresupuestoIn

    with pytest.raises(ValidationError):
        PresupuestoIn(**ALTA, **{campo: valor})


def test_presupuesto_con_total_invalido():
    from app.esquemas.presupuesto import PresupuestoIn

    with pytest.raises(ValidationError):
        PresupuestoIn(**ALTA, total="10.00")


@pytest.mark.parametrize("modelo", ["PresupuestoIn", "PresupuestoPut"])
def test_presupuesto_con_estado_cobrado_invalido(modelo):
    from app.esquemas import presupuesto

    clase = getattr(presupuesto, modelo)
    datos = {**ALTA, "estado": "cobrado"}
    if modelo == "PresupuestoPut":
        datos.pop("paciente_id")
    with pytest.raises(ValidationError):
        clase(**datos)


def test_put_solo_trae_items_y_exige_alguno():
    from app.esquemas.presupuesto import PresupuestoPut

    assert len(PresupuestoPut(items=[ITEM]).items) == 1
    with pytest.raises(ValidationError):
        PresupuestoPut(items=[])
    with pytest.raises(ValidationError):
        PresupuestoPut(items=[ITEM], paciente_id=7)


def test_items_repetidos_invalidos():
    from app.esquemas.presupuesto import PresupuestoIn

    with pytest.raises(ValidationError):
        PresupuestoIn(paciente_id=7, items=[ITEM, {**ITEM, "cantidad": 3}])


def test_mismo_hallazgo_con_otro_tratamiento_es_valido():
    from app.esquemas.presupuesto import PresupuestoIn

    p = PresupuestoIn(paciente_id=7, items=[ITEM, {**ITEM, "tratamiento_id": 9}])
    assert len(p.items) == 2


def test_rechazo_sin_motivo_invalido():
    from app.esquemas.presupuesto import RechazoIn

    for malo in ({}, {"motivo": ""}, {"motivo": "   "}):
        with pytest.raises(ValidationError):
            RechazoIn(**malo)
    assert RechazoIn(motivo="  Precio alto ").motivo == "Precio alto"


def test_rechazo_con_campo_extra_invalido():
    from app.esquemas.presupuesto import RechazoIn

    with pytest.raises(ValidationError):
        RechazoIn(motivo="x", estado="aceptado")


def _salida(**cambios):
    from app.esquemas.presupuesto import ItemOut, PresupuestoOut

    item = ItemOut(
        id=1, hallazgo_id=1, tratamiento_id=2, tratamiento_nombre="Obturación",
        pieza_fdi=16, cara="oclusal", cantidad=2, precio=Decimal("1000.5"),
        subtotal=Decimal("2001"), hallazgo_vigente=True,
    )
    datos = dict(
        id=5, paciente_id=7, profesional_id=3, estado="borrador", total=Decimal("2501"),
        motivo_rechazo=None, presentado_at=None, decidido_at=None, created_at=AHORA,
        updated_at=AHORA, cargo_anulado=False, es_propio=True, items=[item],
    )
    datos.update(cambios)
    return PresupuestoOut(**datos)


def test_importe_serializa_como_texto():
    salida = _salida().model_dump(mode="json")
    assert salida["total"] == "2501.00"
    assert salida["items"][0]["precio"] == "1000.50"
    assert salida["items"][0]["subtotal"] == "2001.00"


def test_importe_cero_y_grande_serializan_con_dos_decimales():
    assert _salida(total=Decimal("0")).model_dump(mode="json")["total"] == "0.00"
    assert _salida(total=Decimal("49500000000000.5")).model_dump(mode="json")["total"] == "49500000000000.50"


def test_salida_no_admite_campos_extra():
    with pytest.raises(ValidationError):
        _salida(deleted_at=None)


def test_salida_admite_pieza_y_cara_nulas_para_la_vista_financiera():
    from app.esquemas.presupuesto import ItemOut

    item = ItemOut(
        id=1, hallazgo_id=1, tratamiento_id=2, tratamiento_nombre="X", pieza_fdi=None,
        cara=None, cantidad=1, precio=Decimal("1"), subtotal=Decimal("1"),
        hallazgo_vigente=False,
    )
    assert item.pieza_fdi is None and item.cara is None


# --- 2.2 cuenta corriente -----------------------------------------------------------------

def test_anulacion_sin_motivo_invalida():
    from app.esquemas.cuenta import AnulacionIn

    for malo in ({}, {"motivo": ""}, {"motivo": "  "}):
        with pytest.raises(ValidationError):
            AnulacionIn(**malo)
    assert AnulacionIn(motivo=" Error de carga ").motivo == "Error de carga"


def test_anulacion_campo_extra_invalida():
    from app.esquemas.cuenta import AnulacionIn

    with pytest.raises(ValidationError):
        AnulacionIn(motivo="x", monto="10.00")


def _mov(**cambios):
    from app.esquemas.cuenta import MovimientoOut

    datos = dict(
        id=1, tipo="cargo", monto=Decimal("1000"), concepto="Presupuesto 12", motivo=None,
        turno_id=None, presupuesto_id=12, recibo_id=None, anula_a_id=None, creado_por=4,
        created_at=AHORA, anulado=False,
    )
    datos.update(cambios)
    return MovimientoOut(**datos)


def test_cuenta_saldo_serializa_como_texto():
    from app.esquemas.cuenta import CuentaOut

    cuenta = CuentaOut(
        paciente_id=7, saldo=Decimal("500"), movimientos=[_mov(), _mov(tipo="pago", monto=Decimal("-500"))]
    )
    datos = cuenta.model_dump(mode="json")
    assert datos["saldo"] == "500.00"
    assert [m["monto"] for m in datos["movimientos"]] == ["1000.00", "-500.00"]


def test_cuenta_saldo_negativo_y_cero_serializan_como_texto():
    from app.esquemas.cuenta import CuentaOut

    assert CuentaOut(paciente_id=7, saldo=Decimal("-0.5"), movimientos=[]).model_dump(mode="json")["saldo"] == "-0.50"
    assert CuentaOut(paciente_id=7, saldo=Decimal("0"), movimientos=[]).model_dump(mode="json")["saldo"] == "0.00"


def test_movimiento_salida_no_admite_extra():
    with pytest.raises(ValidationError):
        _mov(saldo="1.00")
