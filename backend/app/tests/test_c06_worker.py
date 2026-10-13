"""C-06 task 4.1 RED: worker notif_jobs + evolucion de main (D-04).

Sin HTTP directo: los jobs delegan en el servicio + cliente. Sin servicio
compose nuevo (decision C-01): main.py suma bucle_notif(3600s) + barrido de
recuperacion al arranque ([47h,49h]/[23h,25h], ventana extendida ±60 min).
Unit con fakes (siempre corre); variante Redis real skipea sin Docker.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from freezegun import freeze_time

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c05_fakes import FakePacienteRepo, fabricar_paciente  # noqa: E402
from c06_fakes import (  # noqa: E402
    CuentaCliente,
    FakeNotifRepo,
    FakeRedis,
    FakeTurnoRepoC06,
    fabricar_turno_c06,
)

AHORA = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
A_48H = AHORA + timedelta(hours=48)


def _mundo():
    return (
        FakeTurnoRepoC06([fabricar_turno_c06(
            id=1, inicio=A_48H, fin=A_48H + timedelta(minutes=30))]),
        FakeNotifRepo(),
        FakePacienteRepo([fabricar_paciente(
            id=1, telefono="1140001111", email="ana@ficticio.test")]),
        FakeRedis(),
        CuentaCliente(),
    )


@pytest.mark.asyncio
async def test_notif_jobs_delega_sin_duplicar():
    """Task 4.1 RED: barrido via jobs no duplica (delega, sin HTTP directo)."""
    from app.worker import notif_jobs as jobs

    turnos, notifs, pacientes, tienda, cliente = _mundo()
    with freeze_time(AHORA):
        uno = await jobs.barrido_recordatorios(
            turnos, notifs, pacientes, tienda, cliente, ahora=AHORA)
        dos = await jobs.barrido_recordatorios(
            turnos, notifs, pacientes, tienda, cliente, ahora=AHORA)
        re = await jobs.reintentar_fallidas(
            notifs, turnos, pacientes, tienda, cliente, ahora=AHORA)
    assert uno["encoladas"] == 1 and dos["encoladas"] == 0
    assert notifs.cantidad_activas() == 1
    assert len(cliente.envios) == 1
    assert re["enviadas"] == 0  # nada pendiente: sin trabajo extra
    assert "httpx" not in dir(jobs)  # sin HTTP directo en el worker


@pytest.mark.asyncio
async def test_barrido_recuperacion_ventana_extendida():
    """Triangulacion D-04: arranque cubre [47h,49h] que el tick normal pierde."""
    from app.worker import notif_jobs as jobs

    a_47h12 = AHORA + timedelta(hours=47, minutes=12)  # fuera de ±30 min
    turnos = FakeTurnoRepoC06([fabricar_turno_c06(
        id=1, inicio=a_47h12, fin=a_47h12 + timedelta(minutes=30))])
    _, notifs, pacientes, tienda, cliente = _mundo()
    with freeze_time(AHORA):
        normal = await jobs.barrido_recordatorios(
            turnos, notifs, pacientes, tienda, cliente, ahora=AHORA)
        recu = await jobs.barrido_recuperacion(
            turnos, notifs, pacientes, tienda, cliente, ahora=AHORA)
    assert normal["encoladas"] == 0
    assert recu["encoladas"] == 1


@pytest.mark.asyncio
async def test_notif_jobs_redis_real_sin_duplicar():
    """Task 4.1 GREEN (Redis real): doble tick via jobs -> 1 envio."""
    import os

    try:
        import redis.asyncio as aioredis
    except ImportError:
        pytest.skip("redis no instalado")
    tienda = aioredis.from_url(
        os.getenv("REDIS_URL_TEST", "redis://localhost:6379/0"),
        decode_responses=True,
    )
    try:
        await tienda.ping()
    except Exception as exc:
        pytest.skip(f"Redis no reachable: {exc}")
    try:
        from app.worker import notif_jobs as jobs

        turnos, notifs, pacientes, _, cliente = _mundo()
        with freeze_time(AHORA):
            await jobs.barrido_recordatorios(
                turnos, notifs, pacientes, tienda, cliente, ahora=AHORA)
            await jobs.barrido_recordatorios(
                turnos, notifs, pacientes, tienda, cliente, ahora=AHORA)
        assert notifs.cantidad_activas() == 1
        assert len(cliente.envios) == 1
    finally:
        try:
            async for clave in tienda.scan_iter("notif:*"):
                await tienda.delete(clave)
        except Exception:
            pass
        await tienda.aclose()


def test_worker_main_conserva_heartbeat_y_suma_bucle():
    """Task 4.1 RED: main mantiene heartbeat y suma bucle_notif horario."""
    import asyncio
    import inspect

    import app.worker.main as main

    assert asyncio.iscoroutinefunction(main.heartbeat)
    assert asyncio.iscoroutinefunction(main.bucle_notif)
    intervalo = inspect.signature(main.bucle_notif).parameters["intervalo_s"]
    assert intervalo.default == 3600.0
    src = inspect.getsource(main.main)
    assert "heartbeat" in src and "bucle_notif" in src
