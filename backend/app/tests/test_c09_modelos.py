"""C-09 grupo 1: modelos de presupuesto y cuenta corriente contra PG real (D-02, D-11, D-12).

Postgres real (nunca SQLite): CHECK, UNIQUE parciales y el trigger de
inmutabilidad solo se prueban ahí. Datos ficticios.
"""
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c09_helpers import sembrar_c09  # noqa: E402
from c10_helpers import crear_recibo  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401


async def _rechaza(sesion, *entidades):
    sesion.add_all(entidades)
    with pytest.raises(IntegrityError):
        await sesion.flush()
    await sesion.rollback()


def _presupuesto(m, **cambios):
    from app.modelos import Presupuesto

    datos = {"paciente_id": m.ana.id, "profesional_id": m.prof_a.id,
             "estado": "borrador", "total": Decimal("0.00")}
    datos.update(cambios)
    return Presupuesto(**datos)


async def _presupuesto_ok(sesion, m, **cambios):
    p = _presupuesto(m, **cambios)
    sesion.add(p)
    await sesion.flush()
    return p


def _item(p, m, **cambios):
    from app.modelos import ItemPresupuesto

    datos = {"presupuesto_id": p.id, "hallazgo_id": m.h1.id,
             "tratamiento_id": m.trat["CON-001"].id, "cantidad": 1,
             "precio": Decimal("1000.50")}
    datos.update(cambios)
    return ItemPresupuesto(**datos)


# --- 1.2 presupuesto e ítem ------------------------------------------------------------

@pytest.mark.asyncio
async def test_presupuesto_estado_desconocido_rechazado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _presupuesto(m, estado="anulado"))


@pytest.mark.asyncio
@pytest.mark.parametrize("estado", ["borrador", "presentado", "aceptado", "cobrado"])
async def test_presupuesto_estados_del_catalogo_aceptados(sesion_pg, estado):
    m = await sembrar_c09(sesion_pg)
    p = await _presupuesto_ok(sesion_pg, m, estado=estado)
    assert p.id is not None


@pytest.mark.asyncio
async def test_presupuesto_total_negativo_rechazado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _presupuesto(m, total=Decimal("-0.01")))


@pytest.mark.asyncio
async def test_presupuesto_rechazado_sin_motivo_rechazado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _presupuesto(m, estado="rechazado", motivo_rechazo=None))


@pytest.mark.asyncio
async def test_presupuesto_con_motivo_rechazo_fuera_de_rechazado_rechazado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _presupuesto(m, estado="presentado", motivo_rechazo="no"))


@pytest.mark.asyncio
async def test_presupuesto_rechazado_con_motivo_aceptado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    p = await _presupuesto_ok(sesion_pg, m, estado="rechazado", motivo_rechazo="caro")
    assert p.motivo_rechazo == "caro"


@pytest.mark.asyncio
async def test_presupuesto_baja_no_borrador_rechazada(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _presupuesto(
        m, estado="aceptado", deleted_at=sa.func.now(), motivo_baja="x"))


@pytest.mark.asyncio
async def test_presupuesto_baja_sin_motivo_rechazada(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _presupuesto(m, deleted_at=sa.func.now(), motivo_baja=None))


