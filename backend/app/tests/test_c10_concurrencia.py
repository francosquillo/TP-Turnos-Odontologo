"""C-10 grupos 4.6, 4.9, 5.3 y 6.4: concurrencia real con sesiones propias sobre PG real.

Cada tarea abre su propia sesión (conexión distinta) y se lanzan con `asyncio.gather`. Un
`sleep` antes del commit retiene el lock para que las demás esperen. Los datos se commitean
antes de lanzar las tareas. Los tests que importan por flakiness repiten 20 veces seguidas.
Datos ficticios.
"""
import asyncio
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c10_helpers import (  # noqa: E402
    clave_nueva, cobro_in, crear_presupuesto_aceptado, escenario_caja,
)
from db_utils import sesion_pg  # noqa: E402, F401

HOY = date(2026, 10, 31)
REPETICIONES = 20


async def _en_sesion(engine, operacion, *, pausa=0.0, retraso=0.0, revertir=False):
    """Corre `operacion(repos)` en una sesión nueva; devuelve la etiqueta o el nombre del error."""
    from app.servicios import caja_servicio as cs

    if retraso:
        await asyncio.sleep(retraso)
    async with async_sessionmaker(engine, expire_on_commit=False)() as sesion:
        repos = cs.CajaRepos.de_sesion(sesion)
        try:
            resultado = await operacion(repos)
        except cs.ClinicaError as exc:
            await sesion.rollback()
            return type(exc).__name__
        await asyncio.sleep(pausa)  # retiene el lock para que la otra tarea espere
        if revertir:
            await sesion.rollback()
            return "revertido"
        if resultado == "reintento":
            await sesion.rollback()  # como el router: un reintento no deja filas
            return resultado
        await sesion.commit()
        return resultado


def _cobrar(actor, datos, hoy=HOY):
    from app.servicios import caja_servicio as cs

    async def _op(repos):
        _, creado = await cs.cobrar(repos, actor, datos, hoy=hoy)
        return "creado" if creado else "reintento"

    return _op


def _cierre(actor, caja_id, contado):
    from app.esquemas.caja import CierreIn
    from app.servicios import caja_servicio as cs

    async def _op(repos):
        await cs.cerrar(repos, actor, CierreIn(
            caja_id=caja_id, total_contado=contado, motivo_diferencia="control de prueba"))
        return "ok"

    return _op


def _anulacion(actor, recibo_id, hoy=HOY):
    from app.servicios import caja_servicio as cs

    async def _op(repos):
        await cs.anular_recibo(repos, actor, recibo_id, "error de carga", hoy=hoy)
        return "ok"

    return _op


async def _contar(engine, consulta, **params):
    async with engine.connect() as conn:
        return await conn.scalar(sa.text(consulta), params)


async def _cerrar_sql(engine, fecha):
    """Cierra una caja por SQL (sin pasar por el servicio) para repetir con otra fecha."""
    async with engine.begin() as conn:
        await conn.execute(sa.text(
            "UPDATE caja SET estado = 'cerrada', total_sistema = s.t, total_contado = s.t, "
            "diferencia = 0, cerrada_por = abierta_por, cerrada_at = now() "
            "FROM (SELECT coalesce(sum(monto), 0) AS t FROM movimiento_caja mc "
            "      JOIN caja c ON c.id = mc.caja_id WHERE c.fecha = :f) s "
            "WHERE caja.fecha = :f"), {"f": fecha})


async def _mundo(sesion, cantidad=1, total="1000.00"):
    cs, repos, m, a = await escenario_caja(sesion)
    presupuestos = []
    for _ in range(cantidad):
        p, _ = await crear_presupuesto_aceptado(sesion, m, total=total)
        presupuestos.append(p)
    await sesion.commit()
    return cs, m, a, presupuestos, sesion.bind


# --- 4.6 cobros concurrentes ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_veinte_cobros_concurrentes_numeros_1_a_20(sesion_pg):
    cs, m, a, ps, engine = await _mundo(sesion_pg, cantidad=20, total="500.00")
    resultados = await asyncio.gather(*[
        _en_sesion(engine, _cobrar(a["sec"], cobro_in(p, "500.00"))) for p in ps])
    assert resultados == ["creado"] * 20, resultados
    async with engine.connect() as conn:
        numeros = (await conn.execute(sa.text("SELECT numero FROM recibo ORDER BY numero"))).scalars().all()
    assert numeros == list(range(1, 21))
    assert await _contar(engine, "SELECT count(*) FROM caja") == 1
    assert await _contar(engine, "SELECT count(*) FROM movimiento_caja") == 20
    assert await _contar(engine, "SELECT count(*) FROM movimiento WHERE tipo = 'pago'") == 20
    assert await _contar(engine, "SELECT ultimo FROM recibo_contador") == 20


