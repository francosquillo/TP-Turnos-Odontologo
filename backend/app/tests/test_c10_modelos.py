"""C-10 grupo 1: modelos de caja, recibo y movimiento de caja contra PG real (D-02, D-14, D-15, D-25).

Postgres real (nunca SQLite): CHECK, UNIQUE parciales y triggers solo se prueban ahí.
Datos ficticios.
"""
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c10_helpers import (  # noqa: E402
    clave_nueva, crear_caja, crear_cuenta, crear_recibo, sembrar_c10,
)
from db_utils import sesion_pg  # noqa: E402, F401

HOY = date(2026, 10, 31)
AYER = date(2026, 10, 30)
AHORA = datetime(2026, 10, 31, 15, 0, tzinfo=timezone.utc)


async def _rechaza(sesion, *entidades):
    sesion.add_all(entidades)
    with pytest.raises(IntegrityError):
        await sesion.flush()
    await sesion.rollback()


async def _rechaza_sql(sesion, sql, **params):
    with pytest.raises(IntegrityError):
        await sesion.execute(sa.text(sql), params)
    await sesion.rollback()


def _caja(m, **cambios):
    from app.modelos import Caja

    datos = {"fecha": HOY, "abierta_por": m.secretaria.id, "estado": "abierta"}
    datos.update(cambios)
    return Caja(**datos)


def _cerrada(m, **cambios):
    datos = {
        "estado": "cerrada", "total_sistema": Decimal("100.00"),
        "total_contado": Decimal("100.00"), "diferencia": Decimal("0.00"),
        "cerrada_por": m.secretaria.id, "cerrada_at": AHORA,
    }
    datos.update(cambios)
    return _caja(m, **datos)


# --- 1.2 caja --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_caja_fecha_duplicada_rechazada(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    await crear_caja(sesion_pg, m, HOY, estado="cerrada")
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _caja(m))


@pytest.mark.asyncio
async def test_caja_segunda_abierta_rechazada(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    await crear_caja(sesion_pg, m, AYER)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _caja(m))


@pytest.mark.asyncio
async def test_caja_abierta_mas_cerradas_aceptadas(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    await crear_caja(sesion_pg, m, AYER, estado="cerrada")
    await crear_caja(sesion_pg, m, date(2026, 10, 29), estado="cerrada")
    abierta = await crear_caja(sesion_pg, m, HOY)
    assert abierta.id is not None and abierta.estado == "abierta"


@pytest.mark.asyncio
async def test_caja_estado_desconocido_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _caja(m, estado="reabierta"))


@pytest.mark.asyncio
@pytest.mark.parametrize("faltante", [
    "total_sistema", "total_contado", "diferencia", "cerrada_por", "cerrada_at",
])
async def test_caja_cerrada_incompleta_rechazada(sesion_pg, faltante):
    m = await sembrar_c10(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _cerrada(m, **{faltante: None}))


@pytest.mark.asyncio
@pytest.mark.parametrize("campo,valor", [
    ("total_sistema", Decimal("0.00")), ("total_contado", Decimal("0.00")),
    ("diferencia", Decimal("0.00")), ("cerrada_at", AHORA),
])
async def test_caja_abierta_con_totales_rechazada(sesion_pg, campo, valor):
    m = await sembrar_c10(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _caja(m, **{campo: valor}))


@pytest.mark.asyncio
async def test_caja_diferencia_mal_calculada_rechazada(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _cerrada(
        m, total_contado=Decimal("90.00"), diferencia=Decimal("-5.00"),
        motivo_diferencia="faltante"))


@pytest.mark.asyncio
async def test_caja_diferencia_bien_calculada_con_motivo_aceptada(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    caja = _cerrada(m, total_contado=Decimal("90.00"), diferencia=Decimal("-10.00"),
                    motivo_diferencia="faltante")
    sesion_pg.add(caja)
    await sesion_pg.flush()
    assert caja.id is not None


@pytest.mark.asyncio
async def test_caja_diferencia_sin_motivo_rechazada(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _cerrada(
        m, total_contado=Decimal("90.00"), diferencia=Decimal("-10.00")))


@pytest.mark.asyncio
async def test_caja_total_sistema_negativo_con_reversiones_aceptado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    caja = _cerrada(m, total_sistema=Decimal("-50.00"), total_contado=Decimal("0.00"),
                    diferencia=Decimal("50.00"), motivo_diferencia="devolucion")
    sesion_pg.add(caja)
    await sesion_pg.flush()
    assert caja.total_sistema == Decimal("-50.00")


@pytest.mark.asyncio
async def test_caja_contado_negativo_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _cerrada(
        m, total_contado=Decimal("-1.00"), diferencia=Decimal("-101.00"),
        motivo_diferencia="x"))


