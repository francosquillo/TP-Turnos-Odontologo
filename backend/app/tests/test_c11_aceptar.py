"""C-11 tasks 3.2 a 3.4: cobertura congelada al aceptar (D-03, D-05) contra PG real.

`aceptar` congela plan, arancel y `cubierto`; con cobertura mayor a cero crea el `ajuste`
negativo en el mismo savepoint del cargo. Sin plan es idéntico a C-09. Datos ficticios.
"""
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c11_helpers import asignar_plan, crear_arancel, sembrar_c11  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

AHORA = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


def _it(hallazgo, tratamiento, cantidad=1):
    from app.esquemas.presupuesto import ItemIn

    return ItemIn(hallazgo_id=hallazgo.id, tratamiento_id=tratamiento.id, cantidad=cantidad)


async def _escenario(sesion):
    from app.servicios import clinica_servicio as cs
    from app.servicios import presupuesto_servicio as ps

    m = await sembrar_c11(sesion)
    repos = ps.PresupuestoRepos.de_sesion(sesion)
    actor = cs.Actor(usuario_id=m.odo_a.id, rol="odontologo", profesional_id=m.prof_a.id)
    return ps, repos, m, actor


async def _presentado(ps, repos, m, actor, items):
    p = await ps.crear(repos, actor, m.ana.id, items, AHORA)
    return await ps.presentar(repos, actor, p.id, AHORA)


async def _movs(sesion, presupuesto_id):
    filas = await sesion.execute(sa.text(
        "SELECT tipo, monto, concepto, recibo_id, anula_a_id FROM movimiento "
        "WHERE presupuesto_id = :p ORDER BY id"), {"p": presupuesto_id})
    return filas.all()


async def _items(sesion, presupuesto_id):
    filas = await sesion.execute(sa.text(
        "SELECT arancel_id, cubierto FROM item_presupuesto WHERE presupuesto_id = :p ORDER BY id"
    ), {"p": presupuesto_id})
    return filas.all()


@pytest.mark.asyncio
async def test_aceptar_con_plan_congela_plan_arancel_y_cubierto(sesion_pg):
    ps, repos, m, actor = await _escenario(sesion_pg)
    await asignar_plan(sesion_pg, m.ana, m.plan_base)
    p = await _presentado(ps, repos, m, actor, [_it(m.h1, m.trat["OBT-001"], 2)])
    p = await ps.aceptar(repos, actor, p.id, AHORA)
    assert p.plan_id == m.plan_base.id and p.estado == "aceptado"
    # Arancel 10500.00 < precio 15000.00, cantidad 2 -> 21000.00 cubiertos.
    assert await _items(sesion_pg, p.id) == [(m.ar_obt.id, Decimal("21000.00"))]


@pytest.mark.asyncio
async def test_aceptar_item_sin_arancel_queda_en_cero_y_los_demas_se_cubren(sesion_pg):
    ps, repos, m, actor = await _escenario(sesion_pg)
    await asignar_plan(sesion_pg, m.ana, m.plan_base)
    p = await _presentado(ps, repos, m, actor, [_it(m.h1, m.trat["OBT-001"]),
                                               _it(m.h2, m.trat["PRO-001"])])
    p = await ps.aceptar(repos, actor, p.id, AHORA)
    assert await _items(sesion_pg, p.id) == [
        (m.ar_obt.id, Decimal("10500.00")), (None, Decimal("0.00"))]


@pytest.mark.asyncio
async def test_aceptar_sin_plan_es_identico_a_c09(sesion_pg):
    ps, repos, m, actor = await _escenario(sesion_pg)
    p = await _presentado(ps, repos, m, actor, [_it(m.h1, m.trat["OBT-001"])])
    p = await ps.aceptar(repos, actor, p.id, AHORA)
    assert p.plan_id is None and p.estado == "aceptado"
    assert await _items(sesion_pg, p.id) == [(None, None)]
    assert [(t, mo) for t, mo, *_ in await _movs(sesion_pg, p.id)] == [
        ("cargo", Decimal("15000.00"))]