@pytest.mark.asyncio
async def test_primer_cobro_concurrente_una_caja(sesion_pg):
    cs, m, a, ps, engine = await _mundo(sesion_pg, cantidad=2, total="300.00")
    for i in range(REPETICIONES):
        dia = HOY + timedelta(days=i)
        resultados = await asyncio.gather(
            _en_sesion(engine, _cobrar(a["sec"], cobro_in(ps[0], "10.00"), dia), pausa=0.05),
            _en_sesion(engine, _cobrar(a["sec"], cobro_in(ps[1], "10.00"), dia), pausa=0.05))
        assert resultados == ["creado", "creado"], (i, resultados)
        assert await _contar(
            engine, "SELECT count(*) FROM caja WHERE fecha = :f", f=dia) == 1
        assert await _contar(
            engine, "SELECT count(*) FROM movimiento_caja mc JOIN caja c ON c.id = mc.caja_id "
            "WHERE c.fecha = :f", f=dia) == 2
        await _cerrar_sql(engine, dia)


@pytest.mark.asyncio
async def test_sobrepago_concurrente_un_ganador(sesion_pg):
    cs, m, a, ps, engine = await _mundo(sesion_pg, cantidad=REPETICIONES, total="600.00")
    for i, p in enumerate(ps):
        resultados = await asyncio.gather(
            _en_sesion(engine, _cobrar(a["sec"], cobro_in(p, "600.00")), pausa=0.05),
            _en_sesion(engine, _cobrar(a["sec"], cobro_in(p, "600.00")), pausa=0.05))
        # El ganador salda el presupuesto (queda `cobrado`) y el perdedor, que relee tras el
        # lock, recibe 409 (ConflictoError); 422 no es posible porque no ve un pendiente menor.
        assert sorted(resultados) == ["ConflictoError", "creado"], (i, resultados)
        pendiente = await _contar(
            engine, "SELECT coalesce(sum(monto), 0) FROM movimiento WHERE presupuesto_id = :p",
            p=p.id)
        assert pendiente == Decimal("0.00")
    assert await _contar(engine, "SELECT count(*) FROM recibo") == REPETICIONES


@pytest.mark.asyncio
async def test_cobros_con_fallo_intercalado_sin_huecos(sesion_pg):
    cs, m, a, ps, engine = await _mundo(sesion_pg, cantidad=12, total="100.00")
    tareas = []
    for i, p in enumerate(ps):
        monto = "100.00" if i % 3 else "9999.00"  # cada tercero se rechaza por sobrepago
        tareas.append(_en_sesion(engine, _cobrar(a["sec"], cobro_in(p, monto))))
    resultados = await asyncio.gather(*tareas)
    exitosos = resultados.count("creado")
    assert exitosos == 8 and resultados.count("ValidacionClinicaError") == 4, resultados
    async with engine.connect() as conn:
        numeros = (await conn.execute(sa.text("SELECT numero FROM recibo ORDER BY numero"))).scalars().all()
    assert numeros == list(range(1, exitosos + 1))
    assert await _contar(engine, "SELECT ultimo FROM recibo_contador") == exitosos


# --- 4.9 misma clave en paralelo ------------------------------------------------------------------

async def _estado_de_un_cobro(engine, esperados=1):
    assert await _contar(engine, "SELECT count(*) FROM recibo") == esperados
    assert await _contar(engine, "SELECT count(*) FROM movimiento WHERE tipo = 'pago'") == esperados
    assert await _contar(engine, "SELECT count(*) FROM movimiento_caja") == esperados
    assert await _contar(engine, "SELECT ultimo FROM recibo_contador") == esperados


@pytest.mark.asyncio
async def test_misma_clave_concurrente_un_recibo(sesion_pg):
    cs, m, a, ps, engine = await _mundo(sesion_pg, cantidad=REPETICIONES, total="500.00")
    for i, p in enumerate(ps):
        datos = cobro_in(p, "200.00")
        resultados = await asyncio.gather(
            _en_sesion(engine, _cobrar(a["sec"], datos), pausa=0.05),
            _en_sesion(engine, _cobrar(a["sec"], datos), pausa=0.05))
        assert sorted(resultados) == ["creado", "reintento"], (i, resultados)
    await _estado_de_un_cobro(engine, esperados=REPETICIONES)


