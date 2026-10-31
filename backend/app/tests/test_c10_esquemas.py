"""C-10 grupo 2: esquemas de caja y recibos (D-03, D-08, D-12, D-17, D-25). Sin DB.

Dinero viaja como texto con 2 decimales; la clave de idempotencia es un UUID v4 en
minúsculas, obligatoria en el cuerpo y nunca devuelta. Datos ficticios.
"""
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

CLAVE = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"


def _cobro(**cambios):
    datos = {"presupuesto_id": 1, "monto": "400.00", "medio": "efectivo",
             "clave_idempotencia": CLAVE}
    datos.update(cambios)
    return datos


def test_cobro_valido_conserva_el_monto_como_decimal():
    from app.esquemas.caja import CobroIn

    cobro = CobroIn(**_cobro())
    assert cobro.monto == Decimal("400.00") and cobro.medio == "efectivo"
    assert CobroIn(**_cobro(monto=400)).monto == Decimal("400")


def test_cobro_sin_clave_invalido():
    from app.esquemas.caja import CobroIn

    datos = _cobro()
    del datos["clave_idempotencia"]
    with pytest.raises(ValidationError):
        CobroIn(**datos)


@pytest.mark.parametrize("clave", [
    CLAVE.upper(),                                   # mayúsculas
    "a1b2c3d4-e5f6-1a7b-8c9d-0e1f2a3b4c5d",          # UUID v1
    "a1b2c3d4-e5f6-4a7b-7c9d-0e1f2a3b4c5d",          # variante inválida
    "mi clave", "", CLAVE + "x", " " + CLAVE,
])
def test_cobro_clave_mal_formada_invalida(clave):
    from app.esquemas.caja import CobroIn

    with pytest.raises(ValidationError):
        CobroIn(**_cobro(clave_idempotencia=clave))


def test_cobro_clave_uuid4_generado_valido():
    from app.esquemas.caja import CobroIn

    assert CobroIn(**_cobro(clave_idempotencia=str(uuid.uuid4())))


def test_cobro_salida_sin_clave():
    from app.esquemas.caja import CobroOut, ReciboOut

    assert "clave_idempotencia" not in CobroOut.model_fields
    assert "clave_idempotencia" not in ReciboOut.model_fields


@pytest.mark.parametrize("medio", ["tarjeta", "mercadopago", "", "EFECTIVO", None])
def test_cobro_medio_tarjeta_invalido(medio):
    from app.esquemas.caja import CobroIn

    with pytest.raises(ValidationError):
        CobroIn(**_cobro(medio=medio))


@pytest.mark.parametrize("medio", ["efectivo", "transferencia", "tarjeta_simulada"])
def test_cobro_medios_simulados_validos(medio):
    from app.esquemas.caja import CobroIn

    assert CobroIn(**_cobro(medio=medio)).medio == medio


@pytest.mark.parametrize("monto", ["0", "0.00", "-1.00", "10.001", "abc", "NaN", "Infinity", None])
def test_cobro_monto_invalido(monto):
    from app.esquemas.caja import CobroIn

    with pytest.raises(ValidationError):
        CobroIn(**_cobro(monto=monto))


@pytest.mark.parametrize("monto", ["0.01", "1", "400.5", "9999999999999.99"])
def test_cobro_monto_valido(monto):
    from app.esquemas.caja import CobroIn

    assert CobroIn(**_cobro(monto=monto)).monto == Decimal(monto)


def test_cobro_campo_fecha_invalido():
    from app.esquemas.caja import CobroIn

    with pytest.raises(ValidationError):
        CobroIn(**_cobro(fecha="2026-10-31"))


def test_cobro_campo_paciente_invalido():
    from app.esquemas.caja import CobroIn

    with pytest.raises(ValidationError):
        CobroIn(**_cobro(paciente_id=1))


def test_cierre_valido_con_y_sin_motivo():
    from app.esquemas.caja import CierreIn

    assert CierreIn(caja_id=1, total_contado="1500.00").motivo_diferencia is None
    cierre = CierreIn(caja_id=1, total_contado="1400.00", motivo_diferencia="faltante de caja chica")
    assert cierre.total_contado == Decimal("1400.00") and cierre.motivo_diferencia


def test_cierre_con_total_sistema_invalido():
    from app.esquemas.caja import CierreIn

    with pytest.raises(ValidationError):
        CierreIn(caja_id=1, total_contado="10.00", total_sistema="10.00")


def test_cierre_con_diferencia_invalida():
    from app.esquemas.caja import CierreIn

    with pytest.raises(ValidationError):
        CierreIn(caja_id=1, total_contado="10.00", diferencia="0.00")


@pytest.mark.parametrize("contado", ["-0.01", "-100", "10.001", "x"])
def test_cierre_contado_negativo_invalido(contado):
    from app.esquemas.caja import CierreIn

    with pytest.raises(ValidationError):
        CierreIn(caja_id=1, total_contado=contado)


def test_cierre_contado_cero_valido():
    from app.esquemas.caja import CierreIn

    assert CierreIn(caja_id=1, total_contado="0").total_contado == 0


