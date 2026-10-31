"""C-09 grupo 3: repos de presupuesto y cuenta corriente contra PG real (D-11, D-13).

Datos ficticios. Los repos no usan reloj ni reglas de negocio: solo consultas.
"""
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c09_helpers import sembrar_c09  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

T0 = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


async def _presupuesto(sesion, m, minutos=0, **cambios):
    from app.repos.presupuesto_repo import PresupuestoRepository

    datos = {"paciente_id": m.ana.id, "profesional_id": m.prof_a.id, "estado": "borrador",
             "total": Decimal("0.00"), "created_at": T0 + timedelta(minutes=minutos)}
    datos.update(cambios)
    return await PresupuestoRepository(sesion).crear(**datos)


def _item(m, hallazgo, codigo="CON-001", cantidad=1):
    return {"hallazgo_id": hallazgo.id, "tratamiento_id": m.trat[codigo].id,
            "cantidad": cantidad, "precio": m.trat[codigo].precio_base}


# --- 3.1 presupuesto_repo ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_listar_filtra_estado_y_excluye_bajas(sesion_pg):
    from app.repos.presupuesto_repo import PresupuestoRepository

    m = await sembrar_c09(sesion_pg)
    borrador = await _presupuesto(sesion_pg, m)
    presentado = await _presupuesto(sesion_pg, m, estado="presentado")
    await _presupuesto(sesion_pg, m, deleted_at=T0, motivo_baja="duplicado")
    await _presupuesto(sesion_pg, m, estado="rechazado", motivo_rechazo="caro")
    ajeno = await _presupuesto(sesion_pg, m, paciente_id=m.beto.id)
    repo = PresupuestoRepository(sesion_pg)

    todos = {p.id for p in await repo.listar(m.ana.id)}
    assert ajeno.id not in todos and len(todos) == 3
    assert [p.id for p in await repo.listar(m.ana.id, "presentado")] == [presentado.id]
    assert [p.id for p in await repo.listar(m.ana.id, "borrador")] == [borrador.id]
    assert await repo.listar(m.ana.id, "aceptado") == []
    assert [p.estado for p in await repo.listar(m.ana.id, "rechazado")] == ["rechazado"]


@pytest.mark.asyncio
async def test_listar_mas_reciente_primero(sesion_pg):
    from app.repos.presupuesto_repo import PresupuestoRepository

    m = await sembrar_c09(sesion_pg)
    viejo = await _presupuesto(sesion_pg, m, minutos=0)
    nuevo = await _presupuesto(sesion_pg, m, minutos=30)
    medio = await _presupuesto(sesion_pg, m, minutos=10)
    ids = [p.id for p in await PresupuestoRepository(sesion_pg).listar(m.ana.id)]
    assert ids == [nuevo.id, medio.id, viejo.id]


@pytest.mark.asyncio
async def test_listar_mismo_instante_desempata_por_id_descendente(sesion_pg):
    from app.repos.presupuesto_repo import PresupuestoRepository

    m = await sembrar_c09(sesion_pg)
    a = await _presupuesto(sesion_pg, m)
    b = await _presupuesto(sesion_pg, m)
    ids = [p.id for p in await PresupuestoRepository(sesion_pg).listar(m.ana.id)]
    assert ids == [b.id, a.id]


@pytest.mark.asyncio
async def test_get_activo_oculta_las_bajas(sesion_pg):
    from app.repos.presupuesto_repo import PresupuestoRepository

    m = await sembrar_c09(sesion_pg)
    viva = await _presupuesto(sesion_pg, m)
    muerta = await _presupuesto(sesion_pg, m, deleted_at=T0, motivo_baja="x")
    repo = PresupuestoRepository(sesion_pg)
    assert (await repo.get_activo(viva.id)).id == viva.id
    assert await repo.get_activo(muerta.id) is None
    assert await repo.get_activo(99999) is None
    assert await repo.get_para_actualizar(muerta.id) is None
    assert (await repo.get_para_actualizar(viva.id)).id == viva.id


