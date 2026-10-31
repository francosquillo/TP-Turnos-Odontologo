"""C-10 grupo 4.1: día operativo y caja operable (D-04, D-06, D-07).

`freezegun` fija el reloj; las aserciones usan fechas calculadas en Python, nunca el
`now()` de la DB (freezegun no llega ahí). Datos ficticios.
"""
import sys
from datetime import date
from pathlib import Path

import pytest
from freezegun import freeze_time

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c10_helpers import crear_caja, escenario_caja  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

HOY = date(2026, 10, 31)
AYER = date(2026, 10, 30)


def test_hoy_operativo_antes_de_medianoche_local():
    from app.servicios.caja_servicio import hoy_operativo

    # 02:59:59Z = 23:59:59 del 30/10 en Buenos Aires.
    with freeze_time("2026-10-31 02:59:59", tz_offset=0):
        assert hoy_operativo() == date(2026, 10, 30)


def test_hoy_operativo_despues_de_medianoche_local():
    from app.servicios.caja_servicio import hoy_operativo

    with freeze_time("2026-10-31 03:00:00", tz_offset=0):
        assert hoy_operativo() == date(2026, 10, 31)


@pytest.mark.parametrize("instante,esperado", [
    ("2026-10-31 01:00:00", date(2026, 10, 30)),   # 01:00Z = 22:00 del 30/10 local
    ("2026-10-31 12:00:00", date(2026, 10, 31)),
    ("2026-11-01 02:00:00", date(2026, 10, 31)),
    ("2026-11-01 03:00:01", date(2026, 11, 1)),
])
def test_hoy_operativo_a_las_01_utc_sigue_dia_anterior(instante, esperado):
    from app.servicios.caja_servicio import hoy_operativo

    with freeze_time(instante, tz_offset=0):
        assert hoy_operativo() == esperado


def test_hoy_operativo_respeta_la_zona_configurada(monkeypatch):
    from app.servicios.caja_servicio import hoy_operativo

    monkeypatch.setenv("TZ", "UTC")
    with freeze_time("2026-10-31 02:59:59", tz_offset=0):
        assert hoy_operativo() == date(2026, 10, 31)


@pytest.mark.asyncio
async def test_operable_sin_caja(sesion_pg):
    cs, repos, _, _ = await escenario_caja(sesion_pg)
    assert await cs._caja_operable(repos, HOY) is None


@pytest.mark.asyncio
async def test_operable_con_pendiente_409(sesion_pg):
    cs, repos, m, _ = await escenario_caja(sesion_pg)
    await crear_caja(sesion_pg, m, AYER)
    with pytest.raises(cs.ConflictoError):
        await cs._caja_operable(repos, HOY)


@pytest.mark.asyncio
async def test_operable_hoy_cerrada_409(sesion_pg):
    cs, repos, m, _ = await escenario_caja(sesion_pg)
    await crear_caja(sesion_pg, m, HOY, estado="cerrada")
    with pytest.raises(cs.ConflictoError):
        await cs._caja_operable(repos, HOY)


@pytest.mark.asyncio
async def test_operable_hoy_abierta(sesion_pg):
    cs, repos, m, _ = await escenario_caja(sesion_pg)
    await crear_caja(sesion_pg, m, HOY)
    assert await cs._caja_operable(repos, HOY) is None


@pytest.mark.asyncio
async def test_operable_con_anteriores_cerradas(sesion_pg):
    cs, repos, m, _ = await escenario_caja(sesion_pg)
    await crear_caja(sesion_pg, m, AYER, estado="cerrada")
    assert await cs._caja_operable(repos, HOY) is None
