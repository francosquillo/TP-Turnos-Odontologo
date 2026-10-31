"""C-09 grupos 4.5 y 5.3: concurrencia real con dos sesiones sobre PG real (D-13, D-14).

Cada repetición siembra datos COMMITEADOS (paciente propio, para no compartir cuenta) y
lanza dos tareas con `asyncio.gather` sobre conexiones distintas. Un `sleep` antes del
commit garantiza que la segunda tarea espere el `FOR UPDATE` de la primera. Se repite
20 veces seguidas sin fallas. Datos ficticios.
"""
import asyncio
import itertools
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import crear_turno  # noqa: E402
from c09_helpers import sembrar_c09  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

AHORA = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
REPETICIONES = 20
_dni = itertools.count(40000000)


async def _paciente_con_presupuestos(sesion, m, cantidad):
    """Paciente nuevo, vinculado a A, con `cantidad` presupuestos `presentado` (commiteado)."""
    from app.modelos import (
        HallazgoOdontograma, HistoriaClinica, ItemPresupuesto, Paciente, Presupuesto,
    )

    paciente = Paciente(nombre="Cami", apellido="Ficticia", dni=str(next(_dni)))
    sesion.add(paciente)
    await sesion.flush()
    await crear_turno(sesion, paciente, m.prof_a, m.sillon, estado="asistido")
    hc = HistoriaClinica(paciente_id=paciente.id)
    sesion.add(hc)
    await sesion.flush()
    ids = []
    for i in range(cantidad):
        hallazgo = HallazgoOdontograma(
            hc_id=hc.id, pieza_fdi=16, cara="oclusal", estado="caries", catalogo_version=1,
            fecha=AHORA, profesional_id=m.prof_a.id)
        sesion.add(hallazgo)
        await sesion.flush()
        p = Presupuesto(
            paciente_id=paciente.id, profesional_id=m.prof_a.id, estado="presentado",
            total=Decimal("1000.50"), presentado_at=AHORA)
        sesion.add(p)
        await sesion.flush()
        sesion.add(ItemPresupuesto(
            presupuesto_id=p.id, hallazgo_id=hallazgo.id, tratamiento_id=m.trat["CON-001"].id,
            cantidad=1, precio=Decimal("1000.50")))
        ids.append(p.id)
    await sesion.commit()
    return paciente.id, ids


def _actor(m, rol="odontologo"):
    from app.servicios import clinica_servicio as cs

    if rol == "admin":
        return cs.Actor(usuario_id=m.admin.id, rol="admin", profesional_id=None)
    return cs.Actor(usuario_id=m.odo_a.id, rol="odontologo", profesional_id=m.prof_a.id)


async def _en_sesion_propia(engine, operacion, pausa=0.25):
    """Corre `operacion(repos)` en una sesión nueva; devuelve 'ok' o el nombre del error."""
    from app.servicios import presupuesto_servicio as ps

    async with async_sessionmaker(engine, expire_on_commit=False)() as sesion:
        repos = ps.PresupuestoRepos.de_sesion(sesion)
        try:
            await operacion(repos)
            await asyncio.sleep(pausa)  # retiene el lock para que la otra tarea espere
            await sesion.commit()
            return "ok"
        except ps.ClinicaError as exc:
            await sesion.rollback()
            return type(exc).__name__


async def _contar(engine, consulta, **params):
    async with engine.connect() as conn:
        return await conn.scalar(sa.text(consulta), params)


@pytest.mark.asyncio
async def test_doble_aceptacion_concurrente_un_cargo(sesion_pg):
    from app.servicios import presupuesto_servicio as ps

    m = await sembrar_c09(sesion_pg)
    await sesion_pg.commit()
    engine = sesion_pg.bind
    actor = _actor(m)
    for _ in range(REPETICIONES):
        _, (pid,) = await _paciente_con_presupuestos(sesion_pg, m, 1)

        async def aceptar(repos, pid=pid):
            await ps.aceptar(repos, actor, pid, AHORA)

        resultados = await asyncio.gather(
            _en_sesion_propia(engine, aceptar), _en_sesion_propia(engine, aceptar))
        assert sorted(resultados) == ["ConflictoError", "ok"], resultados
        assert await _contar(
            engine, "SELECT count(*) FROM movimiento WHERE presupuesto_id = :p", p=pid) == 1
        assert await _contar(
            engine, "SELECT estado FROM presupuesto WHERE id = :p", p=pid) == "aceptado"