@pytest.mark.asyncio
async def test_presupuesto_baja_de_borrador_con_motivo_aceptada(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    p = await _presupuesto_ok(sesion_pg, m, deleted_at=sa.func.now(), motivo_baja="duplicado")
    assert p.id is not None


@pytest.mark.asyncio
async def test_item_sin_hallazgo_rechazado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    p = await _presupuesto_ok(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _item(p, m, hallazgo_id=None))


@pytest.mark.asyncio
async def test_item_sin_tratamiento_rechazado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    p = await _presupuesto_ok(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _item(p, m, tratamiento_id=None))


@pytest.mark.asyncio
async def test_item_repetido_rechazado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    p = await _presupuesto_ok(sesion_pg, m)
    sesion_pg.add(_item(p, m))
    await sesion_pg.flush()
    await _rechaza(sesion_pg, _item(p, m, cantidad=2))


@pytest.mark.asyncio
async def test_item_mismo_hallazgo_otro_tratamiento_o_otro_presupuesto_aceptado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    p1 = await _presupuesto_ok(sesion_pg, m)
    p2 = await _presupuesto_ok(sesion_pg, m)
    sesion_pg.add_all([
        _item(p1, m), _item(p1, m, tratamiento_id=m.trat["PRO-001"].id), _item(p2, m),
    ])
    await sesion_pg.flush()


@pytest.mark.asyncio
@pytest.mark.parametrize("cantidad", [0, 100, -1])
async def test_item_cantidad_fuera_de_rango_rechazada(sesion_pg, cantidad):
    m = await sembrar_c09(sesion_pg)
    p = await _presupuesto_ok(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _item(p, m, cantidad=cantidad))


@pytest.mark.asyncio
@pytest.mark.parametrize("cantidad", [1, 99])
async def test_item_cantidad_en_los_bordes_aceptada(sesion_pg, cantidad):
    m = await sembrar_c09(sesion_pg)
    p = await _presupuesto_ok(sesion_pg, m)
    sesion_pg.add(_item(p, m, cantidad=cantidad))
    await sesion_pg.flush()


@pytest.mark.asyncio
async def test_item_precio_negativo_rechazado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    p = await _presupuesto_ok(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _item(p, m, precio=Decimal("-1.00")))


# --- 1.3 cuenta corriente y movimiento ------------------------------------------------

async def _cuenta(sesion, m):
    from app.modelos import CuentaCorriente

    cc = CuentaCorriente(paciente_id=m.ana.id)
    sesion.add(cc)
    await sesion.flush()
    return cc


async def _recibo_id(sesion, m, tipo):
    """C-10 (D-15): un `pago` nace con recibo. Para otros tipos no hace falta."""
    return (await crear_recibo(sesion, m)).id if tipo == "pago" else None


def _mov(cc, m, **cambios):
    from app.modelos import Movimiento

    datos = {"cc_id": cc.id, "tipo": "cargo", "monto": Decimal("100.00"),
             "concepto": "Presupuesto 1", "creado_por": m.admin.id}
    datos.update(cambios)
    return Movimiento(**datos)


@pytest.mark.asyncio
async def test_cuenta_paciente_duplicado_rechazado(sesion_pg):
    from app.modelos import CuentaCorriente

    m = await sembrar_c09(sesion_pg)
    await _cuenta(sesion_pg, m)
    await _rechaza(sesion_pg, CuentaCorriente(paciente_id=m.ana.id))


@pytest.mark.asyncio
async def test_cuenta_de_dos_pacientes_distintos_aceptada(sesion_pg):
    from app.modelos import CuentaCorriente

    m = await sembrar_c09(sesion_pg)
    await _cuenta(sesion_pg, m)
    sesion_pg.add(CuentaCorriente(paciente_id=m.beto.id))
    await sesion_pg.flush()


@pytest.mark.asyncio
async def test_cuenta_sin_columna_saldo(sesion_pg):
    from app.modelos import CuentaCorriente

    nombres = {c.name for c in CuentaCorriente.__table__.columns}
    assert "saldo" not in nombres
    assert {"id", "paciente_id", "created_at"} <= nombres
    async with sesion_pg.bind.connect() as conn:
        reales = {c["name"] for c in await conn.run_sync(
            lambda sync: sa.inspect(sync).get_columns("cuenta_corriente"))}
    assert "saldo" not in reales


@pytest.mark.asyncio
@pytest.mark.parametrize("tipo,monto", [
    ("cargo", "0.00"), ("cargo", "-10.00"),
    ("pago", "0.00"), ("pago", "10.00"),
    ("ajuste", "0.00"),
    ("devolucion", "10.00"), ("cobrado", "-10.00"),
])
async def test_movimiento_tipo_y_signo_invalidos_rechazados(sesion_pg, tipo, monto):
    m = await sembrar_c09(sesion_pg)
    cc = await _cuenta(sesion_pg, m)
    recibo_id = await _recibo_id(sesion_pg, m, tipo)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _mov(cc, m, tipo=tipo, monto=Decimal(monto), recibo_id=recibo_id))


@pytest.mark.asyncio
@pytest.mark.parametrize("tipo,monto", [
    ("cargo", "0.01"), ("pago", "-0.01"), ("ajuste", "-5.00"), ("ajuste", "5.00"),
])
async def test_movimiento_tipo_y_signo_validos_aceptados(sesion_pg, tipo, monto):
    m = await sembrar_c09(sesion_pg)
    cc = await _cuenta(sesion_pg, m)
    recibo_id = await _recibo_id(sesion_pg, m, tipo)
    sesion_pg.add(_mov(cc, m, tipo=tipo, monto=Decimal(monto), recibo_id=recibo_id))
    await sesion_pg.flush()


@pytest.mark.asyncio
async def test_movimiento_segundo_cargo_mismo_presupuesto_rechazado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    p = await _presupuesto_ok(sesion_pg, m)
    cc = await _cuenta(sesion_pg, m)
    sesion_pg.add(_mov(cc, m, presupuesto_id=p.id))
    await sesion_pg.flush()
    await _rechaza(sesion_pg, _mov(cc, m, presupuesto_id=p.id))


