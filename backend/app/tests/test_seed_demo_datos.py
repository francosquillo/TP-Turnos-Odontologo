"""Seed demo rico: pacientes extra, turnos relativos a hoy, clinica y cobros/caja (idempotente).

Parte 1 corre sin Postgres (datos). Parte 2 corre el seed real sobre Postgres (sin Postgres se
saltea y debe reportarse como NO EJECUTADA). Nunca SQLite: el EXCLUDE de turnos es de PG.
"""
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: E402, F401

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
AHORA = datetime(2026, 11, 10, 11, 0, tzinfo=TZ)  # martes


# --- datos (sin Postgres) ----------------------------------------------------------------------

def test_hay_al_menos_25_pacientes_extra_con_convencion_de_datos_ficticios():
    from app.db.seed import PACIENTES_DEMO
    from app.servicios.reserva_servicio import normalizar_telefono

    assert len(PACIENTES_DEMO) >= 4 + 25
    assert len({p.dni for p in PACIENTES_DEMO}) == len(PACIENTES_DEMO)
    assert len({p.telefono for p in PACIENTES_DEMO}) == len(PACIENTES_DEMO)
    assert len({p.email for p in PACIENTES_DEMO}) == len(PACIENTES_DEMO)
    for p in PACIENTES_DEMO:
        assert p.dni.startswith("9000") and len(p.dni) == 8
        assert p.telefono.startswith("54911000000") and normalizar_telefono(p.telefono) == p.telefono
        assert p.email.endswith("@example.com")


def test_pacientes_extra_mezclan_planes_y_particulares():
    from app.db.seed import PACIENTES_DEMO

    extra = PACIENTES_DEMO[4:]
    por_plan = {p.plan for p in extra}
    assert por_plan == {"Plan Base", "Plan Plus", None}
    assert sum(p.plan is None for p in extra) >= 8


# --- Postgres real ---------------------------------------------------------------------------------

@pytest.fixture
def env_seed(monkeypatch):
    monkeypatch.setenv("SEED_ADMIN_EMAIL", "admin@demo.test")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "demo-ficticia-123")


async def _todos(sesion, modelo, *orden):
    from sqlalchemy import select

    return list((await sesion.execute(select(modelo).order_by(*orden))).scalars().all())


@pytest.mark.asyncio
async def test_pg_seed_doble_ejecucion_no_duplica_nada_y_devuelve_conteos_nuevos(sesion_pg, env_seed):
    from app.db.seed import run_seed

    primera = await run_seed(sesion_pg, ahora=AHORA)
    segunda = await run_seed(sesion_pg, ahora=AHORA)
    assert primera == segunda
    for clave in ("turnos", "historias_clinicas", "hallazgos", "presupuestos", "recibos", "cajas",
                  "movimientos_cuenta", "movimientos_caja"):
        assert primera[clave] > 0, clave
    assert primera["pacientes"] >= 29


@pytest.mark.asyncio
async def test_pg_turnos_cubren_los_cinco_estados_pasado_y_futuro_en_sillon_demo(sesion_pg, env_seed):
    from sqlalchemy import select

    from app.db.seed import SILLON_DEMO_NOMBRE, run_seed
    from app.modelos import Sillon, Turno

    await run_seed(sesion_pg, ahora=AHORA)
    turnos = await _todos(sesion_pg, Turno, Turno.inicio)
    assert {t.estado for t in turnos} == {"pendiente", "confirmado", "asistido", "ausente", "cancelado"}
    sillon_id = await sesion_pg.scalar(select(Sillon.id).where(Sillon.nombre == SILLON_DEMO_NOMBRE))
    assert {t.sillon_id for t in turnos} == {sillon_id}
    inicios = [t.inicio.astimezone(TZ) for t in turnos]
    assert min(inicios) <= AHORA - timedelta(days=14) and max(inicios) >= AHORA + timedelta(days=10)
    # Coherencia temporal: lo futuro nunca esta asistido/ausente; lo asistido es pasado.
    assert all(t.inicio < AHORA for t in turnos if t.estado in ("asistido", "ausente"))
    assert all(t.inicio >= AHORA for t in turnos if t.estado == "pendiente")
    assert all(t.motivo_cancelacion for t in turnos if t.estado == "cancelado")


@pytest.mark.asyncio
async def test_pg_turnos_respetan_horario_de_agenda_demo_y_no_se_solapan(sesion_pg, env_seed):
    from app.db.seed import AGENDA_DEMO, run_seed
    from app.modelos import Turno

    await run_seed(sesion_pg, ahora=AHORA)
    activos = [t for t in await _todos(sesion_pg, Turno, Turno.inicio)
               if t.estado in ("pendiente", "confirmado", "asistido")]
    assert len(activos) > 40
    for t in activos:
        ini, fin = t.inicio.astimezone(TZ), t.fin.astimezone(TZ)
        ventanas = AGENDA_DEMO["horario"].get(DIAS[ini.weekday()], [])
        assert ini.date() == fin.date()
        assert any(
            ini.strftime("%H:%M") >= desde and fin.strftime("%H:%M") <= hasta for desde, hasta in ventanas
        ), (DIAS[ini.weekday()], ini, fin)
    for anterior, siguiente in zip(activos, activos[1:]):
        assert anterior.fin <= siguiente.inicio