@pytest.mark.asyncio
async def test_primer_cargo_concurrente_una_cuenta(sesion_pg):
    from app.servicios import presupuesto_servicio as ps

    m = await sembrar_c09(sesion_pg)
    await sesion_pg.commit()
    engine = sesion_pg.bind
    actor = _actor(m)
    for _ in range(REPETICIONES):
        paciente_id, (p1, p2) = await _paciente_con_presupuestos(sesion_pg, m, 2)

        def aceptar(pid):
            async def _op(repos):
                await ps.aceptar(repos, actor, pid, AHORA)
            return _op

        resultados = await asyncio.gather(
            _en_sesion_propia(engine, aceptar(p1)), _en_sesion_propia(engine, aceptar(p2)))
        assert resultados == ["ok", "ok"], resultados
        assert await _contar(
            engine, "SELECT count(*) FROM cuenta_corriente WHERE paciente_id = :p",
            p=paciente_id) == 1
        assert await _contar(
            engine,
            "SELECT count(*) FROM movimiento mo JOIN cuenta_corriente c ON c.id = mo.cc_id "
            "WHERE c.paciente_id = :p AND mo.tipo = 'cargo'", p=paciente_id) == 2


@pytest.mark.asyncio
async def test_doble_anulacion_concurrente_un_contramovimiento(sesion_pg):
    from app.servicios import cuenta_servicio as cuenta
    from app.servicios import presupuesto_servicio as ps

    m = await sembrar_c09(sesion_pg)
    await sesion_pg.commit()
    engine = sesion_pg.bind
    odo, admin = _actor(m), _actor(m, "admin")
    for _ in range(REPETICIONES):
        paciente_id, (pid,) = await _paciente_con_presupuestos(sesion_pg, m, 1)

        async def aceptar(repos, pid=pid):
            await ps.aceptar(repos, odo, pid, AHORA)

        assert await _en_sesion_propia(engine, aceptar, pausa=0) == "ok"
        cargo_id = await _contar(
            engine, "SELECT id FROM movimiento WHERE presupuesto_id = :p AND tipo = 'cargo'", p=pid)

        async def anular(repos, paciente_id=paciente_id, cargo_id=cargo_id):
            await cuenta.anular_cargo(repos, admin, paciente_id, cargo_id, "Error de carga")

        resultados = await asyncio.gather(
            _en_sesion_propia(engine, anular), _en_sesion_propia(engine, anular))
        assert sorted(resultados) == ["ConflictoError", "ok"], resultados
        assert await _contar(
            engine, "SELECT count(*) FROM movimiento WHERE anula_a_id = :c", c=cargo_id) == 1
        assert await _contar(
            engine,
            "SELECT COALESCE(SUM(mo.monto), 0) FROM movimiento mo JOIN cuenta_corriente c "
            "ON c.id = mo.cc_id WHERE c.paciente_id = :p", p=paciente_id) == Decimal("0.00")


# --- Bloqueo decisivo: la espera la causa SOLO el FOR UPDATE del servicio (4.5, 5.3) ---
#
# La sesión A toma `FOR KEY SHARE` (no `FOR UPDATE`) sobre la fila que el servicio bloquea:
# ese modo NO choca con el UPDATE de columnas no clave ni con el FK de los INSERT de la
# sesión B, pero SÍ choca con `FOR UPDATE`. Así, si alguien quita `with_for_update`, B ya
# no espera y los tests fallan (con `FOR UPDATE` en A, el UPDATE/FK de B esperaría igual).
ESPERA_MAX = 5.0