@pytest.mark.asyncio
async def test_reemplazar_items_deja_solo_los_nuevos(sesion_pg):
    from app.repos.presupuesto_repo import PresupuestoRepository

    m = await sembrar_c09(sesion_pg)
    p = await _presupuesto(sesion_pg, m)
    repo = PresupuestoRepository(sesion_pg)
    await repo.reemplazar_items(p.id, [_item(m, m.h1), _item(m, m.h2, "PRO-001", 3)])
    assert len(await repo.items_detalle(p.id)) == 2
    await repo.reemplazar_items(p.id, [_item(m, m.h3, "OBT-001")])
    detalle = await repo.items_detalle(p.id)
    assert [d.item.hallazgo_id for d in detalle] == [m.h3.id]
    otro = await _presupuesto(sesion_pg, m)
    await repo.reemplazar_items(otro.id, [_item(m, m.h1)])
    assert len(await repo.items_detalle(p.id)) == 1  # el reemplazo no toca otros presupuestos


@pytest.mark.asyncio
async def test_items_detalle_trae_pieza_cara_y_nombre_de_tratamiento(sesion_pg):
    from app.repos.presupuesto_repo import PresupuestoRepository

    m = await sembrar_c09(sesion_pg)
    p = await _presupuesto(sesion_pg, m)
    repo = PresupuestoRepository(sesion_pg)
    await repo.reemplazar_items(p.id, [_item(m, m.h1), _item(m, m.h3, "PRO-001")])
    d1, d2 = await repo.items_detalle(p.id)
    assert (d1.pieza_fdi, d1.cara, d1.tratamiento_nombre) == (16, "oclusal", "Trat CON-001")
    assert (d2.pieza_fdi, d2.cara, d2.tratamiento_nombre) == (36, "pieza_completa", "Trat PRO-001")
    assert d1.hallazgo_vigente is True


@pytest.mark.asyncio
async def test_items_indican_hallazgo_no_vigente(sesion_pg):
    from app.repos.presupuesto_repo import PresupuestoRepository

    m = await sembrar_c09(sesion_pg)
    p = await _presupuesto(sesion_pg, m)
    repo = PresupuestoRepository(sesion_pg)
    await repo.reemplazar_items(p.id, [_item(m, m.h1), _item(m, m.h2)])
    m.h2.deleted_at = T0
    m.h2.motivo_baja = "corregido"
    await sesion_pg.flush()
    vigentes = {d.item.hallazgo_id: d.hallazgo_vigente for d in await repo.items_detalle(p.id)}
    assert vigentes == {m.h1.id: True, m.h2.id: False}


# --- 3.2 cuenta_repo ------------------------------------------------------------------------

async def _mov(sesion, m, cc, tipo="cargo", monto="100.00", **cambios):
    from app.repos.cuenta_repo import CuentaRepository

    datos = {"tipo": tipo, "monto": Decimal(monto), "concepto": "Presupuesto 1",
             "creado_por": m.admin.id}
    datos.update(cambios)
    return await CuentaRepository(sesion).crear_movimiento(cc.id, **datos)


@pytest.mark.asyncio
async def test_asegurar_dos_veces_una_fila(sesion_pg):
    import sqlalchemy as sa

    from app.repos.cuenta_repo import CuentaRepository

    m = await sembrar_c09(sesion_pg)
    repo = CuentaRepository(sesion_pg)
    uno = await repo.asegurar(m.ana.id)
    dos = await repo.asegurar(m.ana.id)
    assert uno.id == dos.id and uno.paciente_id == m.ana.id
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM cuenta_corriente")) == 1
    otro = await repo.asegurar(m.beto.id)
    assert otro.id != uno.id


@pytest.mark.asyncio
async def test_por_paciente_no_crea_filas(sesion_pg):
    import sqlalchemy as sa

    from app.repos.cuenta_repo import CuentaRepository

    m = await sembrar_c09(sesion_pg)
    repo = CuentaRepository(sesion_pg)
    assert await repo.por_paciente(m.ana.id) is None
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM cuenta_corriente")) == 0
    cc = await repo.asegurar(m.ana.id)
    assert (await repo.por_paciente(m.ana.id)).id == cc.id


@pytest.mark.asyncio
async def test_saldo_suma_cargo_pago_ajuste(sesion_pg):
    from app.repos.cuenta_repo import CuentaRepository

    m = await sembrar_c09(sesion_pg)
    repo = CuentaRepository(sesion_pg)
    cc = await repo.asegurar(m.ana.id)
    await _mov(sesion_pg, m, cc, "cargo", "1000.00")
    await _mov(sesion_pg, m, cc, "pago", "-400.00")
    await _mov(sesion_pg, m, cc, "ajuste", "-100.00", motivo="descuento")
    assert await repo.saldo(cc.id) == Decimal("500.00")


