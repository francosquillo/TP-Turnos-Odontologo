"""C-11 tasks 4.4, 4.5 y 4.8: cobro de la liquidación, reversión e ingresos en la caja (D-12..D-15).

Postgres real: locks, índices parciales y triggers de caja solo se prueban ahí. Datos ficticios.
"""
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c10_helpers import crear_caja  # noqa: E402
from c11_helpers import (  # noqa: E402
    actor_admin, actor_secretaria, aceptar_presupuesto, sembrar_c11,
)
from db_utils import sesion_pg  # noqa: E402, F401

OCTUBRE = date(2026, 10, 1)


def _repos(sesion):
    from app.servicios import liquidacion_servicio as ls

    return ls.LiquidacionRepos.de_sesion(sesion)


def _hoy():
    from app.servicios.caja_servicio import hoy_operativo

    return hoy_operativo()


async def _presentada(sesion, codigo="OBT-001"):
    """Mundo con una liquidación `presentada`; devuelve (m, liquidacion_id, total)."""
    from app.esquemas.liquidacion import GenerarLiquidacionIn
    from app.servicios import liquidacion_servicio as ls

    m = await sembrar_c11(sesion)
    await aceptar_presupuesto(sesion, m, [(m.h1, codigo, 1)], plan=m.plan_base)
    liq = await ls.generar(_repos(sesion), actor_admin(m),
                           GenerarLiquidacionIn(os_id=m.os.id, periodo=OCTUBRE))
    liq = await ls.presentar(_repos(sesion), actor_admin(m), liq.id)
    return m, liq.id, liq.total


async def _cobrar(sesion, m, liq_id, medio="transferencia", hoy=None):
    from app.servicios import liquidacion_servicio as ls

    return await ls.cobrar(_repos(sesion), actor_admin(m), liq_id, medio, hoy)


async def _movs(sesion, liq_id):
    return (await sesion.execute(sa.text(
        "SELECT medio, monto, motivo, caja_id FROM movimiento_caja "
        "WHERE liquidacion_id = :l ORDER BY id"), {"l": liq_id})).all()


# --- 4.4 cobrar --------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cobrar_registra_el_ingreso_por_el_total_y_pasa_a_cobrada(sesion_pg):
    m, liq_id, total = await _presentada(sesion_pg)
    cobrada = await _cobrar(sesion_pg, m, liq_id)
    assert cobrada.estado == "cobrada" and cobrada.cobrada_at is not None
    ((medio, monto, motivo, _),) = await _movs(sesion_pg, liq_id)
    assert (medio, monto, motivo) == ("transferencia", total, None)
    assert total == Decimal("10500.00")


@pytest.mark.asyncio
async def test_cobrar_abre_la_caja_de_hoy_con_el_autor(sesion_pg):
    m, liq_id, _ = await _presentada(sesion_pg)
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM caja")) == 0
    await _cobrar(sesion_pg, m, liq_id)
    fecha, abierta_por, estado = (await sesion_pg.execute(sa.text(
        "SELECT fecha, abierta_por, estado FROM caja"))).one()
    assert (fecha, abierta_por, estado) == (_hoy(), m.admin.id, "abierta")


@pytest.mark.asyncio
async def test_cobrar_con_caja_pendiente_409_y_sigue_presentada(sesion_pg):
    from app.servicios import liquidacion_servicio as ls

    m, liq_id, _ = await _presentada(sesion_pg)
    await crear_caja(sesion_pg, m, _hoy() - timedelta(days=1))
    with pytest.raises(ls.ConflictoError):
        await _cobrar(sesion_pg, m, liq_id)
    assert await _movs(sesion_pg, liq_id) == []
    assert await sesion_pg.scalar(sa.text(
        "SELECT estado FROM liquidacion WHERE id = :l"), {"l": liq_id}) == "presentada"


@pytest.mark.asyncio
async def test_cobrar_con_la_caja_de_hoy_cerrada_409(sesion_pg):
    from app.servicios import liquidacion_servicio as ls

    m, liq_id, _ = await _presentada(sesion_pg)
    await crear_caja(sesion_pg, m, _hoy(), estado="cerrada")
    with pytest.raises(ls.ConflictoError):
        await _cobrar(sesion_pg, m, liq_id)
    assert await _movs(sesion_pg, liq_id) == []


