"""C-10 grupos 5.1 y 5.2: cierre de caja sobre PG real (D-07, D-11, D-12).

El servidor calcula `total_sistema` y la diferencia; el cierre es definitivo. Datos
ficticios; `freezegun` para la hora real de cierre.
"""
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from freezegun import freeze_time
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c10_helpers import cobro_in, crear_presupuesto_aceptado, escenario_caja  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

HOY = date(2026, 10, 31)
AYER = date(2026, 10, 30)


def _cierre(caja, contado, motivo=None):
    from app.esquemas.caja import CierreIn

    return CierreIn(caja_id=caja.id, total_contado=Decimal(contado), motivo_diferencia=motivo)


async def _caja_con(sesion, importes, hoy=HOY):
    """Caja abierta con un cobro por importe; devuelve (cs, repos, m, a, caja, cobros)."""
    cs, repos, m, a = await escenario_caja(sesion)
    cobros = []
    for importe in importes:
        p, _ = await crear_presupuesto_aceptado(sesion, m, total="5000.00")
        cobro, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, importe), hoy=hoy)
        cobros.append(cobro)
    return cs, repos, m, a, await repos.cajas.por_fecha(hoy), cobros


@pytest.mark.asyncio
async def test_cerrar_sin_diferencia(sesion_pg):
    cs, repos, m, a, caja, _ = await _caja_con(sesion_pg, ["1000.00", "500.00"])
    salida = await cs.cerrar(repos, a["sec"], _cierre(caja, "1500.00"))
    assert salida.estado == "cerrada" and salida.diferencia == Decimal("0.00")
    dump = salida.model_dump(mode="json")
    assert dump["diferencia"] == "0.00" and dump["total_sistema"] == "1500.00"
    assert dump["motivo_diferencia"] is None


@pytest.mark.asyncio
async def test_cerrar_calcula_total_del_servidor(sesion_pg):
    cs, repos, m, a, caja, _ = await _caja_con(sesion_pg, ["700.00", "800.50"])
    salida = await cs.cerrar(repos, a["sec"], _cierre(caja, "1500.50"))
    assert salida.total_sistema == Decimal("1500.50")
    guardada = await repos.cajas.por_fecha(HOY)
    assert guardada.total_sistema == Decimal("1500.50") and guardada.total_contado == Decimal("1500.50")


@pytest.mark.asyncio
async def test_cerrar_incluye_reversiones(sesion_pg):
    cs, repos, m, a, caja, cobros = await _caja_con(sesion_pg, ["800.00", "200.00"])
    await cs.anular_recibo(repos, a["admin"], cobros[1].id, "error de carga", hoy=HOY)
    salida = await cs.cerrar(repos, a["sec"], _cierre(caja, "800.00"))
    assert salida.model_dump(mode="json")["total_sistema"] == "800.00"


@pytest.mark.asyncio
async def test_cerrar_diferencia_sin_motivo_422_sigue_abierta(sesion_pg):
    cs, repos, m, a, caja, _ = await _caja_con(sesion_pg, ["1500.00"])
    with pytest.raises(cs.ValidacionClinicaError):
        await cs.cerrar(repos, a["sec"], _cierre(caja, "1400.00"))
    assert (await repos.cajas.por_fecha(HOY)).estado == "abierta"
    # El importe se conserva del lado del cliente: reintentar con motivo cierra.
    salida = await cs.cerrar(repos, a["sec"], _cierre(caja, "1400.00", "faltante"))
    assert salida.estado == "cerrada"


@pytest.mark.asyncio
async def test_cerrar_faltante_con_motivo(sesion_pg):
    cs, repos, m, a, caja, _ = await _caja_con(sesion_pg, ["1500.00"])
    salida = await cs.cerrar(repos, a["sec"], _cierre(caja, "1400.00", "billete roto"))
    dump = salida.model_dump(mode="json")
    assert dump["diferencia"] == "-100.00" and dump["motivo_diferencia"] == "billete roto"


@pytest.mark.asyncio
async def test_cerrar_sobrante_con_motivo(sesion_pg):
    cs, repos, m, a, caja, _ = await _caja_con(sesion_pg, ["1500.00"])
    salida = await cs.cerrar(repos, a["sec"], _cierre(caja, "1600.00", "vuelto no entregado"))
    assert salida.model_dump(mode="json")["diferencia"] == "100.00"