async def _bloqueada_por(engine, pid_a: int) -> int:
    async with engine.connect() as conn:
        return await conn.scalar(
            sa.text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE :a = ANY(pg_blocking_pids(pid)) AND wait_event_type = 'Lock'"),
            {"a": pid_a})


async def _bloqueo_decisivo(engine, sql_lock: str, params: dict, operacion) -> str:
    """A retiene `FOR KEY SHARE` sin commit; B (el servicio) debe quedar bloqueada hasta que A suelta."""
    async with engine.connect() as a:
        pid_a = await a.scalar(sa.text("SELECT pg_backend_pid()"))
        await a.execute(sa.text(sql_lock), params)
        tarea = asyncio.create_task(_en_sesion_propia(engine, operacion, pausa=0))
        try:
            limite = asyncio.get_running_loop().time() + ESPERA_MAX
            while await _bloqueada_por(engine, pid_a) == 0:
                assert not tarea.done(), "la operación terminó sin esperar el FOR UPDATE"
                assert asyncio.get_running_loop().time() < limite, "B nunca quedó esperando el lock"
                await asyncio.sleep(0.02)
            assert not tarea.done(), "B debe seguir bloqueada mientras A retiene el lock"
            await a.rollback()  # A suelta el lock
            return await asyncio.wait_for(tarea, ESPERA_MAX)
        finally:
            if not tarea.done():
                tarea.cancel()


@pytest.mark.asyncio
async def test_aceptar_espera_el_lock_de_la_fila_hasta_que_se_libera(sesion_pg):
    from app.servicios import presupuesto_servicio as ps

    m = await sembrar_c09(sesion_pg)
    await sesion_pg.commit()
    engine = sesion_pg.bind
    actor = _actor(m)
    for _ in range(REPETICIONES):
        _, (pid,) = await _paciente_con_presupuestos(sesion_pg, m, 1)

        async def aceptar(repos, pid=pid):
            await ps.aceptar(repos, actor, pid, AHORA)

        resultado = await _bloqueo_decisivo(
            engine, "SELECT id FROM presupuesto WHERE id = :p FOR KEY SHARE", {"p": pid}, aceptar)
        assert resultado == "ok"
        assert await _contar(
            engine, "SELECT count(*) FROM movimiento WHERE presupuesto_id = :p", p=pid) == 1
        assert await _contar(
            engine, "SELECT estado FROM presupuesto WHERE id = :p", p=pid) == "aceptado"


@pytest.mark.asyncio
async def test_anular_cargo_espera_el_lock_del_movimiento_hasta_que_se_libera(sesion_pg):
    from app.servicios import cuenta_servicio as cuenta
    from app.servicios import presupuesto_servicio as ps

    m = await sembrar_c09(sesion_pg)
    await sesion_pg.commit()
    engine = sesion_pg.bind
    odo, admin = _actor(m), _actor(m, "admin")
    for _ in range(REPETICIONES):
        paciente_id, (pid,) = await _paciente_con_presupuestos(sesion_pg, m, 1)

        async def aceptar(repos, pid=pid):
            await ps.aceptar(repos, odo, pid, AHORA)

        assert await _en_sesion_propia(engine, aceptar, pausa=0) == "ok"
        cargo_id = await _contar(
            engine, "SELECT id FROM movimiento WHERE presupuesto_id = :p AND tipo = 'cargo'", p=pid)

        async def anular(repos, paciente_id=paciente_id, cargo_id=cargo_id):
            await cuenta.anular_cargo(repos, admin, paciente_id, cargo_id, "Error de carga")

        resultado = await _bloqueo_decisivo(
            engine, "SELECT id FROM movimiento WHERE id = :c FOR KEY SHARE", {"c": cargo_id}, anular)
        assert resultado == "ok"
        assert await _contar(
            engine, "SELECT count(*) FROM movimiento WHERE anula_a_id = :c", c=cargo_id) == 1