@pytest.mark.asyncio
async def test_misma_clave_ocho_sesiones_un_recibo(sesion_pg):
    cs, m, a, ps, engine = await _mundo(sesion_pg, cantidad=1, total="500.00")
    datos = cobro_in(ps[0], "200.00")
    resultados = await asyncio.gather(*[
        _en_sesion(engine, _cobrar(a["sec"], datos), pausa=0.02) for _ in range(8)])
    assert sorted(resultados) == ["creado"] + ["reintento"] * 7, resultados
    await _estado_de_un_cobro(engine)


@pytest.mark.asyncio
async def test_misma_clave_otro_contenido_concurrente_un_recibo(sesion_pg):
    cs, m, a, ps, engine = await _mundo(sesion_pg, cantidad=REPETICIONES, total="500.00")
    for i, p in enumerate(ps):
        clave = clave_nueva()
        resultados = await asyncio.gather(
            _en_sesion(engine, _cobrar(a["sec"], cobro_in(p, "200.00", clave=clave)), pausa=0.05),
            _en_sesion(engine, _cobrar(a["sec"], cobro_in(p, "300.00", clave=clave)), pausa=0.05))
        assert sorted(resultados) == ["ConflictoError", "creado"], (i, resultados)
    await _estado_de_un_cobro(engine, esperados=REPETICIONES)


@pytest.mark.asyncio
async def test_misma_clave_primero_falla_segundo_cobra(sesion_pg):
    cs, m, a, ps, engine = await _mundo(sesion_pg, cantidad=REPETICIONES, total="500.00")
    for i, p in enumerate(ps):
        datos = cobro_in(p, "200.00")
        resultados = await asyncio.gather(
            _en_sesion(engine, _cobrar(a["sec"], datos), pausa=0.3, revertir=True),
            _en_sesion(engine, _cobrar(a["sec"], datos), retraso=0.1))
        assert resultados == ["revertido", "creado"], (i, resultados)
    await _estado_de_un_cobro(engine, esperados=REPETICIONES)


@pytest.mark.asyncio
async def test_misma_clave_y_cierre_concurrentes_sin_409(sesion_pg):
    cs, m, a, ps, engine = await _mundo(sesion_pg, cantidad=REPETICIONES + 1, total="500.00")
    # Una caja por repetición, con un cobro previo commiteado.
    for i in range(REPETICIONES):
        dia = HOY + timedelta(days=i)
        async with async_sessionmaker(engine, expire_on_commit=False)() as s:
            from app.servicios import caja_servicio as svc

            repos = svc.CajaRepos.de_sesion(s)
            await svc.cobrar(repos, a["sec"], cobro_in(ps[-1], "10.00"), hoy=dia)
            await s.commit()
        caja_id = await _contar(engine, "SELECT id FROM caja WHERE fecha = :f", f=dia)
        datos = cobro_in(ps[i], "200.00")
        original, reintento, cierre = await asyncio.gather(
            _en_sesion(engine, _cobrar(a["sec"], datos, dia), pausa=0.3),
            _en_sesion(engine, _cobrar(a["sec"], datos, dia), retraso=0.1),
            _en_sesion(engine, _cierre(a["sec"], caja_id, Decimal("210.00")), retraso=0.15))
        assert (original, reintento) == ("creado", "reintento"), (i, original, reintento, cierre)
        assert cierre == "ok", (i, cierre)
        assert await _contar(
            engine, "SELECT total_sistema FROM caja WHERE id = :i", i=caja_id) == Decimal("210.00")


@pytest.mark.asyncio
async def test_claves_mixtas_numeros_consecutivos(sesion_pg):
    cs, m, a, ps, engine = await _mundo(sesion_pg, cantidad=5, total="500.00")
    cobros = [cobro_in(p, "100.00") for p in ps]
    resultados = await asyncio.gather(*[
        _en_sesion(engine, _cobrar(a["sec"], c), pausa=0.01) for c in cobros + cobros])
    assert sorted(resultados) == ["creado"] * 5 + ["reintento"] * 5, resultados
    async with engine.connect() as conn:
        numeros = (await conn.execute(sa.text("SELECT numero FROM recibo ORDER BY numero"))).scalars().all()
    assert numeros == [1, 2, 3, 4, 5]


# --- 5.3 cierre concurrente ----------------------------------------------------------------------------

async def _caja_con_cobro(engine, a, presupuesto, dia, monto="100.00"):
    from app.servicios import caja_servicio as svc

    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        repos = svc.CajaRepos.de_sesion(s)
        await svc.cobrar(repos, a["sec"], cobro_in(presupuesto, monto), hoy=dia)
        await s.commit()
    return await _contar(engine, "SELECT id FROM caja WHERE fecha = :f", f=dia)