@pytest.mark.asyncio
@pytest.mark.parametrize("desactivar", ["plan", "obra"])
async def test_aceptar_con_plan_u_obra_inactivos_se_trata_como_sin_plan(sesion_pg, desactivar):
    ps, repos, m, actor = await _escenario(sesion_pg)
    await asignar_plan(sesion_pg, m.ana, m.plan_base)
    if desactivar == "plan":
        m.plan_base.activo = False
    else:
        m.os.activa = False
    await sesion_pg.flush()
    p = await _presentado(ps, repos, m, actor, [_it(m.h1, m.trat["OBT-001"])])
    p = await ps.aceptar(repos, actor, p.id, AHORA)
    assert p.plan_id is None
    assert len(await _movs(sesion_pg, p.id)) == 1


@pytest.mark.asyncio
async def test_aceptar_usa_el_arancel_vigente_el_dia_de_aceptacion(sesion_pg):
    ps, repos, m, actor = await _escenario(sesion_pg)
    await asignar_plan(sesion_pg, m.ana, m.plan_plus)
    # Aranceles de Plan Plus para N-001: 800 hasta el 29/10; 900 desde el 30/10.
    from datetime import date

    await crear_arancel(sesion_pg, m.plan_plus, "N-001", "800.00", hasta=date(2026, 10, 29))
    nuevo = await crear_arancel(sesion_pg, m.plan_plus, "N-001", "900.00", desde=date(2026, 10, 30))
    p = await _presentado(ps, repos, m, actor, [_it(m.h1, m.trat["CON-001"])])
    p = await ps.aceptar(repos, actor, p.id, AHORA)
    assert await _items(sesion_pg, p.id) == [(nuevo.id, Decimal("900.00"))]


@pytest.mark.asyncio
async def test_aceptar_decidido_a_las_2330_de_buenos_aires_toma_el_dia_local(sesion_pg):
    """31/10 23:30 en Buenos Aires es 01/11 02:30 UTC: el arancel es el del 31/10."""
    from datetime import date

    ps, repos, m, actor = await _escenario(sesion_pg)
    await asignar_plan(sesion_pg, m.ana, m.plan_plus)
    octubre = await crear_arancel(sesion_pg, m.plan_plus, "N-001", "700.00",
                                  hasta=date(2026, 10, 31))
    await crear_arancel(sesion_pg, m.plan_plus, "N-001", "950.00", desde=date(2026, 11, 1))
    p = await _presentado(ps, repos, m, actor, [_it(m.h1, m.trat["CON-001"])])
    en_ba = datetime(2026, 11, 1, 2, 30, tzinfo=timezone.utc)
    p = await ps.aceptar(repos, actor, p.id, en_ba)
    assert await _items(sesion_pg, p.id) == [(octubre.id, Decimal("700.00"))]


# --- 3.3 ajuste de cobertura ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ajuste_de_cobertura_reduce_el_pendiente_y_limita_el_cobro(sesion_pg):
    ps, repos, m, actor = await _escenario(sesion_pg)
    await asignar_plan(sesion_pg, m.ana, m.plan_base)
    p = await _presentado(ps, repos, m, actor, [_it(m.h1, m.trat["OBT-001"])])
    p = await ps.aceptar(repos, actor, p.id, AHORA)
    movs = await _movs(sesion_pg, p.id)
    assert [(t, mo, c) for t, mo, c, *_ in movs] == [
        ("cargo", Decimal("15000.00"), f"Presupuesto {p.id}"),
        ("ajuste", Decimal("-10500.00"), "Cobertura obra social"),
    ]
    assert movs[1].recibo_id is None and movs[1].anula_a_id is None
    assert await repos.cuentas.pendiente_de_presupuesto(p.id) == Decimal("4500.00")


@pytest.mark.asyncio
async def test_cobrar_mas_que_el_pendiente_con_cobertura_es_422(sesion_pg):
    from c10_helpers import cobro_in
    from app.servicios import caja_servicio as cs

    ps, repos, m, actor = await _escenario(sesion_pg)
    await asignar_plan(sesion_pg, m.ana, m.plan_base)
    p = await _presentado(ps, repos, m, actor, [_it(m.h1, m.trat["OBT-001"])])
    p = await ps.aceptar(repos, actor, p.id, AHORA)
    caja_repos = cs.CajaRepos.de_sesion(sesion_pg)
    sec = cs.Actor(usuario_id=m.secretaria.id, rol="secretaria", profesional_id=None)
    with pytest.raises(cs.ValidacionClinicaError):
        await cs.cobrar(caja_repos, sec, cobro_in(p, "4500.01"))
    cobro, creado = await cs.cobrar(caja_repos, sec, cobro_in(p, "4500.00"))
    assert creado and cobro.presupuesto_estado == "cobrado"


