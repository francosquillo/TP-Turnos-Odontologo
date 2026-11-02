"""C-11 tasks 4.1 a 4.3: generar, revisar, presentar y descartar liquidaciones.

Las funciones puras (límites del período, agrupación, monto de fila) corren siempre; el resto
usa Postgres real (skip sin Docker). Datos ficticios.
"""
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c11_helpers import (  # noqa: E402
    actor_admin, actor_odontologo, actor_secretaria, aceptar_presupuesto, asignar_plan,
    crear_arancel, crear_os, crear_plan, sembrar_c11,
)
from db_utils import sesion_pg  # noqa: E402, F401

BA = ZoneInfo("America/Argentina/Buenos_Aires")
OCTUBRE = date(2026, 10, 1)


# --- funciones puras (sin DB) ---------------------------------------------------------------------

def test_limites_periodo_son_el_mes_completo_en_la_zona():
    from app.servicios.liquidacion_servicio import limites_periodo

    inicio, fin = limites_periodo(date(2026, 10, 1), BA)
    assert inicio == datetime(2026, 10, 1, 3, 0, tzinfo=timezone.utc)
    assert fin == datetime(2026, 11, 1, 3, 0, tzinfo=timezone.utc)


def test_limites_periodo_diciembre_cruza_de_anio():
    from app.servicios.liquidacion_servicio import limites_periodo

    inicio, fin = limites_periodo(date(2026, 12, 1), BA)
    assert (inicio.year, inicio.month) == (2026, 12) and (fin.year, fin.month, fin.day) == (2027, 1, 1)


def test_borde_31_oct_2330_buenos_aires_pertenece_a_octubre_aunque_en_utc_sea_noviembre():
    from app.servicios.liquidacion_servicio import limites_periodo

    instante = datetime(2026, 10, 31, 23, 30, tzinfo=BA)
    assert instante.astimezone(timezone.utc).month == 11
    inicio, fin = limites_periodo(OCTUBRE, BA)
    assert inicio <= instante < fin
    # Un minuto después de la medianoche local ya es noviembre.
    assert not (inicio <= datetime(2026, 11, 1, 0, 1, tzinfo=BA) < fin)


def test_monto_de_fila_usa_lo_congelado_y_es_cero_sin_arancel():
    from app.servicios.liquidacion_servicio import monto_de_fila

    assert monto_de_fila(5, Decimal("10500.00")) == Decimal("10500.00")
    assert monto_de_fila(5, Decimal("0")) == Decimal("0.00")
    assert monto_de_fila(None, Decimal("10500.00")) == Decimal("0.00")
    assert monto_de_fila(5, None) == Decimal("0.00")


def test_armar_planes_agrupa_con_subtotal_y_marca_revision():
    from app.repos.liquidacion_repo import FilaDetalle
    from app.servicios.liquidacion_servicio import armar_planes

    def fila(i, plan_id, plan, arancel, monto):
        return FilaDetalle(
            item_id=i, item_presupuesto_id=100 + i, plan_id=plan_id, plan_nombre=plan,
            arancel_id=arancel, fecha_prestacion=OCTUBRE, monto=Decimal(monto),
            paciente_nombre="Ficticia, Ana", codigo="N-1", descripcion="x", cantidad=1,
            profesional_id=1)

    planes = armar_planes([
        fila(1, 1, "Base", 9, "100.00"), fila(2, 1, "Base", None, "0.00"),
        fila(3, 2, "Plus", 9, "50.50")])
    assert [(p.plan_nombre, p.subtotal, len(p.items)) for p in planes] == [
        ("Base", Decimal("100.00"), 2), ("Plus", Decimal("50.50"), 1)]
    assert [i.revision for i in planes[0].items] == [False, True]


# --- generación (PG) ---------------------------------------------------------------------------------

async def _generar(m, repos_liq, os_=None, periodo=OCTUBRE):
    from app.esquemas.liquidacion import GenerarLiquidacionIn
    from app.servicios import liquidacion_servicio as ls

    return await ls.generar(
        repos_liq, actor_admin(m), GenerarLiquidacionIn(os_id=(os_ or m.os).id, periodo=periodo))


