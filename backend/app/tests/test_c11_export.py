"""C-11 tasks 5.1 a 5.3: informe, CSV y PDF de la liquidación con datos en memoria (sin DB).

El informe no incluye pieza dental, hallazgo ni notas clínicas (RN-CL-04). El CSV neutraliza
fórmulas y su total coincide con la liquidación. Datos ficticios.
"""
import csv
import io
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _item(i, paciente, monto, *, revision=False, codigo="N-003", desc="Obturación simple", cant=1):
    from app.esquemas.liquidacion import ItemLiquidacionOut

    return ItemLiquidacionOut(
        id=i, item_presupuesto_id=100 + i, fecha_prestacion=date(2026, 10, 30),
        paciente_nombre=paciente, codigo=codigo, descripcion=desc, cantidad=cant,
        monto=Decimal(monto), revision=revision,
    )


def _detalle(planes=None, estado="presentada", total=None):
    from app.esquemas.liquidacion import LiquidacionDetalleOut, PlanLiquidacionOut

    if planes is None:
        planes = [
            PlanLiquidacionOut(plan_id=1, plan_nombre="Plan Base", subtotal=Decimal("13000.00"),
                               items=[_item(1, "Ficticia, Ana", "10500.00"),
                                      _item(2, "Inventado, Beto", "2500.00", codigo="N-001")]),
            PlanLiquidacionOut(plan_id=2, plan_nombre="Plan Plus", subtotal=Decimal("0.00"),
                               items=[_item(3, "Ficticia, Ana", "0.00", revision=True,
                                            codigo="N-002", desc="Limpieza")]),
        ]
    total = Decimal(total) if total is not None else sum((p.subtotal for p in planes), Decimal("0"))
    return LiquidacionDetalleOut(
        id=7, os_id=1, obra_social="OS Ficticia Demo", periodo=date(2026, 10, 1), estado=estado,
        total=total, cantidad_items=sum(len(p.items) for p in planes),
        cantidad_revision=sum(1 for p in planes for i in p.items if i.revision), creada_por=1,
        presentada_at=None, cobrada_at=None, cobro_revertido_at=None,
        created_at=datetime(2026, 10, 31, tzinfo=timezone.utc), planes=planes, revertida=False,
    )


def _parsear(contenido: bytes) -> list[list[str]]:
    texto = contenido.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(texto), delimiter=";"))


# --- 5.1 modelo de filas ---------------------------------------------------------------------

def test_informe_lleva_subtotales_por_plan_y_total_de_la_liquidacion():
    from app.servicios.liquidacion_export import construir_informe

    informe = construir_informe(_detalle())
    assert [(g.plan, g.subtotal) for g in informe.grupos] == [
        ("Plan Base", Decimal("13000.00")), ("Plan Plus", Decimal("0.00"))]
    assert informe.total == Decimal("13000.00")
    assert informe.obra_social == "OS Ficticia Demo" and informe.periodo == "2026-10"


def test_informe_columnas_no_incluyen_datos_clinicos():
    from app.servicios.liquidacion_export import COLUMNAS

    assert COLUMNAS == ("Plan", "Fecha", "Paciente", "Codigo", "Descripcion", "Cantidad",
                        "Monto", "Estado")
    prohibidas = {"pieza", "pieza_fdi", "cara", "hallazgo", "notas", "motivo"}
    assert not prohibidas & {c.lower() for c in COLUMNAS}


def test_informe_marca_las_filas_en_revision_como_no_liquidadas():
    from app.servicios.liquidacion_export import construir_informe

    informe = construir_informe(_detalle())
    estados = [f.estado for g in informe.grupos for f in g.filas]
    assert estados == ["liquidada", "liquidada", "NO LIQUIDADA (revision manual)"]


def test_informe_incluye_la_leyenda_de_datos_ficticios():
    from app.servicios.liquidacion_export import construir_informe

    assert "ficticios" in construir_informe(_detalle()).leyenda.lower()