# --- 1.3 recibo, contador y movimiento de caja ----------------------------------------

@pytest.mark.asyncio
async def test_recibo_numero_duplicado_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    await crear_recibo(sesion_pg, m, numero=7)
    await sesion_pg.commit()
    from app.modelos import Recibo

    await _rechaza(sesion_pg, Recibo(
        numero=7, paciente_id=m.ana.id, monto=Decimal("10.00"), medio="efectivo",
        emitido_por=m.secretaria.id, clave_idempotencia=clave_nueva()))


@pytest.mark.asyncio
async def test_recibo_clave_duplicada_rechazada(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    clave = clave_nueva()
    await crear_recibo(sesion_pg, m, clave=clave)
    await sesion_pg.commit()
    from app.modelos import Recibo

    await _rechaza(sesion_pg, Recibo(
        numero=999, paciente_id=m.ana.id, monto=Decimal("10.00"), medio="efectivo",
        emitido_por=m.secretaria.id, clave_idempotencia=clave))


@pytest.mark.asyncio
async def test_recibo_sin_clave_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    await sesion_pg.commit()
    from app.modelos import Recibo

    await _rechaza(sesion_pg, Recibo(
        numero=1, paciente_id=m.ana.id, monto=Decimal("10.00"), medio="efectivo",
        emitido_por=m.secretaria.id, clave_idempotencia=None))


@pytest.mark.asyncio
@pytest.mark.parametrize("clave", [
    "A1B2C3D4-E5F6-4A7B-8C9D-0E1F2A3B4C5D",       # mayúsculas
    "a1b2c3d4-e5f6-1a7b-8c9d-0e1f2a3b4c5d",       # UUID v1
    "a1b2c3d4-e5f6-4a7b-7c9d-0e1f2a3b4c5d",       # variante inválida
    "mi-clave-de-prueba",                          # texto libre
    "",                                            # vacío
])
async def test_recibo_clave_mal_formada_rechazada(sesion_pg, clave):
    m = await sembrar_c10(sesion_pg)
    await sesion_pg.commit()
    from app.modelos import Recibo

    await _rechaza(sesion_pg, Recibo(
        numero=1, paciente_id=m.ana.id, monto=Decimal("10.00"), medio="efectivo",
        emitido_por=m.secretaria.id, clave_idempotencia=clave))


@pytest.mark.asyncio
@pytest.mark.parametrize("monto", ["0.00", "-5.00"])
async def test_recibo_monto_no_positivo_rechazado(sesion_pg, monto):
    m = await sembrar_c10(sesion_pg)
    await sesion_pg.commit()
    from app.modelos import Recibo

    await _rechaza(sesion_pg, Recibo(
        numero=1, paciente_id=m.ana.id, monto=Decimal(monto), medio="efectivo",
        emitido_por=m.secretaria.id, clave_idempotencia=clave_nueva()))


@pytest.mark.asyncio
async def test_recibo_anulado_sin_motivo_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    await sesion_pg.commit()
    from app.modelos import Recibo

    await _rechaza(sesion_pg, Recibo(
        numero=1, paciente_id=m.ana.id, monto=Decimal("10.00"), medio="efectivo",
        emitido_por=m.secretaria.id, clave_idempotencia=clave_nueva(),
        anulado=True, motivo_anulacion=None, anulado_por=m.admin.id, anulado_at=AHORA))


@pytest.mark.asyncio
async def test_recibo_con_motivo_pero_no_anulado_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    await sesion_pg.commit()
    from app.modelos import Recibo

    await _rechaza(sesion_pg, Recibo(
        numero=1, paciente_id=m.ana.id, monto=Decimal("10.00"), medio="efectivo",
        emitido_por=m.secretaria.id, clave_idempotencia=clave_nueva(),
        anulado=False, motivo_anulacion="x"))


@pytest.mark.asyncio
@pytest.mark.parametrize("medio", ["efectivo", "transferencia", "tarjeta_simulada"])
async def test_medio_del_catalogo_aceptado(sesion_pg, medio):
    m = await sembrar_c10(sesion_pg)
    recibo = await crear_recibo(sesion_pg, m, medio=medio)
    assert recibo.medio == medio


@pytest.mark.asyncio
@pytest.mark.parametrize("tabla", ["recibo", "movimiento_caja"])
@pytest.mark.parametrize("medio", ["tarjeta", "mercadopago"])
async def test_medio_fuera_de_catalogo_rechazado(sesion_pg, tabla, medio):
    from app.modelos import MovimientoCaja, Recibo

    m = await sembrar_c10(sesion_pg)
    caja = await crear_caja(sesion_pg, m, HOY)
    recibo = await crear_recibo(sesion_pg, m)
    await sesion_pg.commit()
    if tabla == "recibo":
        entidad = Recibo(
            numero=999, paciente_id=m.ana.id, monto=Decimal("10.00"), medio=medio,
            emitido_por=m.secretaria.id, clave_idempotencia=clave_nueva())
    else:
        entidad = MovimientoCaja(
            caja_id=caja.id, recibo_id=recibo.id, medio=medio, monto=Decimal("10.00"),
            creado_por=m.secretaria.id)
    await _rechaza(sesion_pg, entidad)


def _movcaja(caja, recibo, m, **cambios):
    from app.modelos import MovimientoCaja

    datos = {"caja_id": caja.id, "recibo_id": recibo.id, "medio": "efectivo",
             "monto": Decimal("100.00"), "creado_por": m.secretaria.id}
    datos.update(cambios)
    return MovimientoCaja(**datos)


@pytest.mark.asyncio
async def test_movcaja_monto_cero_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    caja = await crear_caja(sesion_pg, m, HOY)
    recibo = await crear_recibo(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _movcaja(caja, recibo, m, monto=Decimal("0.00")))


@pytest.mark.asyncio
async def test_movcaja_sin_recibo_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    caja = await crear_caja(sesion_pg, m, HOY)
    recibo = await crear_recibo(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _movcaja(caja, recibo, m, recibo_id=None))


@pytest.mark.asyncio
async def test_movcaja_reversion_sin_motivo_rechazada(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    caja = await crear_caja(sesion_pg, m, HOY)
    recibo = await crear_recibo(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _movcaja(caja, recibo, m, monto=Decimal("-100.00")))


@pytest.mark.asyncio
async def test_movcaja_ingreso_y_reversion_con_motivo_aceptados(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    caja = await crear_caja(sesion_pg, m, HOY)
    recibo = await crear_recibo(sesion_pg, m)
    sesion_pg.add_all([
        _movcaja(caja, recibo, m),
        _movcaja(caja, recibo, m, monto=Decimal("-100.00"), motivo="error de carga"),
    ])
    await sesion_pg.flush()


@pytest.mark.asyncio
async def test_movcaja_segundo_ingreso_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    caja = await crear_caja(sesion_pg, m, HOY)
    recibo = await crear_recibo(sesion_pg, m)
    sesion_pg.add(_movcaja(caja, recibo, m))
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _movcaja(caja, recibo, m, monto=Decimal("5.00")))


@pytest.mark.asyncio
async def test_movcaja_segunda_reversion_rechazada(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    caja = await crear_caja(sesion_pg, m, HOY)
    recibo = await crear_recibo(sesion_pg, m)
    sesion_pg.add(_movcaja(caja, recibo, m, monto=Decimal("-100.00"), motivo="a"))
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _movcaja(caja, recibo, m, monto=Decimal("-5.00"), motivo="b"))


@pytest.mark.asyncio
async def test_contador_id_distinto_de_1_rechazado(sesion_pg):
    from app.modelos import ReciboContador

    await sesion_pg.commit()
    await _rechaza(sesion_pg, ReciboContador(id=2, ultimo=1))


@pytest.mark.asyncio
async def test_contador_id_1_aceptado(sesion_pg):
    from app.modelos import ReciboContador

    contador = ReciboContador(id=1, ultimo=1)
    sesion_pg.add(contador)
    await sesion_pg.flush()
    assert contador.ultimo == 1


# --- 1.4 triggers -------------------------------------------------------------------------

async def _con_movcaja(sesion, m, caja_estado="abierta"):
    caja = await crear_caja(sesion, m, HOY, estado=caja_estado) if caja_estado != "cerrada_despues" \
        else await crear_caja(sesion, m, HOY)
    recibo = await crear_recibo(sesion, m)
    mov = _movcaja(caja, recibo, m)
    sesion.add(mov)
    await sesion.flush()
    return caja, recibo, mov


@pytest.mark.asyncio
async def test_movcaja_update_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    _, _, mov = await _con_movcaja(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza_sql(sesion_pg, "UPDATE movimiento_caja SET monto = 1.00 WHERE id = :i", i=mov.id)


@pytest.mark.asyncio
async def test_movcaja_delete_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    _, _, mov = await _con_movcaja(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza_sql(sesion_pg, "DELETE FROM movimiento_caja WHERE id = :i", i=mov.id)
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM movimiento_caja")) == 1


@pytest.mark.asyncio
async def test_movcaja_insert_en_caja_cerrada_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    caja = await crear_caja(sesion_pg, m, AYER, estado="cerrada")
    recibo = await crear_recibo(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _movcaja(caja, recibo, m))


@pytest.mark.asyncio
async def test_movcaja_insert_en_caja_abierta_aceptado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    _, _, mov = await _con_movcaja(sesion_pg, m)
    assert mov.id is not None and mov.created_at is not None


@pytest.mark.asyncio
async def test_caja_delete_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    abierta = await crear_caja(sesion_pg, m, HOY)
    cerrada = await crear_caja(sesion_pg, m, AYER, estado="cerrada")
    await sesion_pg.commit()
    id_abierta, id_cerrada = abierta.id, cerrada.id
    await _rechaza_sql(sesion_pg, "DELETE FROM caja WHERE id = :i", i=id_abierta)
    await _rechaza_sql(sesion_pg, "DELETE FROM caja WHERE id = :i", i=id_cerrada)
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM caja")) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("sql", [
    "UPDATE caja SET estado = 'abierta', total_sistema = NULL, total_contado = NULL, "
    "diferencia = NULL, cerrada_por = NULL, cerrada_at = NULL WHERE id = :i",
    "UPDATE caja SET total_contado = 1.00, diferencia = 1.00 - total_sistema, "
    "motivo_diferencia = 'x' WHERE id = :i",
])
async def test_caja_cerrada_update_rechazado(sesion_pg, sql):
    m = await sembrar_c10(sesion_pg)
    cerrada = await crear_caja(sesion_pg, m, AYER, estado="cerrada")
    await sesion_pg.commit()
    await _rechaza_sql(sesion_pg, sql, i=cerrada.id)


@pytest.mark.asyncio
async def test_caja_abierta_cierre_permitido(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    abierta = await crear_caja(sesion_pg, m, HOY)
    await sesion_pg.commit()
    await sesion_pg.execute(sa.text(
        "UPDATE caja SET estado = 'cerrada', total_sistema = 0, total_contado = 0, "
        "diferencia = 0, cerrada_por = :u, cerrada_at = now() WHERE id = :i"),
        {"u": m.secretaria.id, "i": abierta.id})
    estado = await sesion_pg.scalar(sa.text("SELECT estado FROM caja WHERE id = :i"), {"i": abierta.id})
    assert estado == "cerrada"


@pytest.mark.asyncio
async def test_recibo_delete_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    recibo = await crear_recibo(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza_sql(sesion_pg, "DELETE FROM recibo WHERE id = :i", i=recibo.id)
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM recibo")) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("asignacion", [
    "monto = 1.00", "medio = 'transferencia'", "numero = 999", "paciente_id = :otro",
    "emitido_por = :otro", "clave_idempotencia = 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d'",
])
async def test_recibo_update_campo_protegido_rechazado(sesion_pg, asignacion):
    m = await sembrar_c10(sesion_pg)
    recibo = await crear_recibo(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza_sql(
        sesion_pg, f"UPDATE recibo SET {asignacion} WHERE id = :i", i=recibo.id, otro=m.admin.id
        if "emitido_por" in asignacion else m.beto.id)


@pytest.mark.asyncio
async def test_recibo_anular_con_cambio_de_numero_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    recibo = await crear_recibo(sesion_pg, m, numero=5)
    await sesion_pg.commit()
    await _rechaza_sql(
        sesion_pg,
        "UPDATE recibo SET anulado = true, motivo_anulacion = 'x', anulado_por = :u, "
        "anulado_at = now(), numero = 6 WHERE id = :i", i=recibo.id, u=m.admin.id)


@pytest.mark.asyncio
async def test_recibo_desanular_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    recibo = await crear_recibo(
        sesion_pg, m, anulado=True, motivo_anulacion="error", anulado_por=m.admin.id,
        anulado_at=AHORA)
    await sesion_pg.commit()
    await _rechaza_sql(
        sesion_pg,
        "UPDATE recibo SET anulado = false, motivo_anulacion = NULL, anulado_por = NULL, "
        "anulado_at = NULL WHERE id = :i", i=recibo.id)


@pytest.mark.asyncio
async def test_recibo_anulado_no_admite_otro_cambio_de_motivo(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    recibo = await crear_recibo(
        sesion_pg, m, anulado=True, motivo_anulacion="error", anulado_por=m.admin.id,
        anulado_at=AHORA)
    await sesion_pg.commit()
    await _rechaza_sql(
        sesion_pg, "UPDATE recibo SET motivo_anulacion = 'otro' WHERE id = :i", i=recibo.id)


@pytest.mark.asyncio
async def test_recibo_anulacion_valida_permitida(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    recibo = await crear_recibo(sesion_pg, m, numero=5)
    await sesion_pg.commit()
    await sesion_pg.execute(sa.text(
        "UPDATE recibo SET anulado = true, motivo_anulacion = 'error', anulado_por = :u, "
        "anulado_at = now() WHERE id = :i"), {"u": m.admin.id, "i": recibo.id})
    fila = (await sesion_pg.execute(sa.text(
        "SELECT anulado, numero, monto FROM recibo WHERE id = :i"), {"i": recibo.id})).one()
    assert fila == (True, 5, Decimal("100.00"))


# --- 1.5 movimiento: recibo obligatorio en el pago -----------------------------------------

def _mov(cuenta, m, **cambios):
    from app.modelos import Movimiento

    datos = {"cc_id": cuenta.id, "tipo": "pago", "monto": Decimal("-50.00"),
             "concepto": "Recibo", "creado_por": m.secretaria.id}
    datos.update(cambios)
    return Movimiento(**datos)


@pytest.mark.asyncio
async def test_movimiento_recibo_inexistente_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    cuenta = await crear_cuenta(sesion_pg, m.ana)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _mov(cuenta, m, recibo_id=987654))


@pytest.mark.asyncio
async def test_movimiento_pago_sin_recibo_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    cuenta = await crear_cuenta(sesion_pg, m.ana)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _mov(cuenta, m, recibo_id=None))


@pytest.mark.asyncio
async def test_movimiento_segundo_pago_mismo_recibo_rechazado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    cuenta = await crear_cuenta(sesion_pg, m.ana)
    recibo = await crear_recibo(sesion_pg, m)
    sesion_pg.add(_mov(cuenta, m, recibo_id=recibo.id))
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _mov(cuenta, m, recibo_id=recibo.id))


@pytest.mark.asyncio
async def test_movimiento_pago_con_recibo_y_ajuste_con_el_mismo_recibo_aceptados(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    cuenta = await crear_cuenta(sesion_pg, m.ana)
    recibo = await crear_recibo(sesion_pg, m)
    pago = _mov(cuenta, m, recibo_id=recibo.id)
    sesion_pg.add(pago)
    await sesion_pg.flush()
    sesion_pg.add(_mov(
        cuenta, m, tipo="ajuste", monto=Decimal("50.00"), recibo_id=recibo.id,
        anula_a_id=pago.id, motivo="error"))
    await sesion_pg.flush()


@pytest.mark.asyncio
async def test_movimiento_cargo_sin_recibo_sigue_aceptado(sesion_pg):
    m = await sembrar_c10(sesion_pg)
    cuenta = await crear_cuenta(sesion_pg, m.ana)
    sesion_pg.add(_mov(cuenta, m, tipo="cargo", monto=Decimal("10.00")))
    await sesion_pg.flush()