def _repos(sesion):
    from app.servicios import liquidacion_servicio as ls

    return ls.LiquidacionRepos.de_sesion(sesion)


@pytest.mark.asyncio
async def test_generar_agrupa_por_plan_y_calcula_el_total(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    # El plan cambia entre presupuestos: cada uno congela el suyo.
    await aceptar_presupuesto(sesion_pg, m, [(m.h2, "OBT-001", 1)], plan=m.plan_plus)
    liq = await _generar(m, _repos(sesion_pg))
    assert liq.estado == "borrador" and liq.periodo == OCTUBRE
    assert {p.plan_nombre: p.subtotal for p in liq.planes} == {
        "Plan Base": Decimal("10500.00"), "Plan Plus": Decimal("15000.00")}
    assert liq.total == Decimal("25500.00")


@pytest.mark.asyncio
async def test_generar_incluye_prestaciones_del_borde_de_mes_en_buenos_aires(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    en_ba = datetime(2026, 10, 31, 23, 30, tzinfo=BA)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base, ahora=en_ba)
    octubre = await _generar(m, _repos(sesion_pg))
    assert octubre.cantidad_items == 1
    assert octubre.planes[0].items[0].fecha_prestacion == date(2026, 10, 31)


@pytest.mark.asyncio
async def test_generar_noviembre_no_ve_lo_aceptado_el_31_de_octubre_local(sesion_pg):
    from app.servicios import liquidacion_servicio as ls

    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base,
                              ahora=datetime(2026, 10, 31, 23, 30, tzinfo=BA))
    with pytest.raises(ls.ConflictoError):
        await _generar(m, _repos(sesion_pg), periodo=date(2026, 11, 1))


@pytest.mark.asyncio
async def test_generar_solo_toma_la_obra_social_pedida(sesion_pg):
    from app.servicios import liquidacion_servicio as ls

    m = await sembrar_c11(sesion_pg)
    otra = await crear_os(sesion_pg, "Otra OS")
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    with pytest.raises(ls.ConflictoError):
        await _generar(m, _repos(sesion_pg), os_=otra)


@pytest.mark.asyncio
async def test_generar_excluye_cargo_anulado_y_paciente_sin_plan(sesion_pg):
    from app.servicios import cuenta_servicio as cu
    from app.servicios import liquidacion_servicio as ls

    m = await sembrar_c11(sesion_pg)
    anulado, _ = await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    cargo_id = await sesion_pg.scalar(sa.text(
        "SELECT id FROM movimiento WHERE presupuesto_id = :p AND tipo = 'cargo'"),
        {"p": anulado.id})
    await cu.anular_cargo(_repos(sesion_pg).caja.base, actor_admin(m), m.ana.id, cargo_id, "x")
    await asignar_plan(sesion_pg, m.ana, None)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "CON-001", 1)])
    with pytest.raises(ls.ConflictoError):
        await _generar(m, _repos(sesion_pg))


@pytest.mark.asyncio
async def test_generar_dos_veces_el_mismo_periodo_409_y_no_crea_filas(sesion_pg):
    from app.servicios import liquidacion_servicio as ls

    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    await _generar(m, _repos(sesion_pg))
    antes = await sesion_pg.scalar(sa.text("SELECT count(*) FROM item_liquidacion"))
    with pytest.raises(ls.ConflictoError):
        await _generar(m, _repos(sesion_pg))
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM item_liquidacion")) == antes
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM liquidacion")) == 1