@pytest.mark.asyncio
async def test_sin_cobertura_mayor_a_cero_no_hay_ajuste(sesion_pg):
    ps, repos, m, actor = await _escenario(sesion_pg)
    await asignar_plan(sesion_pg, m.ana, m.plan_base)
    p = await _presentado(ps, repos, m, actor, [_it(m.h1, m.trat["PRO-001"])])
    p = await ps.aceptar(repos, actor, p.id, AHORA)
    assert [t for t, *_ in await _movs(sesion_pg, p.id)] == ["cargo"]
    assert p.plan_id == m.plan_base.id and p.estado == "aceptado"


@pytest.mark.asyncio
async def test_aceptar_es_atomico_si_falla_el_ajuste(sesion_pg, monkeypatch):
    ps, repos, m, actor = await _escenario(sesion_pg)
    await asignar_plan(sesion_pg, m.ana, m.plan_base)
    p = await _presentado(ps, repos, m, actor, [_it(m.h1, m.trat["OBT-001"])])
    pid = p.id
    original = repos.cuentas.crear_movimiento

    async def _falla_en_el_ajuste(cc_id, **datos):
        if datos.get("tipo") == "ajuste":
            raise sa.exc.IntegrityError("x", {}, Exception("falla simulada"))
        return await original(cc_id, **datos)

    monkeypatch.setattr(repos.cuentas, "crear_movimiento", _falla_en_el_ajuste)
    with pytest.raises(ps.ConflictoError):
        await ps.aceptar(repos, actor, pid, AHORA)
    await sesion_pg.refresh(p)
    assert p.estado == "presentado" and p.plan_id is None
    assert await _movs(sesion_pg, pid) == []
    assert await _items(sesion_pg, pid) == [(None, None)]


@pytest.mark.asyncio
async def test_aceptar_no_toca_la_caja_aunque_haya_una_pendiente(sesion_pg):
    from c10_helpers import crear_caja
    from app.servicios.caja_servicio import hoy_operativo

    ps, repos, m, actor = await _escenario(sesion_pg)
    await asignar_plan(sesion_pg, m.ana, m.plan_base)
    await crear_caja(sesion_pg, m, hoy_operativo() - timedelta(days=1))
    p = await _presentado(ps, repos, m, actor, [_it(m.h1, m.trat["OBT-001"])])
    p = await ps.aceptar(repos, actor, p.id, AHORA)
    assert p.estado == "aceptado"
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM movimiento_caja")) == 0


# --- 3.4 cobertura total ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cobertura_total_deja_cobrado_sin_recibo_y_fuera_de_pendientes(sesion_pg):
    ps, repos, m, actor = await _escenario(sesion_pg)
    await asignar_plan(sesion_pg, m.ana, m.plan_plus)  # Plan Plus cubre OBT-001 al 100 %
    p = await _presentado(ps, repos, m, actor, [_it(m.h1, m.trat["OBT-001"])])
    p = await ps.aceptar(repos, actor, p.id, AHORA)
    assert p.estado == "cobrado"
    movs = await _movs(sesion_pg, p.id)
    assert [(t, mo) for t, mo, *_ in movs] == [
        ("cargo", Decimal("15000.00")), ("ajuste", Decimal("-15000.00"))]
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM recibo")) == 0
    assert await repos.cuentas.pendientes_de_paciente(m.ana.id) == []


@pytest.mark.asyncio
async def test_cobertura_parcial_deja_aceptado_con_pendiente_a_cargo_del_paciente(sesion_pg):
    ps, repos, m, actor = await _escenario(sesion_pg)
    await asignar_plan(sesion_pg, m.ana, m.plan_base)
    p = await _presentado(ps, repos, m, actor, [_it(m.h1, m.trat["OBT-001"])])
    p = await ps.aceptar(repos, actor, p.id, AHORA)
    assert p.estado == "aceptado"
    (fila,) = await repos.cuentas.pendientes_de_paciente(m.ana.id)
    assert fila.pendiente == Decimal("4500.00")