@pytest.mark.asyncio
async def test_saldo_sin_movimientos_cero(sesion_pg):
    from app.repos.cuenta_repo import CuentaRepository

    m = await sembrar_c09(sesion_pg)
    repo = CuentaRepository(sesion_pg)
    cc = await repo.asegurar(m.ana.id)
    assert await repo.saldo(cc.id) == Decimal("0")


@pytest.mark.asyncio
async def test_saldo_negativo_a_favor(sesion_pg):
    from app.repos.cuenta_repo import CuentaRepository

    m = await sembrar_c09(sesion_pg)
    repo = CuentaRepository(sesion_pg)
    cc = await repo.asegurar(m.ana.id)
    await _mov(sesion_pg, m, cc, "cargo", "100.00")
    await _mov(sesion_pg, m, cc, "pago", "-250.50")
    assert await repo.saldo(cc.id) == Decimal("-150.50")


@pytest.mark.asyncio
async def test_saldo_de_una_cuenta_no_mezcla_otras(sesion_pg):
    from app.repos.cuenta_repo import CuentaRepository

    m = await sembrar_c09(sesion_pg)
    repo = CuentaRepository(sesion_pg)
    ana, beto = await repo.asegurar(m.ana.id), await repo.asegurar(m.beto.id)
    await _mov(sesion_pg, m, ana, "cargo", "100.00")
    await _mov(sesion_pg, m, beto, "cargo", "7.00")
    assert await repo.saldo(ana.id) == Decimal("100.00")
    assert await repo.saldo(beto.id) == Decimal("7.00")


@pytest.mark.asyncio
async def test_movimiento_listado_marca_anulado(sesion_pg):
    from app.repos.cuenta_repo import CuentaRepository

    m = await sembrar_c09(sesion_pg)
    repo = CuentaRepository(sesion_pg)
    cc = await repo.asegurar(m.ana.id)
    cargo1 = await _mov(sesion_pg, m, cc, "cargo", "100.00")
    cargo2 = await _mov(sesion_pg, m, cc, "cargo", "50.00")
    anul = await _mov(sesion_pg, m, cc, "ajuste", "-100.00", anula_a_id=cargo1.id, motivo="error")
    filas = await repo.movimientos(cc.id)
    assert [f.movimiento.id for f in filas] == [anul.id, cargo2.id, cargo1.id]
    assert {f.movimiento.id: f.anulado for f in filas} == {
        anul.id: False, cargo2.id: False, cargo1.id: True}


@pytest.mark.asyncio
async def test_movimiento_para_actualizar_exige_la_cuenta(sesion_pg):
    from app.repos.cuenta_repo import CuentaRepository

    m = await sembrar_c09(sesion_pg)
    repo = CuentaRepository(sesion_pg)
    ana, beto = await repo.asegurar(m.ana.id), await repo.asegurar(m.beto.id)
    cargo = await _mov(sesion_pg, m, ana)
    assert (await repo.movimiento_para_actualizar(ana.id, cargo.id)).id == cargo.id
    assert await repo.movimiento_para_actualizar(beto.id, cargo.id) is None
    assert await repo.movimiento_para_actualizar(ana.id, 99999) is None


@pytest.mark.asyncio
async def test_presupuestos_con_cargo_anulado(sesion_pg):
    from app.repos.cuenta_repo import CuentaRepository

    m = await sembrar_c09(sesion_pg)
    p1 = await _presupuesto(sesion_pg, m)
    p2 = await _presupuesto(sesion_pg, m)
    p3 = await _presupuesto(sesion_pg, m)
    repo = CuentaRepository(sesion_pg)
    cc = await repo.asegurar(m.ana.id)
    c1 = await _mov(sesion_pg, m, cc, presupuesto_id=p1.id)
    await _mov(sesion_pg, m, cc, presupuesto_id=p2.id)
    await _mov(sesion_pg, m, cc, "ajuste", "-100.00", anula_a_id=c1.id, motivo="error")
    assert await repo.presupuestos_con_cargo_anulado([p1.id, p2.id, p3.id]) == {p1.id}
    assert await repo.presupuestos_con_cargo_anulado([]) == set()