@pytest.mark.asyncio
async def test_prestacion_nueva_en_periodo_ya_liquidado_crea_otra_liquidacion(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    primera = await _generar(m, _repos(sesion_pg))
    await aceptar_presupuesto(sesion_pg, m, [(m.h2, "OBT-001", 1)], plan=m.plan_base)
    segunda = await _generar(m, _repos(sesion_pg))
    assert primera.id != segunda.id and segunda.cantidad_items == 1
    assert segunda.total == Decimal("10500.00")


@pytest.mark.asyncio
async def test_generar_con_obra_social_inexistente_404(sesion_pg):
    from app.esquemas.liquidacion import GenerarLiquidacionIn
    from app.servicios import liquidacion_servicio as ls

    m = await sembrar_c11(sesion_pg)
    with pytest.raises(ls.NoEncontradoError):
        await ls.generar(_repos(sesion_pg), actor_admin(m),
                         GenerarLiquidacionIn(os_id=999999, periodo=OCTUBRE))


@pytest.mark.asyncio
@pytest.mark.parametrize("quien", ["secretaria", "odontologo"])
async def test_generar_solo_admin(sesion_pg, quien):
    from app.esquemas.liquidacion import GenerarLiquidacionIn
    from app.servicios import liquidacion_servicio as ls

    m = await sembrar_c11(sesion_pg)
    actor = actor_secretaria(m) if quien == "secretaria" else actor_odontologo(m)
    with pytest.raises(ls.AccesoDenegadoError):
        await ls.generar(_repos(sesion_pg), actor,
                         GenerarLiquidacionIn(os_id=m.os.id, periodo=OCTUBRE))


# --- revisión y regeneración (4.2) --------------------------------------------------------------------

@pytest.mark.asyncio
async def test_item_sin_arancel_es_revision_con_monto_cero_y_no_suma(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1), (m.h2, "PRO-001", 1)],
                              plan=m.plan_base)
    liq = await _generar(m, _repos(sesion_pg))
    filas = [i for p in liq.planes for i in p.items]
    revision = [i for i in filas if i.revision]
    assert len(revision) == 1 and revision[0].monto == Decimal("0.00")
    assert liq.total == Decimal("10500.00") and liq.cantidad_revision == 1


@pytest.mark.asyncio
async def test_arancel_retroactivo_no_vuelve_liquidable_una_fila_en_revision(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "PRO-001", 1)], plan=m.plan_base)
    # Después de aceptar aparece un arancel que cubre la fecha de la prestación.
    await crear_arancel(sesion_pg, m.plan_base, "N-002", "400.00", desde=date(2026, 1, 1))
    liq = await _generar(m, _repos(sesion_pg))
    (fila,) = [i for p in liq.planes for i in p.items]
    assert fila.revision is True and fila.monto == Decimal("0.00") and liq.total == Decimal("0.00")


