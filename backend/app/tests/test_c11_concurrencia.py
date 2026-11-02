"""C-11 task 4.6: doble generación y doble cobro en dos sesiones reales (D-09, D-12).

Cada tarea abre su propia sesión (conexión distinta) y se lanzan con `asyncio.gather`. Un
`sleep` antes del commit retiene los locks para que la otra tarea espere. Los datos se commitean
antes de lanzar las tareas. Se repite varias veces por flakiness. Datos ficticios.
"""
import asyncio
import sys
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c11_helpers import actor_admin, aceptar_presupuesto, sembrar_c11  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

OCTUBRE = date(2026, 10, 1)
REPETICIONES = 10


async def _en_sesion(engine, operacion, *, pausa=0.0):
    """Corre `operacion(repos)` en una sesión nueva; devuelve "ok" o el nombre del error."""
    from app.servicios import liquidacion_servicio as ls

    async with async_sessionmaker(engine, expire_on_commit=False)() as sesion:
        repos = ls.LiquidacionRepos.de_sesion(sesion)
        try:
            await operacion(repos)
        except ls.ClinicaError as exc:
            await sesion.rollback()
            return type(exc).__name__
        await asyncio.sleep(pausa)  # retiene el lock para que la otra tarea espere
        await sesion.commit()
        return "ok"


def _generar(m):
    from app.esquemas.liquidacion import GenerarLiquidacionIn
    from app.servicios import liquidacion_servicio as ls

    async def _op(repos):
        await ls.generar(repos, actor_admin(m), GenerarLiquidacionIn(os_id=m.os.id, periodo=OCTUBRE))

    return _op


def _cobrar(m, liq_id, hoy):
    from app.servicios import liquidacion_servicio as ls

    async def _op(repos):
        await ls.cobrar(repos, actor_admin(m), liq_id, "transferencia", hoy)

    return _op


async def _contar(engine, consulta, **params):
    async with engine.connect() as conn:
        return await conn.scalar(sa.text(consulta), params)


@pytest.mark.asyncio
async def test_doble_generacion_concurrente_una_sola_liquidacion_con_las_filas(sesion_pg):
    engine = sesion_pg.bind
    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1), (m.h2, "PRO-001", 1)],
                              plan=m.plan_base)
    await sesion_pg.commit()
    for _ in range(REPETICIONES):
        resultados = await asyncio.gather(
            _en_sesion(engine, _generar(m), pausa=0.2), _en_sesion(engine, _generar(m)))
        assert sorted(resultados) == ["ConflictoError", "ok"], resultados
        assert await _contar(engine, "SELECT count(*) FROM liquidacion") == 1
        assert await _contar(engine, "SELECT count(*) FROM item_liquidacion") == 2
        assert await _contar(engine, "SELECT count(DISTINCT item_presupuesto_id) "
                                     "FROM item_liquidacion") == 2
        async with engine.begin() as conn:  # deja el estado inicial para la repetición
            await conn.execute(sa.text("DELETE FROM item_liquidacion"))
            await conn.execute(sa.text("DELETE FROM liquidacion"))


@pytest.mark.asyncio
async def test_doble_cobro_concurrente_un_200_un_409_y_un_solo_ingreso(sesion_pg):
    from app.esquemas.liquidacion import GenerarLiquidacionIn
    from app.servicios import liquidacion_servicio as ls
    from app.servicios.caja_servicio import hoy_operativo

    engine = sesion_pg.bind
    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    repos = ls.LiquidacionRepos.de_sesion(sesion_pg)
    liq = await ls.generar(repos, actor_admin(m), GenerarLiquidacionIn(os_id=m.os.id, periodo=OCTUBRE))
    await ls.presentar(repos, actor_admin(m), liq.id)
    await sesion_pg.commit()
    hoy = hoy_operativo()
    resultados = await asyncio.gather(
        _en_sesion(engine, _cobrar(m, liq.id, hoy), pausa=0.2),
        _en_sesion(engine, _cobrar(m, liq.id, hoy)))
    assert sorted(resultados) == ["ConflictoError", "ok"], resultados
    assert await _contar(
        engine, "SELECT count(*) FROM movimiento_caja WHERE liquidacion_id = :l", l=liq.id) == 1
    assert await _contar(
        engine, "SELECT estado FROM liquidacion WHERE id = :l", l=liq.id) == "cobrada"