def test_cierre_motivo_vacio_invalido():
    from app.esquemas.caja import CierreIn

    with pytest.raises(ValidationError):
        CierreIn(caja_id=1, total_contado="1.00", motivo_diferencia="   ")


@pytest.mark.parametrize("motivo", [None, "", "   "])
def test_anulacion_recibo_sin_motivo_invalida(motivo):
    from app.esquemas.caja import AnulacionReciboIn

    with pytest.raises(ValidationError):
        AnulacionReciboIn(motivo=motivo)


def test_anulacion_recibo_con_campo_extra_invalida():
    from app.esquemas.caja import AnulacionReciboIn

    with pytest.raises(ValidationError):
        AnulacionReciboIn(motivo="error de carga", numero=3)


def _recibo(**cambios):
    datos = dict(
        id=1, numero=7, paciente_id=3, paciente_nombre="Ana Ficticia", monto=Decimal("400"),
        medio="efectivo", fecha=date(2026, 10, 31), emitido_por=2,
        created_at=datetime(2026, 10, 31, 15, 0, tzinfo=timezone.utc), anulado=False,
        motivo_anulacion=None, anulado_por=None, anulado_at=None,
    )
    datos.update(cambios)
    return datos


def test_importe_serializa_como_texto():
    from app.esquemas.caja import CajaOut, ReciboOut

    recibo = ReciboOut(**_recibo()).model_dump(mode="json")
    assert recibo["monto"] == "400.00" and recibo["fecha"] == "2026-10-31"
    caja = CajaOut(
        id=1, fecha=date(2026, 10, 31), estado="cerrada", abierta_por=2,
        total_sistema=Decimal("1500"), total_contado=Decimal("1400"),
        diferencia=Decimal("-100"), motivo_diferencia="faltante", cerrada_por=2,
        cerrada_at=datetime(2026, 10, 31, 22, 0, tzinfo=timezone.utc),
    ).model_dump(mode="json")
    assert (caja["total_sistema"], caja["total_contado"], caja["diferencia"]) == (
        "1500.00", "1400.00", "-100.00")


def test_caja_abierta_serializa_totales_de_cierre_nulos():
    from app.esquemas.caja import CajaOut

    caja = CajaOut(
        id=1, fecha=date(2026, 10, 31), estado="abierta", abierta_por=2,
        total_sistema=Decimal("250.50"), total_contado=None, diferencia=None,
        motivo_diferencia=None, cerrada_por=None, cerrada_at=None,
    ).model_dump(mode="json")
    assert caja["total_sistema"] == "250.50"
    assert caja["total_contado"] is None and caja["diferencia"] is None


def test_estado_caja_bloqueo_solo_valores_del_catalogo():
    from app.esquemas.caja import EstadoCajaOut

    base = dict(fecha=date(2026, 10, 31), hoy=date(2026, 10, 31), operable=False,
                caja=None, desglose=[])
    assert EstadoCajaOut(**base, bloqueo="caja_pendiente").bloqueo == "caja_pendiente"
    assert EstadoCajaOut(**base, bloqueo="caja_cerrada").bloqueo == "caja_cerrada"
    assert EstadoCajaOut(**{**base, "operable": True}, bloqueo=None).bloqueo is None
    with pytest.raises(ValidationError):
        EstadoCajaOut(**base, bloqueo="otro")


def test_cobro_out_hereda_el_recibo_e_indica_el_presupuesto():
    from app.esquemas.caja import CobroOut

    salida = CobroOut(**_recibo(), presupuesto_id=12, presupuesto_estado="aceptado")
    assert salida.model_dump(mode="json")["presupuesto_id"] == 12


# --- 2.2 pendientes en la cuenta -------------------------------------------------------------

def test_cuenta_pendientes_por_defecto_vacio():
    from app.esquemas.cuenta import CuentaOut

    cuenta = CuentaOut(paciente_id=7, saldo=Decimal("0"), movimientos=[])
    assert cuenta.pendientes == []
    # Dos instancias no comparten la lista por defecto.
    otra = CuentaOut(paciente_id=8, saldo=Decimal("0"), movimientos=[])
    assert cuenta.pendientes is not otra.pendientes


def test_pendiente_serializa_como_texto():
    from app.esquemas.cuenta import CuentaOut, PendienteOut

    cuenta = CuentaOut(
        paciente_id=7, saldo=Decimal("600"), movimientos=[],
        pendientes=[PendienteOut(presupuesto_id=3, total=Decimal("1000"), pendiente=Decimal("600"))],
    ).model_dump(mode="json")
    assert cuenta["pendientes"] == [{"presupuesto_id": 3, "total": "1000.00", "pendiente": "600.00"}]


def test_pendiente_con_campo_extra_invalido():
    from app.esquemas.cuenta import PendienteOut

    with pytest.raises(ValidationError):
        PendienteOut(presupuesto_id=3, total=Decimal("1"), pendiente=Decimal("1"), estado="x")