@pytest.mark.asyncio
async def test_cambio_de_plan_posterior_conserva_el_plan_congelado(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    await asignar_plan(sesion_pg, m.ana, m.plan_plus)
    liq = await _generar(m, _repos(sesion_pg))
    assert [p.plan_nombre for p in liq.planes] == ["Plan Base"]
    assert liq.total == Decimal("10500.00")


@pytest.mark.asyncio
async def test_arancel_cambiado_despues_de_aceptar_no_altera_la_fila(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    m.ar_obt.vigencia_hasta = date(2026, 10, 14)
    await crear_arancel(sesion_pg, m.plan_base, "N-003", "1.00", desde=date(2026, 10, 15))
    liq = await _generar(m, _repos(sesion_pg))
    assert liq.total == Decimal("10500.00")


# --- presentar y descartar (4.3) --------------------------------------------------------------------

@pytest.mark.asyncio
async def test_presentar_deja_autor_y_fecha_y_no_se_repite(sesion_pg):
    from app.servicios import liquidacion_servicio as ls

    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    liq = await _generar(m, _repos(sesion_pg))
    presentada = await ls.presentar(_repos(sesion_pg), actor_admin(m), liq.id)
    assert presentada.estado == "presentada" and presentada.presentada_at is not None
    with pytest.raises(ls.ConflictoError):
        await ls.presentar(_repos(sesion_pg), actor_admin(m), liq.id)


@pytest.mark.asyncio
async def test_descartar_borrador_libera_las_prestaciones(sesion_pg):
    from app.servicios import liquidacion_servicio as ls

    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    liq = await _generar(m, _repos(sesion_pg))
    await ls.descartar(_repos(sesion_pg), actor_admin(m), liq.id)
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM liquidacion")) == 0
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM item_liquidacion")) == 0
    nueva = await _generar(m, _repos(sesion_pg))
    assert nueva.cantidad_items == 1


@pytest.mark.asyncio
async def test_descartar_presentada_409_y_no_cambia_nada(sesion_pg):
    from app.servicios import liquidacion_servicio as ls

    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    liq = await _generar(m, _repos(sesion_pg))
    await ls.presentar(_repos(sesion_pg), actor_admin(m), liq.id)
    with pytest.raises(ls.ConflictoError):
        await ls.descartar(_repos(sesion_pg), actor_admin(m), liq.id)
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM item_liquidacion")) == 1


@pytest.mark.asyncio
async def test_anular_cargo_tras_descartar_el_borrador_funciona(sesion_pg):
    from app.servicios import cuenta_servicio as cu
    from app.servicios import liquidacion_servicio as ls

    m = await sembrar_c11(sesion_pg)
    p, _ = await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    cargo_id = await sesion_pg.scalar(sa.text(
        "SELECT id FROM movimiento WHERE presupuesto_id = :p AND tipo = 'cargo'"), {"p": p.id})
    liq = await _generar(m, _repos(sesion_pg))
    with pytest.raises(cu.ConflictoError):
        await cu.anular_cargo(_repos(sesion_pg).caja.base, actor_admin(m), m.ana.id, cargo_id, "x")
    await ls.descartar(_repos(sesion_pg), actor_admin(m), liq.id)
    anulacion = await cu.anular_cargo(
        _repos(sesion_pg).caja.base, actor_admin(m), m.ana.id, cargo_id, "x")
    assert anulacion.monto == Decimal("-15000.00")


# --- vista del odontólogo (R) ----------------------------------------------------------------------------

async def _presupuesto_de_b(sesion, m):
    """Presupuesto aceptado de B para Beto, insertado directo (el vínculo clínico no importa)."""
    from app.modelos import ItemPresupuesto, Presupuesto

    p = Presupuesto(
        paciente_id=m.beto.id, profesional_id=m.prof_b.id, estado="aceptado",
        total=Decimal("15000.00"), plan_id=m.plan_base.id,
        decidido_at=datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc))
    sesion.add(p)
    await sesion.flush()
    sesion.add(ItemPresupuesto(
        presupuesto_id=p.id, hallazgo_id=m.h3.id, tratamiento_id=m.trat["OBT-001"].id,
        cantidad=1, precio=Decimal("15000.00"), arancel_id=m.ar_obt.id,
        cubierto=Decimal("10500.00")))
    await sesion.flush()


@pytest.mark.asyncio
async def test_odontologo_ve_solo_las_filas_de_sus_presupuestos(sesion_pg):
    from app.servicios import liquidacion_servicio as ls

    m = await sembrar_c11(sesion_pg)
    await aceptar_presupuesto(sesion_pg, m, [(m.h1, "OBT-001", 1)], plan=m.plan_base)
    await _presupuesto_de_b(sesion_pg, m)
    liq = await _generar(m, _repos(sesion_pg))
    assert liq.cantidad_items == 2
    propia = await ls.obtener(_repos(sesion_pg), actor_odontologo(m), liq.id)
    assert propia.cantidad_items == 1 and propia.total == Decimal("10500.00")
    ajena = await ls.obtener(_repos(sesion_pg), actor_odontologo(m, b=True), liq.id)
    assert ajena.cantidad_items == 1
    assert {i.paciente_nombre for p in propia.planes for i in p.items} != {
        i.paciente_nombre for p in ajena.planes for i in p.items}
    listado = await ls.listar(_repos(sesion_pg), actor_odontologo(m))
    assert [x.cantidad_items for x in listado] == [1]


@pytest.mark.asyncio
async def test_odontologo_sin_filas_propias_recibe_404_y_secretaria_403(sesion_pg):
    from app.servicios import liquidacion_servicio as ls

    m = await sembrar_c11(sesion_pg)
    await _presupuesto_de_b(sesion_pg, m)
    liq = await _generar(m, _repos(sesion_pg))
    with pytest.raises(ls.NoEncontradoError):
        await ls.obtener(_repos(sesion_pg), actor_odontologo(m), liq.id)
    with pytest.raises(ls.AccesoDenegadoError):
        await ls.obtener(_repos(sesion_pg), actor_secretaria(m), liq.id)