# --- 5.2 CSV ----------------------------------------------------------------------------------

def test_csv_utf8_con_bom_y_separador_punto_y_coma():
    from app.servicios.liquidacion_export import a_csv, construir_informe

    contenido = a_csv(construir_informe(_detalle()))
    assert contenido.startswith(b"\xef\xbb\xbf")
    filas = _parsear(contenido)
    assert ["Obra social", "OS Ficticia Demo"] in filas
    assert ["Periodo", "2026-10"] in filas
    encabezado = next(f for f in filas if f and f[0] == "Plan")
    assert len(encabezado) == 8 and encabezado[2] == "Paciente"


def test_csv_suma_de_filas_y_total_coinciden_con_la_liquidacion():
    from app.servicios.liquidacion_export import a_csv, construir_informe

    detalle = _detalle()
    filas = _parsear(a_csv(construir_informe(detalle)))
    items = [f for f in filas if len(f) == 8 and f[1] == "2026-10-30"]
    assert sum(Decimal(f[6]) for f in items) == detalle.total
    total = next(f for f in filas if f and f[0] == "TOTAL")
    assert Decimal(total[6]) == detalle.total
    subtotales = {f[0]: Decimal(f[6]) for f in filas if f and f[0].startswith("Subtotal")}
    assert subtotales == {"Subtotal Plan Base": Decimal("13000.00"),
                          "Subtotal Plan Plus": Decimal("0.00")}


@pytest.mark.parametrize("peligroso", ["=1+1", "+cmd", "-10", "@SUMA(A1)", "\tTAB"])
def test_csv_neutraliza_formulas_en_el_nombre_del_paciente(peligroso):
    from app.esquemas.liquidacion import PlanLiquidacionOut
    from app.servicios.liquidacion_export import a_csv, construir_informe

    plan = PlanLiquidacionOut(plan_id=1, plan_nombre="Plan Base", subtotal=Decimal("100.00"),
                              items=[_item(1, peligroso, "100.00")])
    filas = _parsear(a_csv(construir_informe(_detalle([plan]))))
    fila = next(f for f in filas if len(f) == 8 and f[1] == "2026-10-30")
    assert fila[2] == "'" + peligroso
    assert not fila[2].startswith(("=", "+", "-", "@", "\t"))


def test_csv_no_altera_un_nombre_comun():
    from app.esquemas.liquidacion import PlanLiquidacionOut
    from app.servicios.liquidacion_export import a_csv, construir_informe

    plan = PlanLiquidacionOut(plan_id=1, plan_nombre="Plan Base", subtotal=Decimal("100.00"),
                              items=[_item(1, "Ñandú, José", "100.00")])
    filas = _parsear(a_csv(construir_informe(_detalle([plan]))))
    assert next(f for f in filas if len(f) == 8 and f[1] == "2026-10-30")[2] == "Ñandú, José"


# --- 5.3 PDF ----------------------------------------------------------------------------------

def test_pdf_valido_con_subtotales_y_total():
    from app.servicios.liquidacion_export import a_pdf, construir_informe

    pdf = a_pdf(construir_informe(_detalle()))
    assert pdf.startswith(b"%PDF") and pdf.rstrip().endswith(b"%%EOF")
    for esperado in (b"Plan Base", b"Plan Plus", b"13000.00", b"OS Ficticia Demo", b"TOTAL"):
        assert esperado in pdf, esperado


def test_pdf_cambia_con_el_contenido():
    from app.esquemas.liquidacion import PlanLiquidacionOut
    from app.servicios.liquidacion_export import a_pdf, construir_informe

    otro = PlanLiquidacionOut(plan_id=1, plan_nombre="Plan Unico", subtotal=Decimal("777.00"),
                              items=[_item(1, "Ficticia, Ana", "777.00")])
    pdf = a_pdf(construir_informe(_detalle([otro])))
    assert b"Plan Unico" in pdf and b"777.00" in pdf and b"Plan Base" not in pdf