@pytest.mark.asyncio
async def test_cerrar_sin_diferencia_ignora_motivo(sesion_pg):
    cs, repos, m, a, caja, _ = await _caja_con(sesion_pg, ["100.00"])
    salida = await cs.cerrar(repos, a["sec"], _cierre(caja, "100.00", "no hacía falta"))
    assert salida.motivo_diferencia is None


@pytest.mark.asyncio
async def test_cerrar_guarda_autor_y_hora(sesion_pg):
    cs, repos, m, a, caja, _ = await _caja_con(sesion_pg, ["100.00"])
    with freeze_time("2026-10-31 20:00:00", tz_offset=0, real_asyncio=True):
        salida = await cs.cerrar(repos, a["sec"], _cierre(caja, "100.00"))
    assert salida.cerrada_por == m.secretaria.id
    assert salida.cerrada_at == datetime(2026, 10, 31, 20, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_cerrar_repetido_409(sesion_pg):
    cs, repos, m, a, caja, _ = await _caja_con(sesion_pg, ["100.00"])
    await cs.cerrar(repos, a["sec"], _cierre(caja, "100.00"))
    with pytest.raises(cs.ConflictoError):
        await cs.cerrar(repos, a["sec"], _cierre(caja, "100.00"))


@pytest.mark.asyncio
async def test_cerrar_inexistente_404(sesion_pg):
    from app.esquemas.caja import CierreIn

    cs, repos, m, a = await escenario_caja(sesion_pg)
    with pytest.raises(cs.NoEncontradoError):
        await cs.cerrar(repos, a["sec"], CierreIn(caja_id=987654, total_contado=Decimal("0")))


@pytest.mark.asyncio
@pytest.mark.parametrize("rol", ["admin", "odo"])
async def test_cerrar_rol_sin_permiso_403(sesion_pg, rol):
    cs, repos, m, a, caja, _ = await _caja_con(sesion_pg, ["100.00"])
    with pytest.raises(cs.AccesoDenegadoError):
        await cs.cerrar(repos, a[rol], _cierre(caja, "100.00"))
    assert (await repos.cajas.por_fecha(HOY)).estado == "abierta"


# --- 5.2 día anterior y desbloqueo --------------------------------------------------------------

@pytest.mark.asyncio
async def test_cerrar_dia_anterior_conserva_fecha(sesion_pg):
    cs, repos, m, a, caja, _ = await _caja_con(sesion_pg, ["300.00"], hoy=AYER)
    with freeze_time("2026-10-31 15:00:00", tz_offset=0, real_asyncio=True):
        salida = await cs.cerrar(repos, a["sec"], _cierre(caja, "300.00"))
    assert salida.fecha == AYER and salida.cerrada_at.date() == HOY


@pytest.mark.asyncio
async def test_cerrar_pendiente_desbloquea_cobro(sesion_pg):
    cs, repos, m, a, caja, _ = await _caja_con(sesion_pg, ["300.00"], hoy=AYER)
    p, _ = await crear_presupuesto_aceptado(sesion_pg, m, total="1000.00")
    with pytest.raises(cs.ConflictoError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    await cs.cerrar(repos, a["sec"], _cierre(caja, "300.00"))
    cobro, creado = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    assert creado and cobro.fecha == HOY


@pytest.mark.asyncio
async def test_caja_cerrada_hoy_no_se_reabre(sesion_pg):
    cs, repos, m, a, caja, _ = await _caja_con(sesion_pg, ["300.00"])
    await cs.cerrar(repos, a["sec"], _cierre(caja, "300.00"))
    p, _ = await crear_presupuesto_aceptado(sesion_pg, m, total="1000.00")
    with pytest.raises(cs.ConflictoError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    caja_id = caja.id
    await sesion_pg.commit()
    with pytest.raises(IntegrityError):
        await sesion_pg.execute(sa.text(
            "UPDATE caja SET estado = 'abierta', total_sistema = NULL, total_contado = NULL, "
            "diferencia = NULL, cerrada_por = NULL, cerrada_at = NULL WHERE id = :i"), {"i": caja_id})
    await sesion_pg.rollback()
    assert (await repos.cajas.por_fecha(HOY)).estado == "cerrada"