@pytest.mark.asyncio
async def test_pg_seed_con_dias_nuevos_agrega_turnos_sin_duplicar_los_existentes(sesion_pg, env_seed):
    from sqlalchemy import func, select

    from app.db.seed import run_seed
    from app.modelos import Turno

    await run_seed(sesion_pg, ahora=AHORA)
    antes = await _todos(sesion_pg, Turno, Turno.id)
    await run_seed(sesion_pg, ahora=AHORA + timedelta(days=7))
    despues = await _todos(sesion_pg, Turno, Turno.id)
    assert len(despues) > len(antes)  # entran los dias nuevos del horizonte
    assert [t.id for t in despues[: len(antes)]] == [t.id for t in antes]
    claves = await sesion_pg.scalar(
        select(func.count()).select_from(
            select(Turno.paciente_id, Turno.inicio).distinct().subquery()
        )
    )
    assert claves == len(despues)


@pytest.mark.asyncio
async def test_pg_seed_no_falla_si_un_turno_real_ocupa_un_hueco_demo(sesion_pg, env_seed):
    from app.db.seed import PACIENTES_DEMO, run_seed, seed_demo, seed_obras_sociales, seed_pacientes_demo
    from app.db.seed import seed_roles, seed_tratamientos
    from app.modelos import Paciente, Turno
    from sqlalchemy import select

    await seed_roles(sesion_pg)
    sillon, profesional = await seed_demo(sesion_pg)
    await seed_tratamientos(sesion_pg)
    await seed_obras_sociales(sesion_pg)
    await seed_pacientes_demo(sesion_pg)
    real = await sesion_pg.scalar(select(Paciente).where(Paciente.dni == PACIENTES_DEMO[0].dni))
    # Un turno "real" bloquea toda la manana de varios dias futuros (confirmado, otro origen).
    for dias in range(1, 8):
        dia = (AHORA + timedelta(days=dias)).date()
        sesion_pg.add(Turno(
            paciente_id=real.id, profesional_id=profesional.id, sillon_id=sillon.id,
            inicio=datetime(dia.year, dia.month, dia.day, 9, 0, tzinfo=TZ),
            fin=datetime(dia.year, dia.month, dia.day, 13, 0, tzinfo=TZ),
            estado="confirmado", origen="online",
        ))
    await sesion_pg.flush()
    await run_seed(sesion_pg, ahora=AHORA)
    activos = [t for t in await _todos(sesion_pg, Turno, Turno.inicio)
               if t.estado in ("pendiente", "confirmado", "asistido")]
    for anterior, siguiente in zip(activos, activos[1:]):
        assert anterior.fin <= siguiente.inicio


@pytest.mark.asyncio
async def test_pg_cada_item_de_presupuesto_referencia_hallazgo_vigente_de_su_paciente_y_tratamiento(
    sesion_pg, env_seed
):
    from sqlalchemy import select

    from app.db.seed import run_seed
    from app.modelos import (
        HallazgoOdontograma, HistoriaClinica, ItemPresupuesto, Presupuesto, Tratamiento,
    )

    await run_seed(sesion_pg, ahora=AHORA)
    filas = (await sesion_pg.execute(
        select(ItemPresupuesto, HallazgoOdontograma, HistoriaClinica, Presupuesto)
        .outerjoin(HallazgoOdontograma, HallazgoOdontograma.id == ItemPresupuesto.hallazgo_id)
        .outerjoin(HistoriaClinica, HistoriaClinica.id == HallazgoOdontograma.hc_id)
        .join(Presupuesto, Presupuesto.id == ItemPresupuesto.presupuesto_id)
    )).all()
    assert len(filas) >= 8
    for item, hallazgo, hc, presupuesto in filas:
        assert hallazgo is not None and hallazgo.deleted_at is None
        assert 11 <= hallazgo.pieza_fdi <= 48 and 1 <= hallazgo.pieza_fdi % 10 <= 8
        assert hc.paciente_id == presupuesto.paciente_id
        assert await sesion_pg.get(Tratamiento, item.tratamiento_id) is not None
    # El total guardado coincide con la suma de sus items (lo calcula el servicio).
    por_presupuesto: dict[int, Decimal] = {}
    for item, _, _, presupuesto in filas:
        por_presupuesto[presupuesto.id] = por_presupuesto.get(presupuesto.id, Decimal(0)) + item.cantidad * item.precio
    for presupuesto in await _todos(sesion_pg, Presupuesto, Presupuesto.id):
        if presupuesto.id in por_presupuesto:
            assert presupuesto.total == por_presupuesto[presupuesto.id]


