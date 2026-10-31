"""C-10 grupo 3: repos de recibo, caja y cuenta contra PG real (D-08, D-10, D-11, D-17, D-22, D-25).

Postgres real (nunca SQLite). Datos ficticios.
"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c10_helpers import (  # noqa: E402
    clave_nueva, crear_caja, crear_presupuesto_aceptado, crear_recibo, sembrar_c10,
)
from db_utils import sesion_pg  # noqa: E402, F401

HOY = date(2026, 10, 31)
AYER = date(2026, 10, 30)


# --- 3.1 recibo_repo ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_por_clave_encontrado(sesion_pg):
    from app.repos.recibo_repo import ReciboRepository

    m = await sembrar_c10(sesion_pg)
    clave = clave_nueva()
    recibo = await crear_recibo(sesion_pg, m, clave=clave)
    otro = await crear_recibo(sesion_pg, m)
    repo = ReciboRepository(sesion_pg)
    assert (await repo.por_clave(clave)).id == recibo.id
    assert (await repo.por_clave(otro.clave_idempotencia)).id == otro.id


@pytest.mark.asyncio
async def test_por_clave_inexistente_none(sesion_pg):
    from app.repos.recibo_repo import ReciboRepository

    m = await sembrar_c10(sesion_pg)
    await crear_recibo(sesion_pg, m)
    assert await ReciboRepository(sesion_pg).por_clave(clave_nueva()) is None


@pytest.mark.asyncio
async def test_siguiente_numero_empieza_en_1(sesion_pg):
    from app.repos.recibo_repo import ReciboRepository

    await sembrar_c10(sesion_pg)
    assert await ReciboRepository(sesion_pg).siguiente_numero() == 1


@pytest.mark.asyncio
async def test_siguiente_numero_consecutivo(sesion_pg):
    from app.repos.recibo_repo import ReciboRepository

    await sembrar_c10(sesion_pg)
    repo = ReciboRepository(sesion_pg)
    assert [await repo.siguiente_numero() for _ in range(4)] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_siguiente_numero_rollback_lo_devuelve(sesion_pg):
    from app.repos.recibo_repo import ReciboRepository

    await sembrar_c10(sesion_pg)
    await sesion_pg.commit()
    repo = ReciboRepository(sesion_pg)
    assert await repo.siguiente_numero() == 1
    await sesion_pg.commit()
    assert await repo.siguiente_numero() == 2
    await sesion_pg.rollback()
    assert await repo.siguiente_numero() == 2


async def _con_ingreso(sesion, m, caja, **recibo):
    from app.modelos import MovimientoCaja

    r = await crear_recibo(sesion, m, **recibo)
    sesion.add(MovimientoCaja(
        caja_id=caja.id, recibo_id=r.id, medio=r.medio, monto=r.monto,
        creado_por=m.secretaria.id))
    await sesion.flush()
    return r


@pytest.mark.asyncio
async def test_listar_por_fecha_mayor_a_menor(sesion_pg):
    from app.repos.recibo_repo import ReciboRepository

    m = await sembrar_c10(sesion_pg)
    caja_hoy = await crear_caja(sesion_pg, m, HOY)
    caja_ayer = await crear_caja(sesion_pg, m, AYER, estado="cerrada")
    # Solo hoy tiene ingresos (a una caja cerrada no se le pueden insertar): ayer queda vacío.
    r1 = await _con_ingreso(sesion_pg, m, caja_hoy, numero=1)
    r2 = await _con_ingreso(sesion_pg, m, caja_hoy, numero=2, paciente=m.beto)
    r3 = await _con_ingreso(sesion_pg, m, caja_hoy, numero=3)
    repo = ReciboRepository(sesion_pg)
    filas = await repo.listar_por_fecha(HOY)
    assert [f.recibo.numero for f in filas] == [3, 2, 1]
    assert [f.recibo.id for f in filas] == [r3.id, r2.id, r1.id]
    assert filas[1].paciente_nombre == "Beto Inventado" and filas[0].paciente_nombre == "Ana Ficticia"
    assert all(f.fecha == HOY for f in filas)
    assert await repo.listar_por_fecha(caja_ayer.fecha) == []


@pytest.mark.asyncio
async def test_listar_recibo_anulado_otro_dia_queda_en_su_fecha(sesion_pg):
    from app.modelos import MovimientoCaja
    from app.repos.recibo_repo import ReciboRepository

    m = await sembrar_c10(sesion_pg)
    caja_hoy = await crear_caja(sesion_pg, m, HOY)
    r = await _con_ingreso(sesion_pg, m, caja_hoy, numero=1)
    # La reversión cae en otra fecha: el recibo sigue listado en la de su ingreso.
    sesion_pg.add(MovimientoCaja(
        caja_id=caja_hoy.id, recibo_id=r.id, medio=r.medio, monto=-r.monto,
        motivo="error", creado_por=m.admin.id))
    await sesion_pg.flush()
    repo = ReciboRepository(sesion_pg)
    assert [f.recibo.numero for f in await repo.listar_por_fecha(HOY)] == [1]
    assert await repo.listar_por_fecha(AYER) == []
    assert await repo.fecha_de(r.id) == HOY


# --- 3.2 caja_repo ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_asegurar_dos_veces_una_fila(sesion_pg):
    from app.repos.caja_repo import CajaRepository

    m = await sembrar_c10(sesion_pg)
    repo = CajaRepository(sesion_pg)
    await repo.asegurar(HOY, m.secretaria.id)
    await repo.asegurar(HOY, m.admin.id)
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM caja")) == 1
    caja = await repo.por_fecha_para_actualizar(HOY)
    assert caja.abierta_por == m.secretaria.id and caja.estado == "abierta"


@pytest.mark.asyncio
async def test_asegurar_con_otra_abierta_no_crea(sesion_pg):
    from app.repos.caja_repo import CajaRepository

    m = await sembrar_c10(sesion_pg)
    await crear_caja(sesion_pg, m, AYER)
    repo = CajaRepository(sesion_pg)
    await repo.asegurar(HOY, m.secretaria.id)
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM caja")) == 1
    assert await repo.por_fecha_para_actualizar(HOY) is None


@pytest.mark.asyncio
async def test_pendiente_anterior_encontrada(sesion_pg):
    from app.repos.caja_repo import CajaRepository

    m = await sembrar_c10(sesion_pg)
    ayer = await crear_caja(sesion_pg, m, AYER)
    pendiente = await CajaRepository(sesion_pg).pendiente_anterior(HOY)
    assert pendiente.id == ayer.id


@pytest.mark.asyncio
async def test_pendiente_ignora_hoy(sesion_pg):
    from app.repos.caja_repo import CajaRepository

    m = await sembrar_c10(sesion_pg)
    await crear_caja(sesion_pg, m, HOY)
    await crear_caja(sesion_pg, m, date(2026, 10, 29), estado="cerrada")
    assert await CajaRepository(sesion_pg).pendiente_anterior(HOY) is None


async def _ingreso(sesion, m, caja, monto, medio):
    from app.modelos import MovimientoCaja

    r = await crear_recibo(sesion, m, monto=monto, medio=medio)
    sesion.add(MovimientoCaja(
        caja_id=caja.id, recibo_id=r.id, medio=medio, monto=Decimal(monto),
        creado_por=m.secretaria.id))
    await sesion.flush()
    return r


@pytest.mark.asyncio
async def test_total_suma_ingresos_y_reversiones(sesion_pg):
    from app.modelos import MovimientoCaja
    from app.repos.caja_repo import CajaRepository

    m = await sembrar_c10(sesion_pg)
    caja = await crear_caja(sesion_pg, m, HOY)
    repo = CajaRepository(sesion_pg)
    assert await repo.total(caja.id) == Decimal("0")
    await _ingreso(sesion_pg, m, caja, "1000.00", "efectivo")
    r2 = await _ingreso(sesion_pg, m, caja, "500.50", "transferencia")
    assert await repo.total(caja.id) == Decimal("1500.50")
    sesion_pg.add(MovimientoCaja(
        caja_id=caja.id, recibo_id=r2.id, medio="transferencia", monto=Decimal("-500.50"),
        motivo="error", creado_por=m.admin.id))
    await sesion_pg.flush()
    assert await repo.total(caja.id) == Decimal("1000.00")


@pytest.mark.asyncio
async def test_desglose_por_medio(sesion_pg):
    from app.repos.caja_repo import CajaRepository

    m = await sembrar_c10(sesion_pg)
    caja = await crear_caja(sesion_pg, m, HOY)
    repo = CajaRepository(sesion_pg)
    assert await repo.desglose(caja.id) == {}
    await _ingreso(sesion_pg, m, caja, "100.00", "efectivo")
    await _ingreso(sesion_pg, m, caja, "250.00", "efectivo")
    await _ingreso(sesion_pg, m, caja, "40.00", "tarjeta_simulada")
    assert await repo.desglose(caja.id) == {
        "efectivo": Decimal("350.00"), "tarjeta_simulada": Decimal("40.00")}


# --- 3.3 cuenta_repo: pendientes -----------------------------------------------------------

async def _mov(sesion, m, cuenta, presupuesto, tipo, monto, **extra):
    from app.repos.cuenta_repo import CuentaRepository

    datos = {"tipo": tipo, "monto": Decimal(monto), "concepto": "x",
             "presupuesto_id": presupuesto.id, "creado_por": m.admin.id}
    datos.update(extra)
    return await CuentaRepository(sesion).crear_movimiento(cuenta.id, **datos)


async def _pago(sesion, m, cuenta, presupuesto, monto):
    recibo = await crear_recibo(sesion, m, monto=monto)
    pago = await _mov(sesion, m, cuenta, presupuesto, "pago", f"-{monto}", recibo_id=recibo.id)
    return recibo, pago


@pytest.mark.asyncio
async def test_pendiente_cargo_menos_pagos(sesion_pg):
    from app.repos.cuenta_repo import CuentaRepository

    m = await sembrar_c10(sesion_pg)
    p, cuenta = await crear_presupuesto_aceptado(sesion_pg, m, total="1000.00")
    repo = CuentaRepository(sesion_pg)
    assert await repo.pendiente_de_presupuesto(p.id) == Decimal("1000.00")
    await _pago(sesion_pg, m, cuenta, p, "400.00")
    assert await repo.pendiente_de_presupuesto(p.id) == Decimal("600.00")
    await _pago(sesion_pg, m, cuenta, p, "600.00")
    assert await repo.pendiente_de_presupuesto(p.id) == Decimal("0.00")


@pytest.mark.asyncio
async def test_pendiente_repone_pago_anulado(sesion_pg):
    from app.repos.cuenta_repo import CuentaRepository

    m = await sembrar_c10(sesion_pg)
    p, cuenta = await crear_presupuesto_aceptado(sesion_pg, m, total="1000.00")
    recibo, pago = await _pago(sesion_pg, m, cuenta, p, "400.00")
    await _mov(sesion_pg, m, cuenta, p, "ajuste", "400.00", anula_a_id=pago.id,
               recibo_id=recibo.id, motivo="error")
    assert await CuentaRepository(sesion_pg).pendiente_de_presupuesto(p.id) == Decimal("1000.00")


@pytest.mark.asyncio
async def test_pendiente_cero_con_cargo_anulado(sesion_pg):
    from app.repos.cuenta_repo import CuentaRepository

    m = await sembrar_c10(sesion_pg)
    p, cuenta = await crear_presupuesto_aceptado(sesion_pg, m, total="1000.00")
    cargo = await sesion_pg.scalar(sa.text("SELECT id FROM movimiento WHERE tipo = 'cargo'"))
    await _mov(sesion_pg, m, cuenta, p, "ajuste", "-1000.00", anula_a_id=cargo, motivo="error")
    repo = CuentaRepository(sesion_pg)
    assert await repo.pendiente_de_presupuesto(p.id) == Decimal("0.00")
    assert await repo.pendientes_de_paciente(m.ana.id) == []
    # Con un pago previo queda saldo a favor (negativo): tampoco es cobrable.
    p2, cuenta2 = await crear_presupuesto_aceptado(sesion_pg, m, total="1000.00", paciente=m.beto)
    await _pago(sesion_pg, m, cuenta2, p2, "400.00")
    cargo2 = await sesion_pg.scalar(sa.text(
        "SELECT id FROM movimiento WHERE tipo = 'cargo' AND presupuesto_id = :p"), {"p": p2.id})
    await _mov(sesion_pg, m, cuenta2, p2, "ajuste", "-1000.00", anula_a_id=cargo2, motivo="error")
    assert await repo.pendiente_de_presupuesto(p2.id) == Decimal("-400.00")
    assert await repo.pendientes_de_paciente(m.beto.id) == []


@pytest.mark.asyncio
async def test_pendientes_excluye_cobrado_y_saldo_no_positivo(sesion_pg):
    from app.repos.cuenta_repo import CuentaRepository

    m = await sembrar_c10(sesion_pg)
    parcial, cuenta = await crear_presupuesto_aceptado(sesion_pg, m, total="1000.00")
    await _pago(sesion_pg, m, cuenta, parcial, "400.00")
    saldado, _ = await crear_presupuesto_aceptado(sesion_pg, m, total="200.00")
    await _pago(sesion_pg, m, cuenta, saldado, "200.00")
    cobrado, _ = await crear_presupuesto_aceptado(sesion_pg, m, total="300.00", estado="cobrado")
    borrador, _ = await crear_presupuesto_aceptado(
        sesion_pg, m, total="50.00", estado="borrador", con_cargo=False)
    otro_paciente, _ = await crear_presupuesto_aceptado(sesion_pg, m, total="70.00", paciente=m.beto)
    filas = await CuentaRepository(sesion_pg).pendientes_de_paciente(m.ana.id)
    assert [(f.presupuesto_id, f.total, f.pendiente) for f in filas] == [
        (parcial.id, Decimal("1000.00"), Decimal("600.00"))]
    assert otro_paciente.id not in [f.presupuesto_id for f in filas]
    assert cobrado.id not in [f.presupuesto_id for f in filas]
    assert borrador.id not in [f.presupuesto_id for f in filas]


@pytest.mark.asyncio
async def test_pago_de_recibo_encontrado(sesion_pg):
    from app.repos.cuenta_repo import CuentaRepository

    m = await sembrar_c10(sesion_pg)
    p, cuenta = await crear_presupuesto_aceptado(sesion_pg, m, total="1000.00")
    recibo, pago = await _pago(sesion_pg, m, cuenta, p, "400.00")
    otro_recibo, otro_pago = await _pago(sesion_pg, m, cuenta, p, "100.00")
    repo = CuentaRepository(sesion_pg)
    assert (await repo.pago_de_recibo(recibo.id)).id == pago.id
    assert (await repo.pago_de_recibo(otro_recibo.id)).id == otro_pago.id
    assert await repo.pago_de_recibo(987654) is None
