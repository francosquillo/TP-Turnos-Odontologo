"""C-10 grupos 6.1 a 6.3: anulación de recibos sobre PG real (D-09, D-13).

Contramovimiento en la caja de HOY; una caja cerrada nunca se toca. Datos ficticios;
`freezegun` para la hora de anulación.
"""
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from freezegun import freeze_time

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c10_helpers import (  # noqa: E402
    cobro_in, contar, crear_presupuesto_aceptado, escenario_caja,
)
from db_utils import sesion_pg  # noqa: E402, F401

HOY = date(2026, 10, 31)
AYER = date(2026, 10, 30)
MOTIVO = "cobro cargado dos veces"


async def _cobrado(sesion, monto="400.00", total="1000.00", medio="efectivo", dia=HOY):
    cs, repos, m, a = await escenario_caja(sesion)
    p, cuenta = await crear_presupuesto_aceptado(sesion, m, total=total)
    cobro, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, monto, medio=medio), hoy=dia)
    return cs, repos, m, a, p, cuenta, cobro


async def _cerrar(cs, repos, a, fecha, contado):
    from app.esquemas.caja import CierreIn

    caja = await repos.cajas.por_fecha(fecha)
    await cs.cerrar(repos, a["sec"], CierreIn(caja_id=caja.id, total_contado=Decimal(contado)))


# --- 6.1 anulación básica ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anular_crea_ajuste_opuesto_con_anula_a_id(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg)
    await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    pago = await repos.cuentas.pago_de_recibo(cobro.id)
    ajuste = (await sesion_pg.execute(sa.text(
        "SELECT tipo, monto, anula_a_id, recibo_id, presupuesto_id, motivo, creado_por "
        "FROM movimiento WHERE tipo = 'ajuste'"))).one()
    assert ajuste == ("ajuste", Decimal("400.00"), pago.id, cobro.id, p.id, MOTIVO, m.admin.id)
    assert pago.monto == Decimal("-400.00")  # el original no se toca


@pytest.mark.asyncio
async def test_anular_marca_recibo_conserva_numero(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg)
    salida = await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    assert salida.anulado is True and salida.numero == cobro.numero == 1
    assert salida.monto == Decimal("400.00") and salida.fecha == HOY
    assert await contar(sesion_pg, "recibo") == 1


@pytest.mark.asyncio
async def test_anular_sube_el_saldo(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg)
    assert await repos.cuentas.saldo(cuenta.id) == Decimal("600.00")
    await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    assert await repos.cuentas.saldo(cuenta.id) == Decimal("1000.00")
    assert await repos.cuentas.pendiente_de_presupuesto(p.id) == Decimal("1000.00")


@pytest.mark.asyncio
async def test_anular_guarda_motivo_autor_y_fecha(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg)
    with freeze_time("2026-10-31 18:30:00", tz_offset=0, real_asyncio=True):
        salida = await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    assert salida.motivo_anulacion == MOTIVO and salida.anulado_por == m.admin.id
    assert salida.anulado_at == datetime(2026, 10, 31, 18, 30, tzinfo=timezone.utc)


@pytest.mark.asyncio
@pytest.mark.parametrize("medio", ["efectivo", "transferencia", "tarjeta_simulada"])
async def test_anular_movimiento_caja_negativo_con_medio_original(sesion_pg, medio):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg, medio=medio)
    await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    filas = (await sesion_pg.execute(sa.text(
        "SELECT medio, monto, motivo FROM movimiento_caja ORDER BY monto"))).all()
    assert filas == [(medio, Decimal("-400.00"), MOTIVO), (medio, Decimal("400.00"), None)]


@pytest.mark.asyncio
async def test_anular_concepto_fijo(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg)
    await cs.anular_recibo(repos, a["admin"], cobro.id, "texto libre con datos", hoy=HOY)
    concepto = await sesion_pg.scalar(sa.text("SELECT concepto FROM movimiento WHERE tipo = 'ajuste'"))
    assert concepto == "Anulación del recibo 1"


@pytest.mark.asyncio
async def test_anular_repetido_409(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg)
    await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    antes = (await contar(sesion_pg, "movimiento"), await contar(sesion_pg, "movimiento_caja"))
    with pytest.raises(cs.ConflictoError):
        await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    assert (await contar(sesion_pg, "movimiento"), await contar(sesion_pg, "movimiento_caja")) == antes


@pytest.mark.asyncio
async def test_anular_inexistente_404(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg)
    with pytest.raises(cs.NoEncontradoError):
        await cs.anular_recibo(repos, a["admin"], 987654, MOTIVO, hoy=HOY)


@pytest.mark.asyncio
@pytest.mark.parametrize("rol", ["sec", "odo"])
async def test_anular_rol_sin_permiso_403(sesion_pg, rol):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg)
    with pytest.raises(cs.AccesoDenegadoError):
        await cs.anular_recibo(repos, a[rol], cobro.id, MOTIVO, hoy=HOY)
    assert await contar(sesion_pg, "movimiento_caja") == 1


@pytest.mark.asyncio
async def test_numero_siguiente_tras_anular(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg)
    await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    nuevo, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    assert nuevo.numero == 2


# --- 6.2 reglas de caja -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anular_mismo_dia_misma_caja(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg)
    caja = await repos.cajas.por_fecha(HOY)
    assert await repos.cajas.total(caja.id) == Decimal("400.00")
    await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    assert await repos.cajas.total(caja.id) == Decimal("0.00")
    assert await contar(sesion_pg, "caja") == 1


