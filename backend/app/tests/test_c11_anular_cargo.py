"""C-11 task 3.5: anular un cargo con cobertura (D-06) contra PG real.

La anulación revierte también el `ajuste` de cobertura en la misma transacción; con un ítem
en cualquier liquidación responde 409 y no crea nada. Datos ficticios.
"""
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c11_helpers import asignar_plan, sembrar_c11  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

AHORA = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


async def _aceptado_con_cobertura(sesion, plan_attr="plan_base"):
    from app.esquemas.presupuesto import ItemIn
    from app.servicios import clinica_servicio as cs
    from app.servicios import presupuesto_servicio as ps

    m = await sembrar_c11(sesion)
    await asignar_plan(sesion, m.ana, getattr(m, plan_attr))
    repos = ps.PresupuestoRepos.de_sesion(sesion)
    odo = cs.Actor(usuario_id=m.odo_a.id, rol="odontologo", profesional_id=m.prof_a.id)
    admin = cs.Actor(usuario_id=m.admin.id, rol="admin", profesional_id=None)
    p = await ps.crear(repos, odo, m.ana.id, [
        ItemIn(hallazgo_id=m.h1.id, tratamiento_id=m.trat["OBT-001"].id, cantidad=1)], AHORA)
    await ps.presentar(repos, odo, p.id, AHORA)
    p = await ps.aceptar(repos, odo, p.id, AHORA)
    cargo = await sesion.scalar(sa.text(
        "SELECT id FROM movimiento WHERE presupuesto_id = :p AND tipo = 'cargo'"), {"p": p.id})
    return repos, m, admin, p, cargo


async def _anular(repos, m, admin, cargo_id, motivo="error de carga"):
    from app.servicios import cuenta_servicio as cu

    return await cu.anular_cargo(repos, admin, m.ana.id, cargo_id, motivo)


async def _saldo(repos, m):
    cuenta = await repos.cuentas.por_paciente(m.ana.id)
    return await repos.cuentas.saldo(cuenta.id)


@pytest.mark.asyncio
async def test_anular_cargo_con_cobertura_revierte_tambien_el_ajuste_y_saldo_cero(sesion_pg):
    repos, m, admin, p, cargo = await _aceptado_con_cobertura(sesion_pg)
    assert await _saldo(repos, m) == Decimal("4500.00")
    await _anular(repos, m, admin, cargo)
    filas = (await sesion_pg.execute(sa.text(
        "SELECT tipo, monto, anula_a_id IS NOT NULL FROM movimiento "
        "WHERE presupuesto_id = :p ORDER BY id"), {"p": p.id})).all()
    assert [(t, mo) for t, mo, _ in filas] == [
        ("cargo", Decimal("15000.00")), ("ajuste", Decimal("-10500.00")),
        ("ajuste", Decimal("-15000.00")), ("ajuste", Decimal("10500.00"))]
    assert await _saldo(repos, m) == Decimal("0.00")


@pytest.mark.asyncio
async def test_anular_cargo_con_cobertura_y_pagos_deja_saldo_a_favor_correcto(sesion_pg):
    from c10_helpers import cobro_in
    from app.servicios import caja_servicio as cs

    repos, m, admin, p, cargo = await _aceptado_con_cobertura(sesion_pg)
    sec = cs.Actor(usuario_id=m.secretaria.id, rol="secretaria", profesional_id=None)
    await cs.cobrar(cs.CajaRepos.de_sesion(sesion_pg), sec, cobro_in(p, "1000.00"))
    await _anular(repos, m, admin, cargo)
    # Pagó 1000.00 y todo lo demás se revirtió: el saldo es a su favor por lo pagado.
    assert await _saldo(repos, m) == Decimal("-1000.00")


@pytest.mark.asyncio
async def test_anular_cargo_con_cobertura_crea_exactamente_dos_contramovimientos(sesion_pg):
    repos, m, admin, p, cargo = await _aceptado_con_cobertura(sesion_pg)
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM movimiento")) == 2
    await _anular(repos, m, admin, cargo)
    assert await sesion_pg.scalar(sa.text(
        "SELECT count(*) FROM movimiento WHERE anula_a_id IS NOT NULL")) == 2


@pytest.mark.asyncio
async def test_anular_cargo_con_item_liquidado_409_sin_filas(sesion_pg):
    from app.modelos import ItemLiquidacion, Liquidacion
    from app.servicios import cuenta_servicio as cu

    repos, m, admin, p, cargo = await _aceptado_con_cobertura(sesion_pg)
    item_id, ar_id = (await sesion_pg.execute(sa.text(
        "SELECT id, arancel_id FROM item_presupuesto WHERE presupuesto_id = :p"),
        {"p": p.id})).one()
    liq = Liquidacion(os_id=m.os.id, periodo=date(2026, 10, 1), creada_por=m.admin.id)
    sesion_pg.add(liq)
    await sesion_pg.flush()
    sesion_pg.add(ItemLiquidacion(
        liquidacion_id=liq.id, item_presupuesto_id=item_id, plan_id=m.plan_base.id,
        arancel_id=ar_id, fecha_prestacion=date(2026, 10, 30), monto=Decimal("10500.00")))
    await sesion_pg.flush()
    antes = await sesion_pg.scalar(sa.text("SELECT count(*) FROM movimiento"))
    with pytest.raises(cu.ConflictoError):
        await _anular(repos, m, admin, cargo)
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM movimiento")) == antes


@pytest.mark.asyncio
async def test_anular_cargo_tras_descartar_el_borrador_es_posible(sesion_pg):
    from app.modelos import ItemLiquidacion, Liquidacion

    repos, m, admin, p, cargo = await _aceptado_con_cobertura(sesion_pg)
    item_id, ar_id = (await sesion_pg.execute(sa.text(
        "SELECT id, arancel_id FROM item_presupuesto WHERE presupuesto_id = :p"),
        {"p": p.id})).one()
    liq = Liquidacion(os_id=m.os.id, periodo=date(2026, 10, 1), creada_por=m.admin.id)
    sesion_pg.add(liq)
    await sesion_pg.flush()
    fila = ItemLiquidacion(
        liquidacion_id=liq.id, item_presupuesto_id=item_id, plan_id=m.plan_base.id,
        arancel_id=ar_id, fecha_prestacion=date(2026, 10, 30), monto=Decimal("10500.00"))
    sesion_pg.add(fila)
    await sesion_pg.flush()
    await sesion_pg.delete(fila)
    await sesion_pg.delete(liq)
    await sesion_pg.flush()
    anulacion = await _anular(repos, m, admin, cargo)
    assert anulacion.monto == Decimal("-15000.00")
