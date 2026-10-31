"""C-10 grupos 4.2 a 4.5: servicio de cobro sobre PG real (D-04..D-11, D-15).

El servicio solo hace flush. Datos ficticios; `freezegun` donde importa el día operativo,
y fechas calculadas en Python (nunca el `now()` de la DB).
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

from c10_helpers import (  # noqa: E402
    cobro_in, contar, crear_caja, crear_presupuesto_aceptado, escenario_caja,
)
from db_utils import sesion_pg  # noqa: E402, F401

HOY = date(2026, 10, 31)
AYER = date(2026, 10, 30)


async def _listo(sesion, total="1000.00", **kw):
    cs, repos, m, a = await escenario_caja(sesion)
    p, cuenta = await crear_presupuesto_aceptado(sesion, m, total=total, **kw)
    return cs, repos, m, a, p, cuenta


# --- 4.2 cobro básico -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cobrar_crea_recibo_pago_y_movimiento_enlazados(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    cobro, creado = await cs.cobrar(repos, a["sec"], cobro_in(p, "400.00"), hoy=HOY)
    assert creado is True and cobro.numero == 1 and cobro.monto == Decimal("400.00")
    assert cobro.fecha == HOY and cobro.presupuesto_id == p.id and cobro.anulado is False
    pago = await repos.cuentas.pago_de_recibo(cobro.id)
    assert pago.tipo == "pago" and pago.monto == Decimal("-400.00")
    assert pago.presupuesto_id == p.id and pago.recibo_id == cobro.id
    fila = (await sesion_pg.execute(sa.text(
        "SELECT recibo_id, monto, medio FROM movimiento_caja"))).one()
    assert fila == (cobro.id, Decimal("400.00"), "efectivo")
    assert await contar(sesion_pg, "recibo") == 1


@pytest.mark.asyncio
async def test_cobrar_baja_el_saldo(sesion_pg):
    cs, repos, m, a, p, cuenta = await _listo(sesion_pg)
    assert await repos.cuentas.saldo(cuenta.id) == Decimal("1000.00")
    await cs.cobrar(repos, a["sec"], cobro_in(p, "400.00"), hoy=HOY)
    assert await repos.cuentas.saldo(cuenta.id) == Decimal("600.00")
    await cs.cobrar(repos, a["sec"], cobro_in(p, "100.50"), hoy=HOY)
    assert await repos.cuentas.saldo(cuenta.id) == Decimal("499.50")


@pytest.mark.asyncio
async def test_cobrar_concepto_sin_phi(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    uno, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    dos, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    assert (await repos.cuentas.pago_de_recibo(uno.id)).concepto == "Recibo 1"
    assert (await repos.cuentas.pago_de_recibo(dos.id)).concepto == "Recibo 2"


@pytest.mark.asyncio
async def test_cobrar_guarda_autor(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    cobro, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    pago = await repos.cuentas.pago_de_recibo(cobro.id)
    movcaja_autor = await sesion_pg.scalar(sa.text("SELECT creado_por FROM movimiento_caja"))
    assert cobro.emitido_por == pago.creado_por == movcaja_autor == m.secretaria.id
    assert cobro.paciente_nombre == "Ana Ficticia"


@pytest.mark.asyncio
async def test_cobrar_abre_caja_con_abierta_por(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    assert await contar(sesion_pg, "caja") == 0
    await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    caja = await repos.cajas.por_fecha(HOY)
    assert caja.estado == "abierta" and caja.abierta_por == m.secretaria.id
    await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    assert await contar(sesion_pg, "caja") == 1


@pytest.mark.asyncio
async def test_cobrar_paciente_de_baja_ok(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    m.ana.deleted_at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    await sesion_pg.flush()
    cobro, creado = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    assert creado and cobro.paciente_id == m.ana.id


@pytest.mark.asyncio
@pytest.mark.parametrize("medio", ["efectivo", "transferencia", "tarjeta_simulada"])
async def test_cobrar_cada_medio_ok(sesion_pg, medio):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    cobro, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "50.00", medio=medio), hoy=HOY)
    assert cobro.medio == medio
    assert await sesion_pg.scalar(sa.text("SELECT medio FROM movimiento_caja")) == medio


@pytest.mark.asyncio
@pytest.mark.parametrize("rol", ["admin", "odo"])
async def test_cobrar_rol_sin_permiso_403(sesion_pg, rol):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    with pytest.raises(cs.AccesoDenegadoError):
        await cs.cobrar(repos, a[rol], cobro_in(p, "50.00"), hoy=HOY)
    assert await contar(sesion_pg, "recibo") == 0 and await contar(sesion_pg, "caja") == 0


# --- 4.3 validaciones -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cobrar_sobrepago_422(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg, total="600.00")
    with pytest.raises(cs.ValidacionClinicaError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "600.01"), hoy=HOY)
    assert await contar(sesion_pg, "recibo") == 0
    assert await contar(sesion_pg, "movimiento_caja") == 0
    assert await contar(sesion_pg, "movimiento") == 1  # solo el cargo


@pytest.mark.asyncio
async def test_cobrar_sobrepago_tras_un_parcial_422(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg, total="1000.00")
    await cs.cobrar(repos, a["sec"], cobro_in(p, "400.00"), hoy=HOY)
    with pytest.raises(cs.ValidacionClinicaError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "600.01"), hoy=HOY)


@pytest.mark.asyncio
async def test_cobrar_justo_el_pendiente_ok(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg, total="600.00")
    cobro, creado = await cs.cobrar(repos, a["sec"], cobro_in(p, "600.00"), hoy=HOY)
    assert creado and cobro.monto == Decimal("600.00")
    assert await repos.cuentas.pendiente_de_presupuesto(p.id) == Decimal("0.00")


@pytest.mark.asyncio
@pytest.mark.parametrize("estado", ["borrador", "presentado", "rechazado", "cobrado"])
async def test_cobrar_estado_no_aceptado_409(sesion_pg, estado):
    cs, repos, m, a = await escenario_caja(sesion_pg)
    p, _ = await crear_presupuesto_aceptado(sesion_pg, m, estado=estado)
    with pytest.raises(cs.ConflictoError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "10.00"), hoy=HOY)
    assert await contar(sesion_pg, "recibo") == 0 and await contar(sesion_pg, "movimiento_caja") == 0


@pytest.mark.asyncio
async def test_cobrar_cargo_anulado_409(sesion_pg):
    cs, repos, m, a, p, cuenta = await _listo(sesion_pg)
    cargo_id = await sesion_pg.scalar(sa.text("SELECT id FROM movimiento WHERE tipo = 'cargo'"))
    await repos.cuentas.crear_movimiento(
        cuenta.id, tipo="ajuste", monto=Decimal("-1000.00"), concepto="x", motivo="error",
        presupuesto_id=p.id, anula_a_id=cargo_id, creado_por=m.admin.id)
    with pytest.raises(cs.ConflictoError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "10.00"), hoy=HOY)
    assert await contar(sesion_pg, "recibo") == 0


@pytest.mark.asyncio
async def test_cobrar_presupuesto_inexistente_404(sesion_pg):
    from app.esquemas.caja import CobroIn
    from c10_helpers import clave_nueva

    cs, repos, m, a = await escenario_caja(sesion_pg)
    datos = CobroIn(presupuesto_id=987654, monto=Decimal("10.00"), medio="efectivo",
                    clave_idempotencia=clave_nueva())
    with pytest.raises(cs.NoEncontradoError):
        await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    assert await contar(sesion_pg, "recibo") == 0


@pytest.mark.asyncio
async def test_cobrar_presupuesto_de_baja_404(sesion_pg):
    cs, repos, m, a = await escenario_caja(sesion_pg)
    p, _ = await crear_presupuesto_aceptado(sesion_pg, m, estado="borrador", con_cargo=False)
    p.deleted_at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    p.motivo_baja = "duplicado"
    await sesion_pg.flush()
    with pytest.raises(cs.NoEncontradoError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "10.00"), hoy=HOY)


@pytest.mark.asyncio
async def test_cobrar_rechazado_no_consume_numero(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg, total="600.00")
    uno, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    with pytest.raises(cs.ValidacionClinicaError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "9999.00"), hoy=HOY)
    dos, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    assert (uno.numero, dos.numero) == (1, 2)


@pytest.mark.asyncio
async def test_cobrar_falla_final_revierte_todo(sesion_pg, monkeypatch):
    cs, repos, m, a, p, _ = await _listo(sesion_pg, total="600.00")
    await sesion_pg.commit()

    async def _falla(**_):
        raise IntegrityError("falla simulada", {}, Exception("x"))

    monkeypatch.setattr(repos.cajas, "crear_movimiento", _falla)
    with pytest.raises(cs.ConflictoError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "600.00"), hoy=HOY)
    assert await contar(sesion_pg, "recibo") == 0
    assert await contar(sesion_pg, "movimiento_caja") == 0
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM movimiento WHERE tipo = 'pago'")) == 0
    assert await repos.presupuestos.estado_de(p.id) == "aceptado"
    monkeypatch.undo()
    # El número vuelve al contador: el próximo cobro es el 1.
    cobro, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "600.00"), hoy=HOY)
    assert cobro.numero == 1


# --- 4.4 paso a cobrado --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cobrar_total_marca_cobrado(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg, total="1000.00")
    cobro, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "1000.00"), hoy=HOY)
    assert await repos.presupuestos.estado_de(p.id) == "cobrado"
    assert cobro.presupuesto_estado == "cobrado"


@pytest.mark.asyncio
async def test_cobrar_parcial_sigue_aceptado(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg, total="1000.00")
    cobro, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "999.99"), hoy=HOY)
    assert await repos.presupuestos.estado_de(p.id) == "aceptado"
    assert cobro.presupuesto_estado == "aceptado"


@pytest.mark.asyncio
async def test_dos_parciales_marcan_cobrado(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg, total="1000.00")
    primero, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "400.00"), hoy=HOY)
    assert primero.presupuesto_estado == "aceptado"
    segundo, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "600.00", medio="transferencia"), hoy=HOY)
    assert segundo.presupuesto_estado == "cobrado"
    assert await repos.presupuestos.estado_de(p.id) == "cobrado"
    with pytest.raises(cs.ConflictoError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "1.00"), hoy=HOY)


@pytest.mark.asyncio
async def test_cobrar_fallido_no_marca_cobrado(sesion_pg, monkeypatch):
    cs, repos, m, a, p, _ = await _listo(sesion_pg, total="500.00")
    await sesion_pg.commit()

    async def _falla(**_):
        raise IntegrityError("falla simulada", {}, Exception("x"))

    monkeypatch.setattr(repos.cajas, "crear_movimiento", _falla)
    with pytest.raises(cs.ConflictoError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "500.00"), hoy=HOY)
    assert await repos.presupuestos.estado_de(p.id) == "aceptado"


# --- 4.5 bloqueo y día operativo -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cobrar_con_pendiente_409_sin_filas(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    await crear_caja(sesion_pg, m, AYER)
    with pytest.raises(cs.ConflictoError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    assert await contar(sesion_pg, "caja") == 1
    assert await contar(sesion_pg, "recibo") == 0 and await contar(sesion_pg, "movimiento_caja") == 0


@pytest.mark.asyncio
async def test_cobrar_con_caja_de_hoy_cerrada_409(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    await crear_caja(sesion_pg, m, HOY, estado="cerrada")
    with pytest.raises(cs.ConflictoError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    assert await contar(sesion_pg, "recibo") == 0


@pytest.mark.asyncio
async def test_cobrar_dia_sin_caja_previa_ok(sesion_pg):
    """Un día sin movimientos no deja caja ni exige cierre (D-05)."""
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    await crear_caja(sesion_pg, m, date(2026, 10, 28), estado="cerrada")
    cobro, creado = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    assert creado and cobro.fecha == HOY
    assert await contar(sesion_pg, "caja") == 2


@pytest.mark.asyncio
async def test_cobrar_cruza_medianoche_otra_caja(sesion_pg):
    from app.esquemas.caja import CierreIn

    cs, repos, m, a, p, _ = await _listo(sesion_pg, total="1000.00")
    with freeze_time("2026-10-31 02:59:59", tz_offset=0, real_asyncio=True):
        antes, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"))
    assert antes.fecha == date(2026, 10, 30)
    caja_30 = await repos.cajas.por_fecha(date(2026, 10, 30))
    await cs.cerrar(repos, a["sec"], CierreIn(caja_id=caja_30.id, total_contado=Decimal("100.00")))
    with freeze_time("2026-10-31 03:00:00", tz_offset=0, real_asyncio=True):
        despues, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"))
    assert despues.fecha == date(2026, 10, 31)
    assert (await repos.cajas.por_fecha(date(2026, 10, 30))).estado == "cerrada"
    assert (await repos.cajas.por_fecha(date(2026, 10, 31))).estado == "abierta"


@pytest.mark.asyncio
async def test_numeracion_continua_entre_dias(sesion_pg):
    from app.esquemas.caja import CierreIn

    cs, repos, m, a, p, _ = await _listo(sesion_pg, total="1000.00")
    uno, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=AYER)
    caja = await repos.cajas.por_fecha(AYER)
    await cs.cerrar(repos, a["sec"], CierreIn(caja_id=caja.id, total_contado=Decimal("100.00")))
    dos, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    assert (uno.numero, dos.numero) == (1, 2)