@pytest.mark.asyncio
async def test_doble_cierre_concurrente_un_ganador(sesion_pg):
    cs, m, a, ps, engine = await _mundo(sesion_pg, cantidad=1, total="5000.00")
    for i in range(REPETICIONES):
        dia = HOY + timedelta(days=i)
        caja_id = await _caja_con_cobro(engine, a, ps[0], dia)
        resultados = await asyncio.gather(
            _en_sesion(engine, _cierre(a["sec"], caja_id, Decimal("100.00")), pausa=0.05),
            _en_sesion(engine, _cierre(a["sec"], caja_id, Decimal("100.00")), pausa=0.05))
        assert sorted(resultados) == ["ConflictoError", "ok"], (i, resultados)


@pytest.mark.asyncio
async def test_cobro_y_cierre_total_consistente(sesion_pg):
    cs, m, a, ps, engine = await _mundo(sesion_pg, cantidad=1, total="5000.00")
    ganadores = {"cobro": 0, "cierre": 0}
    for i in range(REPETICIONES):
        dia = HOY + timedelta(days=i)
        caja_id = await _caja_con_cobro(engine, a, ps[0], dia, monto="100.00")
        cobro, cierre = await asyncio.gather(
            _en_sesion(engine, _cobrar(a["sec"], cobro_in(ps[0], "50.00"), dia), pausa=0.05),
            _en_sesion(engine, _cierre(a["sec"], caja_id, Decimal("100.00")), pausa=0.05))
        total_sistema = await _contar(
            engine, "SELECT total_sistema FROM caja WHERE id = :i", i=caja_id)
        suma_movimientos = await _contar(
            engine, "SELECT sum(monto) FROM movimiento_caja WHERE caja_id = :i", i=caja_id)
        assert cierre == "ok", (i, cobro, cierre)
        assert total_sistema == suma_movimientos, (i, cobro, total_sistema, suma_movimientos)
        if cobro == "creado":
            ganadores["cobro"] += 1
            assert total_sistema == Decimal("150.00")
        else:
            ganadores["cierre"] += 1
            assert cobro == "ConflictoError" and total_sistema == Decimal("100.00")
    assert ganadores["cobro"] + ganadores["cierre"] == REPETICIONES


# --- 6.4 anulación concurrente -------------------------------------------------------------------------

async def _recibo_de(engine, a, presupuesto, dia, monto="100.00"):
    from app.servicios import caja_servicio as svc

    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        repos = svc.CajaRepos.de_sesion(s)
        cobro, _ = await svc.cobrar(repos, a["sec"], cobro_in(presupuesto, monto), hoy=dia)
        await s.commit()
    return cobro.id


@pytest.mark.asyncio
async def test_doble_anulacion_concurrente_un_contramovimiento(sesion_pg):
    cs, m, a, ps, engine = await _mundo(sesion_pg, cantidad=REPETICIONES, total="500.00")
    for i, p in enumerate(ps):
        recibo_id = await _recibo_de(engine, a, p, HOY)
        resultados = await asyncio.gather(
            _en_sesion(engine, _anulacion(a["admin"], recibo_id), pausa=0.05),
            _en_sesion(engine, _anulacion(a["admin"], recibo_id), pausa=0.05))
        assert sorted(resultados) == ["ConflictoError", "ok"], (i, resultados)
        assert await _contar(
            engine, "SELECT count(*) FROM movimiento WHERE recibo_id = :r AND tipo = 'ajuste'",
            r=recibo_id) == 1
        assert await _contar(
            engine, "SELECT count(*) FROM movimiento_caja WHERE recibo_id = :r AND monto < 0",
            r=recibo_id) == 1


@pytest.mark.asyncio
async def test_cobro_y_anulacion_concurrentes_sin_deadlock(sesion_pg):
    cs, m, a, ps, engine = await _mundo(sesion_pg, cantidad=REPETICIONES + 1, total="500.00")
    for i in range(REPETICIONES):
        recibo_id = await _recibo_de(engine, a, ps[-1], HOY, monto="10.00")
        resultados = await asyncio.wait_for(asyncio.gather(
            _en_sesion(engine, _cobrar(a["sec"], cobro_in(ps[i], "100.00")), pausa=0.05),
            _en_sesion(engine, _anulacion(a["admin"], recibo_id), pausa=0.05)), timeout=20)
        assert resultados == ["creado", "ok"], (i, resultados)
    numeros = await _contar(engine, "SELECT count(DISTINCT numero) FROM recibo")
    assert numeros == await _contar(engine, "SELECT count(*) FROM recibo")
    assert await _contar(engine, "SELECT max(numero) FROM recibo") == numeros