@pytest.mark.asyncio
async def test_cobrar_un_borrador_409_sin_movimiento(sesion_pg):
    from app.esquemas.liquidacion import GenerarLiquidacionIn
    from app.servicios import liquidacion_servicio as ls

    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    borrador = await ls.generar(_repos(sesion_pg), actor_admin(m),
                                GenerarLiquidacionIn(os_id=m.os.id, periodo=OCTUBRE))
    with pytest.raises(ls.ConflictoError):
        await _cobrar(sesion_pg, m, borrador.id)
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM movimiento_caja")) == 0


@pytest.mark.asyncio
async def test_cobrar_con_total_cero_409(sesion_pg):
    from app.servicios import liquidacion_servicio as ls

    m, liq_id, total = await _presentada(sesion_pg, codigo="PRO-001")  # sin arancel: revisión
    assert total == Decimal("0.00")
    with pytest.raises(ls.ConflictoError):
        await _cobrar(sesion_pg, m, liq_id)


@pytest.mark.asyncio
async def test_doble_cobro_409_y_un_solo_ingreso(sesion_pg):
    from app.servicios import liquidacion_servicio as ls

    m, liq_id, _ = await _presentada(sesion_pg)
    await _cobrar(sesion_pg, m, liq_id)
    with pytest.raises(ls.ConflictoError):
        await _cobrar(sesion_pg, m, liq_id)
    assert len(await _movs(sesion_pg, liq_id)) == 1


@pytest.mark.asyncio
async def test_fallo_parcial_deja_la_liquidacion_presentada(sesion_pg, monkeypatch):
    from app.servicios import liquidacion_servicio as ls

    m, liq_id, _ = await _presentada(sesion_pg)
    repos = _repos(sesion_pg)

    async def _falla(**datos):
        raise sa.exc.IntegrityError("x", {}, Exception("falla simulada"))

    monkeypatch.setattr(repos.cajas, "crear_movimiento", _falla)
    with pytest.raises(ls.ConflictoError):
        await ls.cobrar(repos, actor_admin(m), liq_id, "efectivo")
    estado = await sesion_pg.scalar(sa.text(
        "SELECT estado FROM liquidacion WHERE id = :l"), {"l": liq_id})
    assert estado == "presentada" and await _movs(sesion_pg, liq_id) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("quien", ["secretaria", "odontologo"])
async def test_cobrar_solo_admin(sesion_pg, quien):
    from c11_helpers import actor_odontologo
    from app.servicios import liquidacion_servicio as ls

    m, liq_id, _ = await _presentada(sesion_pg)
    actor = actor_secretaria(m) if quien == "secretaria" else actor_odontologo(m)
    with pytest.raises(ls.AccesoDenegadoError):
        await ls.cobrar(_repos(sesion_pg), actor, liq_id, "efectivo")


@pytest.mark.asyncio
async def test_cobrar_no_expone_ni_exige_clave_de_idempotencia_ni_recibo(sesion_pg):
    m, liq_id, _ = await _presentada(sesion_pg)
    await _cobrar(sesion_pg, m, liq_id)
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM recibo")) == 0
    assert await sesion_pg.scalar(sa.text(
        "SELECT recibo_id IS NULL FROM movimiento_caja WHERE liquidacion_id = :l"),
        {"l": liq_id}) is True


# --- 4.5 revertir (R) -------------------------------------------------------------------------------------

async def _revertir(sesion, m, liq_id, motivo="cobro duplicado", hoy=None):
    from app.servicios import liquidacion_servicio as ls

    return await ls.revertir_cobro(_repos(sesion), actor_admin(m), liq_id, motivo, hoy)


@pytest.mark.asyncio
async def test_revertir_resta_en_la_caja_de_hoy_con_el_medio_original(sesion_pg):
    m, liq_id, total = await _presentada(sesion_pg)
    await _cobrar(sesion_pg, m, liq_id, medio="efectivo")
    revertida = await _revertir(sesion_pg, m, liq_id)
    assert revertida.estado == "presentada" and revertida.revertida is True
    ingreso, reversion = await _movs(sesion_pg, liq_id)
    assert (reversion.medio, reversion.monto, reversion.motivo) == (
        "efectivo", -total, "cobro duplicado")
    assert await sesion_pg.scalar(sa.text("SELECT COALESCE(SUM(monto), 0) FROM movimiento_caja")) == 0


