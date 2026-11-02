"""C-11 grupo 1: modelos de obra social, arancel, liquidación y caja contra PG real.

Postgres real (nunca SQLite): EXCLUDE/GiST, CHECK y UNIQUE parciales solo se prueban ahí.
Cubre tasks 1.2 a 1.6. Datos ficticios.
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

from c10_helpers import crear_caja, crear_cuenta, crear_presupuesto_aceptado, crear_recibo  # noqa: E402
from c11_helpers import crear_arancel, crear_os, crear_plan, sembrar_c11  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

HOY = date(2026, 10, 31)
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


# --- 1.2 obra social, plan y arancel ---------------------------------------------------------

@pytest.mark.asyncio
async def test_arancel_superpuesto_mismo_plan_y_codigo_rechazado(sesion_pg):
    from app.modelos import Arancel

    m = await sembrar_c11(sesion_pg)
    await crear_arancel(sesion_pg, m.plan_plus, "N-009", "100.00",
                        desde=date(2026, 1, 1), hasta=date(2026, 6, 30))
    await sesion_pg.commit()
    await _rechaza(sesion_pg, Arancel(
        plan_id=m.plan_plus.id, codigo_nomenclador="N-009", descripcion="x",
        precio=Decimal("120.00"), vigencia_desde=date(2026, 6, 30)))


@pytest.mark.asyncio
async def test_arancel_vigencias_contiguas_conviven(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    await crear_arancel(sesion_pg, m.plan_plus, "N-009", "100.00",
                        desde=date(2026, 1, 1), hasta=date(2026, 9, 30))
    await crear_arancel(sesion_pg, m.plan_plus, "N-009", "130.00", desde=date(2026, 10, 1))
    # Otro plan o otro código no chocan con el rango abierto.
    await crear_arancel(sesion_pg, m.plan_base, "N-009", "130.00", desde=date(2026, 10, 1))
    await crear_arancel(sesion_pg, m.plan_plus, "N-010", "130.00", desde=date(2026, 10, 1))


@pytest.mark.asyncio
async def test_arancel_rango_abierto_choca_con_cualquier_fecha_posterior(sesion_pg):
    from app.modelos import Arancel

    m = await sembrar_c11(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, Arancel(
        plan_id=m.plan_base.id, codigo_nomenclador="N-003", descripcion="x",
        precio=Decimal("1.00"), vigencia_desde=date(2030, 1, 1)))


@pytest.mark.asyncio
@pytest.mark.parametrize("precio", ["0.00", "-5.00"])
async def test_arancel_precio_no_positivo_rechazado(sesion_pg, precio):
    from app.modelos import Arancel

    m = await sembrar_c11(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, Arancel(
        plan_id=m.plan_plus.id, codigo_nomenclador="N-777", descripcion="x",
        precio=Decimal(precio), vigencia_desde=date(2026, 1, 1)))


@pytest.mark.asyncio
async def test_arancel_vigencia_hasta_anterior_a_desde_rechazada(sesion_pg):
    from app.modelos import Arancel

    m = await sembrar_c11(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, Arancel(
        plan_id=m.plan_plus.id, codigo_nomenclador="N-777", descripcion="x",
        precio=Decimal("1.00"), vigencia_desde=date(2026, 5, 2),
        vigencia_hasta=date(2026, 5, 1)))


@pytest.mark.asyncio
async def test_plan_nombre_unico_por_obra_social(sesion_pg):
    from app.modelos import Plan

    m = await sembrar_c11(sesion_pg)
    otra = await crear_os(sesion_pg, "Otra OS")
    await crear_plan(sesion_pg, otra, "Plan Base")  # mismo nombre, otra OS: válido
    await sesion_pg.commit()
    await _rechaza(sesion_pg, Plan(obra_social_id=m.os.id, nombre="Plan Base"))


# --- 1.3 columnas nuevas --------------------------------------------------------------------

@pytest.mark.asyncio
async def test_columnas_de_cobertura_nulas_por_defecto(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    p, _ = await crear_presupuesto_aceptado(sesion_pg, m)
    await sesion_pg.refresh(m.ana)
    assert m.ana.plan_id is None and p.plan_id is None


@pytest.mark.asyncio
async def test_plan_con_pacientes_no_se_borra_fk_restrict(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    m.ana.plan_id = m.plan_base.id
    await sesion_pg.commit()
    await _rechaza_sql(sesion_pg, "DELETE FROM plan WHERE id = :i", i=m.plan_base.id)


# --- 1.4 liquidación -------------------------------------------------------------------------

async def _item(sesion, m):
    from app.modelos import ItemPresupuesto

    p, _ = await crear_presupuesto_aceptado(sesion, m)
    item = ItemPresupuesto(
        presupuesto_id=p.id, hallazgo_id=m.h1.id, tratamiento_id=m.trat["OBT-001"].id,
        cantidad=1, precio=Decimal("15000.00"),
    )
    sesion.add(item)
    await sesion.flush()
    return item


def _liq(m, **cambios):
    from app.modelos import Liquidacion

    datos = {"os_id": m.os.id, "periodo": date(2026, 10, 1), "creada_por": m.admin.id}
    datos.update(cambios)
    return Liquidacion(**datos)


@pytest.mark.asyncio
async def test_liquidacion_periodo_con_dia_distinto_de_uno_rechazado(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _liq(m, periodo=date(2026, 10, 15)))


@pytest.mark.asyncio
async def test_liquidacion_estado_fuera_de_catalogo_rechazado(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _liq(m, estado="anulada"))


@pytest.mark.asyncio
async def test_item_liquidacion_prestacion_unica(sesion_pg):
    from app.modelos import ItemLiquidacion

    m = await sembrar_c11(sesion_pg)
    item = await _item(sesion_pg, m)
    liq1, liq2 = _liq(m), _liq(m)
    sesion_pg.add_all([liq1, liq2])
    await sesion_pg.flush()

    def fila(liq):
        return ItemLiquidacion(
            liquidacion_id=liq.id, item_presupuesto_id=item.id, plan_id=m.plan_base.id,
            arancel_id=m.ar_obt.id, fecha_prestacion=HOY, monto=Decimal("10500.00"))

    sesion_pg.add(fila(liq1))
    await sesion_pg.commit()
    await _rechaza(sesion_pg, fila(liq2))


@pytest.mark.asyncio
async def test_item_liquidacion_sin_arancel_exige_monto_cero(sesion_pg):
    from app.modelos import ItemLiquidacion

    m = await sembrar_c11(sesion_pg)
    item = await _item(sesion_pg, m)
    liq = _liq(m)
    sesion_pg.add(liq)
    await sesion_pg.flush()
    liq_id, item_id, plan_id = liq.id, item.id, m.plan_base.id
    await sesion_pg.commit()
    await _rechaza(sesion_pg, ItemLiquidacion(
        liquidacion_id=liq_id, item_presupuesto_id=item_id, plan_id=plan_id,
        arancel_id=None, fecha_prestacion=HOY, monto=Decimal("1.00")))
    sesion_pg.add(ItemLiquidacion(
        liquidacion_id=liq_id, item_presupuesto_id=item_id, plan_id=plan_id,
        arancel_id=None, fecha_prestacion=HOY, monto=Decimal("0.00")))
    await sesion_pg.flush()


# --- 1.5 movimiento_caja ---------------------------------------------------------------------

def _mov(caja_id, usuario_id, **datos):
    from app.modelos import MovimientoCaja

    base = {"caja_id": caja_id, "medio": "efectivo", "monto": Decimal("100.00"),
            "creado_por": usuario_id}
    base.update(datos)
    return MovimientoCaja(**base)


async def _liquidacion(sesion, m):
    liq = _liq(m)
    sesion.add(liq)
    await sesion.flush()
    return liq


@pytest.mark.asyncio
async def test_movcaja_sin_ninguna_referencia_rechazado(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    caja = await crear_caja(sesion_pg, m, HOY)
    caja_id, uid = caja.id, m.secretaria.id
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _mov(caja_id, uid))


@pytest.mark.asyncio
async def test_movcaja_con_las_dos_referencias_rechazado(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    caja = await crear_caja(sesion_pg, m, HOY)
    recibo = await crear_recibo(sesion_pg, m)
    liq = await _liquidacion(sesion_pg, m)
    caja_id, uid, rid, lid = caja.id, m.secretaria.id, recibo.id, liq.id
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _mov(caja_id, uid, recibo_id=rid, liquidacion_id=lid))


@pytest.mark.asyncio
async def test_movcaja_liquidacion_ingreso_y_reversion_unicos(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    caja = await crear_caja(sesion_pg, m, HOY)
    liq = await _liquidacion(sesion_pg, m)
    caja_id, uid, lid = caja.id, m.secretaria.id, liq.id
    sesion_pg.add_all([
        _mov(caja_id, uid, liquidacion_id=lid),
        _mov(caja_id, uid, liquidacion_id=lid, monto=Decimal("-100.00"), motivo="x"),
    ])
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _mov(caja_id, uid, liquidacion_id=lid))
    await _rechaza(sesion_pg, _mov(
        caja_id, uid, liquidacion_id=lid, monto=Decimal("-50.00"), motivo="otra"))


@pytest.mark.asyncio
async def test_movcaja_con_recibo_sigue_valido_y_inmutable(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    caja = await crear_caja(sesion_pg, m, HOY)
    recibo = await crear_recibo(sesion_pg, m)
    mov = _mov(caja.id, m.secretaria.id, recibo_id=recibo.id)
    sesion_pg.add(mov)
    await sesion_pg.flush()
    mov_id = mov.id
    await sesion_pg.commit()
    await _rechaza_sql(sesion_pg, "UPDATE movimiento_caja SET monto = 1 WHERE id = :i", i=mov_id)


# --- 1.6 ajuste de cobertura único -----------------------------------------------------------

@pytest.mark.asyncio
async def test_segundo_ajuste_de_cobertura_rechazado_y_contramovimiento_permitido(sesion_pg):
    from app.modelos import Movimiento

    m = await sembrar_c11(sesion_pg)
    p, cuenta = await crear_presupuesto_aceptado(sesion_pg, m, total="1000.00")

    def ajuste(monto, **extra):
        return Movimiento(
            cc_id=cuenta.id, tipo="ajuste", monto=Decimal(monto),
            concepto="Cobertura obra social", presupuesto_id=p.id,
            creado_por=m.admin.id, **extra)

    primero = ajuste("-700.00")
    sesion_pg.add(primero)
    await sesion_pg.flush()
    # El contramovimiento (positivo, con anula_a_id y motivo) no choca con el índice parcial.
    sesion_pg.add(ajuste("700.00", anula_a_id=primero.id, motivo="anulación"))
    await sesion_pg.flush()
    await sesion_pg.commit()
    await _rechaza(sesion_pg, ajuste("-100.00"))