@pytest.mark.asyncio
async def test_anular_recibo_de_dia_cerrado_no_toca_esa_caja(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg, dia=AYER)
    await _cerrar(cs, repos, a, AYER, "400.00")
    salida = await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    ayer = await repos.cajas.por_fecha(AYER)
    assert ayer.estado == "cerrada" and ayer.total_sistema == Decimal("400.00")
    assert await repos.cajas.total(ayer.id) == Decimal("400.00")
    hoy = await repos.cajas.por_fecha(HOY)
    assert await repos.cajas.total(hoy.id) == Decimal("-400.00")
    assert salida.fecha == AYER  # el recibo sigue emitido en su día


@pytest.mark.asyncio
async def test_anular_abre_caja_de_hoy_con_admin(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg, dia=AYER)
    await _cerrar(cs, repos, a, AYER, "400.00")
    assert await repos.cajas.por_fecha(HOY) is None
    await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    caja = await repos.cajas.por_fecha(HOY)
    assert caja.estado == "abierta" and caja.abierta_por == m.admin.id
    assert await repos.cajas.total(caja.id) == Decimal("-400.00")


@pytest.mark.asyncio
async def test_anular_con_caja_pendiente_409_sin_cambios(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg, dia=AYER)  # AYER queda abierta
    antes = (await contar(sesion_pg, "movimiento"), await contar(sesion_pg, "movimiento_caja"),
             await contar(sesion_pg, "caja"))
    with pytest.raises(cs.ConflictoError):
        await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    assert (await contar(sesion_pg, "movimiento"), await contar(sesion_pg, "movimiento_caja"),
            await contar(sesion_pg, "caja")) == antes
    assert await sesion_pg.scalar(sa.text("SELECT anulado FROM recibo")) is False


@pytest.mark.asyncio
async def test_anular_con_hoy_cerrada_409_sin_cambios(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg)
    await _cerrar(cs, repos, a, HOY, "400.00")
    antes = (await contar(sesion_pg, "movimiento"), await contar(sesion_pg, "movimiento_caja"))
    with pytest.raises(cs.ConflictoError):
        await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    assert (await contar(sesion_pg, "movimiento"), await contar(sesion_pg, "movimiento_caja")) == antes
    assert await sesion_pg.scalar(sa.text("SELECT anulado FROM recibo")) is False


# --- 6.3 estado del presupuesto y saldo a favor ------------------------------------------------------

@pytest.mark.asyncio
async def test_anular_de_cobrado_vuelve_a_aceptado(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg, monto="1000.00")
    assert await repos.presupuestos.estado_de(p.id) == "cobrado"
    await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    assert await repos.presupuestos.estado_de(p.id) == "aceptado"
    assert await repos.cuentas.pendiente_de_presupuesto(p.id) == Decimal("1000.00")
    assert [f.presupuesto_id for f in await repos.cuentas.pendientes_de_paciente(m.ana.id)] == [p.id]


@pytest.mark.asyncio
async def test_anular_de_aceptado_sigue_aceptado(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg, monto="400.00")
    await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    assert await repos.presupuestos.estado_de(p.id) == "aceptado"
    assert await repos.cuentas.pendiente_de_presupuesto(p.id) == Decimal("1000.00")


@pytest.mark.asyncio
async def test_cobrar_de_nuevo_tras_anular_marca_cobrado(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg, monto="1000.00")
    await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    nuevo, creado = await cs.cobrar(repos, a["sec"], cobro_in(p, "1000.00"), hoy=HOY)
    assert creado and nuevo.numero == 2 and nuevo.presupuesto_estado == "cobrado"
    assert await repos.presupuestos.estado_de(p.id) == "cobrado"


async def _anular_cargo(m, a, repos, p, cuenta):
    from app.servicios import cuenta_servicio as cuentas

    cargo_id = await repos.cajas.sesion.scalar(sa.text(
        "SELECT id FROM movimiento WHERE tipo = 'cargo' AND presupuesto_id = :p"), {"p": p.id})
    return await cuentas.anular_cargo(repos.base, a["admin"], m.ana.id, cargo_id, "cargo erróneo")


@pytest.mark.asyncio
async def test_cargo_anulado_con_pago_deja_saldo_a_favor_y_no_cobrable(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg, monto="400.00")
    await _anular_cargo(m, a, repos, p, cuenta)
    assert await repos.cuentas.saldo(cuenta.id) == Decimal("-400.00")
    with pytest.raises(cs.ConflictoError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "10.00"), hoy=HOY)
    assert await repos.cuentas.pendientes_de_paciente(m.ana.id) == []


@pytest.mark.asyncio
async def test_devolucion_por_anular_recibo_deja_saldo_cero(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg, monto="400.00")
    await _anular_cargo(m, a, repos, p, cuenta)
    await cs.anular_recibo(repos, a["admin"], cobro.id, MOTIVO, hoy=HOY)
    assert await repos.cuentas.saldo(cuenta.id) == Decimal("0.00")


@pytest.mark.asyncio
async def test_cobrado_con_cargo_anulado_sigue_cobrado(sesion_pg):
    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg, monto="1000.00")
    await _anular_cargo(m, a, repos, p, cuenta)
    assert await repos.presupuestos.estado_de(p.id) == "cobrado"


@pytest.mark.asyncio
async def test_anular_pago_por_ruta_c09_sigue_409(sesion_pg):
    from app.servicios import cuenta_servicio as cuentas

    cs, repos, m, a, p, cuenta, cobro = await _cobrado(sesion_pg)
    pago = await repos.cuentas.pago_de_recibo(cobro.id)
    with pytest.raises(cuentas.ConflictoError):
        await cuentas.anular_cargo(repos.base, a["admin"], m.ana.id, pago.id, "x")
    assert await sesion_pg.scalar(sa.text("SELECT anulado FROM recibo")) is False