@pytest.mark.asyncio
async def test_revertir_un_cobro_de_dia_cerrado_deja_esa_caja_intacta(sesion_pg):
    from app.esquemas.caja import CierreIn
    from app.servicios import caja_servicio as cs

    m, liq_id, total = await _presentada(sesion_pg)
    ayer = _hoy() - timedelta(days=1)
    await _cobrar(sesion_pg, m, liq_id, hoy=ayer)
    caja_ayer = await sesion_pg.scalar(sa.text("SELECT id FROM caja WHERE fecha = :f"), {"f": ayer})
    await cs.cerrar(cs.CajaRepos.de_sesion(sesion_pg), actor_secretaria(m),
                    CierreIn(caja_id=caja_ayer, total_contado=total))
    await _revertir(sesion_pg, m, liq_id)
    ingreso, reversion = await _movs(sesion_pg, liq_id)
    assert ingreso.caja_id == caja_ayer and reversion.caja_id != caja_ayer
    assert await sesion_pg.scalar(sa.text(
        "SELECT total_sistema FROM caja WHERE id = :c"), {"c": caja_ayer}) == total
    assert await sesion_pg.scalar(sa.text(
        "SELECT fecha FROM caja WHERE id = :c"), {"c": reversion.caja_id}) == _hoy()


@pytest.mark.asyncio
async def test_revertir_sin_motivo_es_422_en_el_esquema():
    from pydantic import ValidationError

    from app.esquemas.liquidacion import RevertirCobroIn

    with pytest.raises(ValidationError):
        RevertirCobroIn()


@pytest.mark.asyncio
async def test_doble_reversion_y_cobrar_despues_de_revertir_409(sesion_pg):
    from app.servicios import liquidacion_servicio as ls

    m, liq_id, _ = await _presentada(sesion_pg)
    await _cobrar(sesion_pg, m, liq_id)
    await _revertir(sesion_pg, m, liq_id)
    with pytest.raises(ls.ConflictoError):
        await _revertir(sesion_pg, m, liq_id)
    with pytest.raises(ls.ConflictoError):
        await _cobrar(sesion_pg, m, liq_id)
    assert len(await _movs(sesion_pg, liq_id)) == 2


@pytest.mark.asyncio
async def test_revertir_una_liquidacion_no_cobrada_409(sesion_pg):
    from app.servicios import liquidacion_servicio as ls

    m, liq_id, _ = await _presentada(sesion_pg)
    with pytest.raises(ls.ConflictoError):
        await _revertir(sesion_pg, m, liq_id)


# --- 4.8 GET /caja con ingresos de liquidación ------------------------------------------------------------

@pytest.mark.asyncio
async def test_caja_lista_ingreso_y_reversion_sin_datos_de_pacientes(sesion_pg):
    from app.servicios import caja_servicio as cs

    m, liq_id, total = await _presentada(sesion_pg)
    await _cobrar(sesion_pg, m, liq_id, medio="transferencia")
    await _revertir(sesion_pg, m, liq_id)
    estado = await cs.obtener_caja(cs.CajaRepos.de_sesion(sesion_pg), actor_secretaria(m))
    montos = [i.monto for i in estado.ingresos_liquidacion]
    assert montos == [total, -total]
    primero = estado.ingresos_liquidacion[0]
    assert (primero.obra_social, primero.periodo, primero.medio) == (
        "OS Ficticia Demo", OCTUBRE, "transferencia")
    campos = set(type(primero).model_fields)
    assert not campos & {"paciente", "paciente_id", "paciente_nombre", "presupuesto_id"}
    assert [d.subtotal for d in estado.desglose] == [Decimal("0.00")]


@pytest.mark.asyncio
async def test_cierre_incluye_el_ingreso_de_liquidacion_en_total_y_desglose(sesion_pg):
    from app.esquemas.caja import CierreIn
    from app.servicios import caja_servicio as cs

    m, liq_id, total = await _presentada(sesion_pg)
    await _cobrar(sesion_pg, m, liq_id, medio="transferencia")
    repos = cs.CajaRepos.de_sesion(sesion_pg)
    antes = await cs.obtener_caja(repos, actor_secretaria(m))
    assert antes.caja.total_sistema == total
    assert [(d.medio, d.subtotal) for d in antes.desglose] == [("transferencia", total)]
    cerrada = await cs.cerrar(repos, actor_secretaria(m),
                              CierreIn(caja_id=antes.caja.id, total_contado=total))
    assert cerrada.total_sistema == total and cerrada.diferencia == Decimal("0.00")


@pytest.mark.asyncio
async def test_caja_sin_ingresos_de_liquidacion_devuelve_lista_vacia(sesion_pg):
    from app.servicios import caja_servicio as cs

    m = await sembrar_c11(sesion_pg)
    await crear_caja(sesion_pg, m, _hoy())
    estado = await cs.obtener_caja(cs.CajaRepos.de_sesion(sesion_pg), actor_secretaria(m))
    assert estado.ingresos_liquidacion == []