@pytest.mark.asyncio
async def test_pg_clinica_tiene_historias_hallazgos_y_presupuestos_en_varios_estados(sesion_pg, env_seed):
    from app.db.seed import run_seed
    from app.modelos import HallazgoOdontograma, HistoriaClinica, Presupuesto

    await run_seed(sesion_pg, ahora=AHORA)
    historias = await _todos(sesion_pg, HistoriaClinica, HistoriaClinica.id)
    assert len(historias) >= 8 and all(h.antecedentes and h.alergias for h in historias)
    hallazgos = await _todos(sesion_pg, HallazgoOdontograma, HallazgoOdontograma.id)
    assert len({h.pieza_fdi for h in hallazgos}) >= 6
    assert {h.estado for h in hallazgos} >= {"caries", "obturacion", "corona", "endodoncia"}
    estados = {p.estado for p in await _todos(sesion_pg, Presupuesto, Presupuesto.id)}
    assert estados >= {"borrador", "presentado", "aceptado", "rechazado", "cobrado"}


@pytest.mark.asyncio
async def test_pg_recibos_contiguos_cajas_pasadas_cerradas_y_saldo_derivado(sesion_pg, env_seed):
    from sqlalchemy import func, select

    from app.db.seed import run_seed
    from app.modelos import Caja, CuentaCorriente, Movimiento, MovimientoCaja, Recibo, ReciboContador

    await run_seed(sesion_pg, ahora=AHORA)
    recibos = await _todos(sesion_pg, Recibo, Recibo.numero)
    assert len(recibos) >= 5
    assert [r.numero for r in recibos] == list(range(1, len(recibos) + 1))  # sin huecos
    assert await sesion_pg.scalar(select(ReciboContador.ultimo)) == len(recibos)
    assert {r.medio for r in recibos} <= {"efectivo", "transferencia", "tarjeta_simulada"}
    assert len({r.medio for r in recibos}) >= 2

    cajas = await _todos(sesion_pg, Caja, Caja.fecha)
    assert len(cajas) >= 3
    for caja in cajas:
        assert caja.fecha < AHORA.date() and caja.estado == "cerrada"
        suma = await sesion_pg.scalar(
            select(func.coalesce(func.sum(MovimientoCaja.monto), 0)).where(MovimientoCaja.caja_id == caja.id)
        )
        assert caja.total_sistema == suma and caja.diferencia == caja.total_contado - suma
        if caja.diferencia != 0:
            assert caja.motivo_diferencia
    assert any(c.diferencia != 0 for c in cajas)  # hay un cierre con diferencia justificada

    anulados = [r for r in recibos if r.anulado]
    assert anulados and all(r.motivo_anulacion and r.anulado_por for r in anulados)
    for recibo in anulados:  # anulacion = contramovimiento, nunca borrado
        montos = (await sesion_pg.execute(
            select(MovimientoCaja.monto).where(MovimientoCaja.recibo_id == recibo.id)
        )).scalars().all()
        assert sorted(montos) == [-recibo.monto, recibo.monto]

    # Cada pago tiene su recibo; el saldo no es columna: se deriva de los movimientos.
    movimientos = await _todos(sesion_pg, Movimiento, Movimiento.id)
    assert all(m.recibo_id for m in movimientos if m.tipo == "pago")
    assert not hasattr(CuentaCorriente, "saldo")
    saldos = [
        await sesion_pg.scalar(
            select(func.coalesce(func.sum(Movimiento.monto), 0)).where(Movimiento.cc_id == cc.id)
        )
        for cc in await _todos(sesion_pg, CuentaCorriente, CuentaCorriente.id)
    ]
    assert any(s > 0 for s in saldos) and any(s == 0 for s in saldos)


@pytest.mark.asyncio
async def test_pg_seed_no_genera_notificaciones(sesion_pg, env_seed):
    from sqlalchemy import func, select

    from app.db.seed import run_seed
    from app.modelos import Notificacion

    await run_seed(sesion_pg, ahora=AHORA)
    assert await sesion_pg.scalar(select(func.count()).select_from(Notificacion)) == 0


@pytest.mark.asyncio
async def test_pg_seed_no_toca_pacientes_reales_ni_sus_cajas_ya_cerradas(sesion_pg, env_seed):
    """Con una caja ya existente en un dia del horizonte, el seed no la modifica ni falla."""
    from app.db.seed import run_seed
    from app.modelos import Caja

    await run_seed(sesion_pg, ahora=AHORA)
    cajas = await _todos(sesion_pg, Caja, Caja.fecha)
    snapshot = [(c.id, c.fecha, c.total_sistema, c.estado) for c in cajas]
    await run_seed(sesion_pg, ahora=AHORA + timedelta(days=3))
    cajas2 = await _todos(sesion_pg, Caja, Caja.fecha)
    assert [(c.id, c.fecha, c.total_sistema, c.estado) for c in cajas2] == snapshot
    assert date(2026, 11, 10) > max(c.fecha for c in cajas2)
