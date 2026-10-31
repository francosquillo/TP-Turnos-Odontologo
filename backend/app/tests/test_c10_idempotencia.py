"""C-10 grupos 4.7 y 4.8: idempotencia del cobro por clave (D-25) sobre PG real.

Mismo contenido devuelve el recibo original sin filas ni número nuevos; otro contenido es
409; los reintentos tardíos no evalúan la caja. Datos ficticios; el día se pasa como `hoy`.
"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c10_helpers import (  # noqa: E402
    clave_nueva, cobro_in, contar, crear_presupuesto_aceptado, escenario_caja,
)
from db_utils import sesion_pg  # noqa: E402, F401

HOY = date(2026, 10, 31)
AYER = date(2026, 10, 30)


async def _listo(sesion, total="1000.00"):
    cs, repos, m, a = await escenario_caja(sesion)
    p, cuenta = await crear_presupuesto_aceptado(sesion, m, total=total)
    return cs, repos, m, a, p, cuenta


async def _filas(sesion):
    return {t: await contar(sesion, t) for t in ("recibo", "movimiento", "movimiento_caja", "caja")}


# --- 4.7 secuencial -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_misma_clave_mismo_contenido_devuelve_original(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    datos = cobro_in(p, "400.00")
    primero, creado1 = await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    segundo, creado2 = await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    assert (creado1, creado2) == (True, False)
    assert segundo.model_dump() == primero.model_dump()


@pytest.mark.asyncio
async def test_misma_clave_no_crea_filas(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    datos = cobro_in(p, "400.00")
    await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    antes = await _filas(sesion_pg)
    saldo = await repos.cuentas.pendiente_de_presupuesto(p.id)
    await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    assert await _filas(sesion_pg) == antes
    assert await repos.cuentas.pendiente_de_presupuesto(p.id) == saldo == Decimal("600.00")


@pytest.mark.asyncio
async def test_misma_clave_no_consume_numero(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    datos = cobro_in(p, "100.00")
    await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    siguiente, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    assert siguiente.numero == 2


@pytest.mark.asyncio
async def test_misma_clave_monto_equivalente_es_reintento(sesion_pg):
    from app.esquemas.caja import CobroIn

    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    clave = clave_nueva()
    primero, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "400.00", clave=clave), hoy=HOY)
    equivalente = CobroIn(presupuesto_id=p.id, monto=Decimal("400"), medio="efectivo",
                          clave_idempotencia=clave)
    segundo, creado = await cs.cobrar(repos, a["sec"], equivalente, hoy=HOY)
    assert creado is False and segundo.id == primero.id


@pytest.mark.asyncio
@pytest.mark.parametrize("cambio", ["presupuesto", "monto", "medio"])
async def test_misma_clave_otro_contenido_409_sin_filas(sesion_pg, cambio):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    otro, _ = await crear_presupuesto_aceptado(sesion_pg, m, total="1000.00")
    clave = clave_nueva()
    await cs.cobrar(repos, a["sec"], cobro_in(p, "400.00", clave=clave), hoy=HOY)
    antes = await _filas(sesion_pg)
    distinto = {
        "presupuesto": cobro_in(otro, "400.00", clave=clave),
        "monto": cobro_in(p, "400.01", clave=clave),
        "medio": cobro_in(p, "400.00", medio="transferencia", clave=clave),
    }[cambio]
    with pytest.raises(cs.ConflictoError):
        await cs.cobrar(repos, a["sec"], distinto, hoy=HOY)
    assert await _filas(sesion_pg) == antes
    siguiente, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    assert siguiente.numero == 2


@pytest.mark.asyncio
async def test_otra_clave_mismo_contenido_crea_otro_recibo(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    uno, c1 = await cs.cobrar(repos, a["sec"], cobro_in(p, "400.00"), hoy=HOY)
    dos, c2 = await cs.cobrar(repos, a["sec"], cobro_in(p, "400.00"), hoy=HOY)
    assert (c1, c2) == (True, True) and (uno.numero, dos.numero) == (1, 2)


@pytest.mark.asyncio
async def test_clave_de_cobro_rechazado_sigue_libre(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg, total="600.00")
    clave = clave_nueva()
    with pytest.raises(cs.ValidacionClinicaError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "600.01", clave=clave), hoy=HOY)
    cobro, creado = await cs.cobrar(repos, a["sec"], cobro_in(p, "600.00", clave=clave), hoy=HOY)
    assert creado and cobro.numero == 1


@pytest.mark.asyncio
async def test_colision_unique_409_sin_consumir_numero(sesion_pg, monkeypatch):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    clave = clave_nueva()
    await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00", clave=clave), hoy=HOY)
    antes = await _filas(sesion_pg)

    async def _no_la_ve(_clave):
        return None

    monkeypatch.setattr(repos.recibos, "por_clave", _no_la_ve)
    with pytest.raises(cs.ConflictoError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00", clave=clave), hoy=HOY)
    monkeypatch.undo()
    assert await _filas(sesion_pg) == antes
    siguiente, _ = await cs.cobrar(repos, a["sec"], cobro_in(p, "100.00"), hoy=HOY)
    assert siguiente.numero == 2


@pytest.mark.asyncio
async def test_reintento_sin_permiso_403(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    datos = cobro_in(p, "100.00")
    await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    for rol in ("admin", "odo"):
        with pytest.raises(cs.AccesoDenegadoError):
            await cs.cobrar(repos, a[rol], datos, hoy=HOY)


# --- 4.8 reintentos tardíos -----------------------------------------------------------------------

async def _cerrar(cs, repos, a, fecha, contado):
    from app.esquemas.caja import CierreIn

    caja = await repos.cajas.por_fecha(fecha)
    await cs.cerrar(repos, a["sec"], CierreIn(caja_id=caja.id, total_contado=Decimal(contado)))
    return caja


@pytest.mark.asyncio
async def test_reintento_caja_cerrada_devuelve_original(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    datos = cobro_in(p, "400.00")
    original, _ = await cs.cobrar(repos, a["sec"], datos, hoy=AYER)
    caja = await _cerrar(cs, repos, a, AYER, "400.00")
    segundo, creado = await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    assert creado is False and segundo.id == original.id and segundo.fecha == AYER
    caja = await repos.cajas.por_fecha(AYER)
    assert caja.estado == "cerrada" and caja.total_sistema == Decimal("400.00")


@pytest.mark.asyncio
async def test_reintento_con_caja_pendiente_devuelve_original(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    datos = cobro_in(p, "400.00")
    original, _ = await cs.cobrar(repos, a["sec"], datos, hoy=AYER)  # AYER queda abierta
    with pytest.raises(cs.ConflictoError):  # un cobro nuevo sí está bloqueado
        await cs.cobrar(repos, a["sec"], cobro_in(p, "10.00"), hoy=HOY)
    segundo, creado = await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    assert creado is False and segundo.id == original.id


@pytest.mark.asyncio
async def test_reintento_hoy_cerrada_devuelve_original(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    datos = cobro_in(p, "400.00")
    original, _ = await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    await _cerrar(cs, repos, a, HOY, "400.00")
    with pytest.raises(cs.ConflictoError):
        await cs.cobrar(repos, a["sec"], cobro_in(p, "10.00"), hoy=HOY)
    segundo, creado = await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    assert creado is False and segundo.id == original.id


@pytest.mark.asyncio
async def test_reintento_recibo_anulado_devuelve_anulado_sin_mover(sesion_pg):
    cs, repos, m, a, p, cuenta = await _listo(sesion_pg)
    datos = cobro_in(p, "400.00")
    original, _ = await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    await cs.anular_recibo(repos, a["admin"], original.id, "error de carga", hoy=HOY)
    antes = await _filas(sesion_pg)
    saldo = await repos.cuentas.saldo(cuenta.id)
    segundo, creado = await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    assert creado is False and segundo.id == original.id
    assert segundo.anulado is True and segundo.motivo_anulacion == "error de carga"
    assert await _filas(sesion_pg) == antes
    assert await repos.cuentas.saldo(cuenta.id) == saldo == Decimal("1000.00")


@pytest.mark.asyncio
async def test_reintento_presupuesto_cobrado_devuelve_original(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg, total="400.00")
    datos = cobro_in(p, "400.00")
    original, _ = await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    assert original.presupuesto_estado == "cobrado"
    segundo, creado = await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    assert creado is False and segundo.id == original.id
    assert segundo.presupuesto_estado == "cobrado"


@pytest.mark.asyncio
async def test_reintento_no_abre_caja(sesion_pg):
    cs, repos, m, a, p, _ = await _listo(sesion_pg)
    datos = cobro_in(p, "400.00")
    await cs.cobrar(repos, a["sec"], datos, hoy=AYER)
    await _cerrar(cs, repos, a, AYER, "400.00")
    assert await contar(sesion_pg, "caja") == 1
    await cs.cobrar(repos, a["sec"], datos, hoy=HOY)
    assert await contar(sesion_pg, "caja") == 1
    assert await repos.cajas.por_fecha(HOY) is None