@pytest.mark.asyncio
async def test_movimiento_cargos_de_presupuestos_distintos_o_sin_presupuesto_aceptados(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    p1 = await _presupuesto_ok(sesion_pg, m)
    p2 = await _presupuesto_ok(sesion_pg, m)
    cc = await _cuenta(sesion_pg, m)
    recibo = await crear_recibo(sesion_pg, m)
    sesion_pg.add_all([
        _mov(cc, m, presupuesto_id=p1.id), _mov(cc, m, presupuesto_id=p2.id),
        _mov(cc, m), _mov(cc, m),
        # un pago puede citar el mismo presupuesto que su cargo
        _mov(cc, m, tipo="pago", monto=Decimal("-5.00"), presupuesto_id=p1.id,
             recibo_id=recibo.id),
    ])
    await sesion_pg.flush()


@pytest.mark.asyncio
async def test_movimiento_doble_anulacion_rechazada(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    cc = await _cuenta(sesion_pg, m)
    cargo = _mov(cc, m)
    sesion_pg.add(cargo)
    await sesion_pg.flush()
    anul = dict(tipo="ajuste", monto=Decimal("-100.00"), anula_a_id=cargo.id, motivo="error")
    sesion_pg.add(_mov(cc, m, **anul))
    await sesion_pg.flush()
    await _rechaza(sesion_pg, _mov(cc, m, **anul))


@pytest.mark.asyncio
async def test_movimiento_anulacion_sin_motivo_rechazada(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    cc = await _cuenta(sesion_pg, m)
    cargo = _mov(cc, m)
    sesion_pg.add(cargo)
    await sesion_pg.flush()
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _mov(
        cc, m, tipo="ajuste", monto=Decimal("-100.00"), anula_a_id=cargo.id, motivo=None))


@pytest.mark.asyncio
async def test_movimiento_anulacion_que_no_es_ajuste_rechazada(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    cc = await _cuenta(sesion_pg, m)
    cargo = _mov(cc, m)
    sesion_pg.add(cargo)
    await sesion_pg.flush()
    await sesion_pg.commit()
    recibo = await crear_recibo(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _mov(cc, m, tipo="pago", monto=Decimal("-1.00"),
                                   anula_a_id=cargo.id, motivo="x", recibo_id=recibo.id))


@pytest.mark.asyncio
async def test_movimiento_pago_con_recibo_existente_aceptado(sesion_pg):
    """C-10 (D-15) reemplaza al contrato transitorio de C-09: el recibo ya existe y se guarda."""
    m = await sembrar_c09(sesion_pg)
    cc = await _cuenta(sesion_pg, m)
    recibo = await crear_recibo(sesion_pg, m)
    mov = _mov(cc, m, tipo="pago", monto=Decimal("-50.00"), recibo_id=recibo.id)
    sesion_pg.add(mov)
    await sesion_pg.flush()
    assert mov.recibo_id == recibo.id


@pytest.mark.asyncio
async def test_movimiento_sin_creador_rechazado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    cc = await _cuenta(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _mov(cc, m, creado_por=None))


@pytest.mark.asyncio
async def test_movimiento_creador_inexistente_rechazado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    cc = await _cuenta(sesion_pg, m)
    await sesion_pg.commit()
    await _rechaza(sesion_pg, _mov(cc, m, creado_por=987654))


# --- 1.4 inmutabilidad por trigger ------------------------------------------------------

@pytest.mark.asyncio
async def test_movimiento_insert_sigue_permitido(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    cc = await _cuenta(sesion_pg, m)
    mov = _mov(cc, m)
    sesion_pg.add(mov)
    await sesion_pg.flush()
    assert mov.id is not None and mov.created_at is not None


@pytest.mark.asyncio
async def test_movimiento_update_rechazado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    cc = await _cuenta(sesion_pg, m)
    mov = _mov(cc, m)
    sesion_pg.add(mov)
    await sesion_pg.flush()
    with pytest.raises(IntegrityError):
        await sesion_pg.execute(
            sa.text("UPDATE movimiento SET concepto = 'otro' WHERE id = :i"), {"i": mov.id})
    await sesion_pg.rollback()


@pytest.mark.asyncio
async def test_movimiento_update_por_orm_rechazado_y_monto_intacto(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    cc = await _cuenta(sesion_pg, m)
    mov = _mov(cc, m)
    sesion_pg.add(mov)
    await sesion_pg.commit()
    mov_id = mov.id
    mov.monto = Decimal("1.00")
    with pytest.raises(IntegrityError):
        await sesion_pg.flush()
    await sesion_pg.rollback()
    monto = await sesion_pg.scalar(
        sa.text("SELECT monto FROM movimiento WHERE id = :i"), {"i": mov_id})
    assert monto == Decimal("100.00")


@pytest.mark.asyncio
async def test_movimiento_delete_rechazado(sesion_pg):
    m = await sembrar_c09(sesion_pg)
    cc = await _cuenta(sesion_pg, m)
    mov = _mov(cc, m)
    sesion_pg.add(mov)
    await sesion_pg.commit()
    with pytest.raises(IntegrityError):
        await sesion_pg.execute(sa.text("DELETE FROM movimiento WHERE id = :i"), {"i": mov.id})
    await sesion_pg.rollback()
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM movimiento")) == 1
