"""C-05 PG-real: servicio reserva + cero-migracion (skipean sin Docker).

TDD: RED = falla sin implementacion/repos; GREEN con C-05. Requiere compose
(db+redis) + `alembic upgrade head`. Sin PG skipean con mensaje accionable.
Datos 100% ficticios.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: E402, F401

LUNES_9_BA = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)  # 09:00 BA
AHORA_BASE = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
AGENDA_LUNES = {
    "duracion_slot_min": 30,
    "horario": {"lunes": [["08:00", "12:00"]]},
}


async def _semilla(sesion_pg):
    from app.modelos import Paciente, Profesional, Sillon

    paciente = Paciente(
        nombre="Paciente", apellido="PG", telefono="1140001111",
        consentimiento_datos=True,
    )
    profesional = Profesional(matricula="C05-PG1", agenda_config=dict(AGENDA_LUNES))
    sillon = Sillon(nombre="Sillón C05-PG1")
    sesion_pg.add_all([paciente, profesional, sillon])
    await sesion_pg.flush()
    return paciente, profesional, sillon


def _repos_reales(sesion_pg):
    from app.repos.paciente_repo import PacienteRepository
    from app.repos.profesional_repo import ProfesionalRepository
    from app.repos.sillon_repo import SillonRepository
    from app.repos.turno_repo import TurnoRepository

    return (
        TurnoRepository(sesion_pg),
        PacienteRepository(sesion_pg),
        ProfesionalRepository(sesion_pg),
        SillonRepository(sesion_pg),
    )


@pytest.mark.asyncio
async def test_reserva_pg_reutiliza_paciente_y_crea_pendiente(sesion_pg):
    """Tasks 1.2/1.3 PG: match por telefono + pendiente con hash (PG real)."""
    from app.servicios import reserva_servicio as svc

    paciente, profesional, sillon = await _semilla(sesion_pg)
    turnos, pacientes, profesionales, sillones = _repos_reales(sesion_pg)
    uno = await svc.crear_reserva(
        turnos, pacientes, profesionales, sillones,
        profesional_id=profesional.id, sillon_id=sillon.id,
        inicio=LUNES_9_BA, fin=LUNES_9_BA + timedelta(minutes=30),
        nombre="Otro Nombre", telefono="11 4000-1111", ahora=AHORA_BASE,
    )
    assert uno.turno.estado == "pendiente"
    assert uno.turno.paciente_id == paciente.id  # reutilizado, no duplicado
    assert uno.turno.token_confirmacion_hash == svc.hash_token(uno.token)
    dos = await svc.crear_reserva(
        turnos, pacientes, profesionales, sillones,
        profesional_id=profesional.id, sillon_id=sillon.id,
        inicio=LUNES_9_BA + timedelta(minutes=30),
        fin=LUNES_9_BA + timedelta(minutes=60),
        nombre="Nueva Ficticia", telefono="1199998888", ahora=AHORA_BASE,
    )
    assert dos.turno.paciente_id != paciente.id
    pacientes_nuevos = await pacientes.por_telefono("1199998888")
    assert pacientes_nuevos is not None and pacientes_nuevos.id == dos.turno.paciente_id


@pytest.mark.asyncio
async def test_confirmar_pg_valido_expirado_reuso_desconocido(sesion_pg):
    """Task 1.4 PG: ciclo completo contra PG real (valido, reuso, expirado)."""
    from c03_fakes import FakeStore

    from app.servicios import reserva_servicio as svc

    _, profesional, sillon = await _semilla(sesion_pg)
    turnos, pacientes, profesionales, sillones = _repos_reales(sesion_pg)
    tienda = FakeStore()
    resultado = await svc.crear_reserva(
        turnos, pacientes, profesionales, sillones,
        profesional_id=profesional.id, sillon_id=sillon.id,
        inicio=LUNES_9_BA, fin=LUNES_9_BA + timedelta(minutes=30),
        nombre="Ana Ficticia", telefono="1150002222", ahora=AHORA_BASE,
    )
    # Expirado por 72 h: sigue pendiente y conserva el hash.
    await turnos.actualizar(resultado.turno, created_at=AHORA_BASE)
    with pytest.raises(svc.TokenExpiradoError):
        await svc.confirmar_por_token(
            turnos, resultado.token, ahora=AHORA_BASE + timedelta(hours=73)
        )
    assert (await turnos.get(resultado.turno.id)).estado == "pendiente"
    # Valido: confirma e invalida.
    confirmado = await svc.confirmar_por_token(
        turnos, resultado.token, ahora=AHORA_BASE + timedelta(hours=1),
        tienda_usados=tienda,
    )
    assert confirmado.estado == "confirmado"
    assert confirmado.token_confirmacion_hash is None
    # Reuso: 410 sin cambios. Desconocido: 404.
    with pytest.raises(svc.TokenUsadoError):
        await svc.confirmar_por_token(
            turnos, resultado.token, ahora=AHORA_BASE + timedelta(hours=2),
            tienda_usados=tienda,
        )
    with pytest.raises(svc.TokenDesconocidoError):
        await svc.confirmar_por_token(turnos, svc.generar_token(), ahora=AHORA_BASE)


@pytest.mark.asyncio
async def test_reserva_pg_concurrente_un_ganador(sesion_pg):
    """Task 1.5 PG: EXCLUDE decide (un 201, un HuecoOcupadoError, 1 turno).

    Patron calcado a C-04 `test_creacion_concurrente_mismo_hueco_un_ganador_pg`:
    sesion propia + commit por intento. Compartir una sesion sin commit entre
    dos `crear_reserva` concurrentes rompe con SAWarning/excepcion de sesion
    en vez de `HuecoOcupadoError`.
    """
    import asyncio

    pytest.importorskip("asyncpg")
    from db_utils import dsn_test, pg_reachable

    ok, motivo = await pg_reachable()
    if not ok:
        pytest.skip(f"Postgres no reachable: {motivo}")
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.modelos import Profesional, Sillon, Turno
    from app.repos.paciente_repo import PacienteRepository
    from app.repos.profesional_repo import ProfesionalRepository
    from app.repos.sillon_repo import SillonRepository
    from app.repos.turno_repo import TurnoRepository
    from app.servicios import agenda_servicio
    from app.servicios import reserva_servicio as svc

    engine = create_async_engine(dsn_test())
    try:
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as base:
            profesional = Profesional(matricula="C05-PG1", agenda_config=dict(AGENDA_LUNES))
            sillon = Sillon(nombre="Sillón C05-PG1")
            base.add_all([profesional, sillon])
            await base.commit()
            ids = (profesional.id, sillon.id)

        async def _intento(nombre: str, telefono: str):
            async with Session() as sesion:
                try:
                    resultado = await svc.crear_reserva(
                        TurnoRepository(sesion),
                        PacienteRepository(sesion),
                        ProfesionalRepository(sesion),
                        SillonRepository(sesion),
                        profesional_id=ids[0], sillon_id=ids[1],
                        inicio=LUNES_9_BA, fin=LUNES_9_BA + timedelta(minutes=30),
                        nombre=nombre, telefono=telefono, ahora=AHORA_BASE,
                    )
                    await sesion.commit()
                    return resultado
                except agenda_servicio.HuecoOcupadoError:
                    await sesion.rollback()
                    raise

        resultados = await asyncio.gather(
            _intento("Ana Ficticia", "1150002222"),
            _intento("Bruno Ficticio", "1150003333"),
            return_exceptions=True,
        )
        assert sum(not isinstance(r, Exception) for r in resultados) == 1
        assert sum(isinstance(r, agenda_servicio.HuecoOcupadoError) for r in resultados) == 1
        async with Session() as check:
            total = await check.scalar(select(func.count()).select_from(Turno))
        assert total == 1
    finally:
        await engine.dispose()


def test_c05_sin_migracion_nueva():
    """Task 4.1: C-05 fue cero DDL (hash vive desde C-04).

    C-06 anadio legitimamente 003_notificacion.py (D-08 del change
    c-06-notificaciones-whatsapp); se admite ese unico archivo conocido.
    """
    versiones = sorted(
        (BACKEND_DIR / "alembic" / "versions").glob("*.py"),
    )
    nombres = [p.name for p in versiones if p.name != "__init__.py"]
    assert nombres == [
        "001_core_identidad_pacientes.py",
        "002_turno.py",
        "003_notificacion.py",  # C-06 (D-08): tabla notificacion + plantilla
    ], nombres
    texto_002 = (BACKEND_DIR / "alembic" / "versions" / "002_turno.py").read_text()
    assert "token_confirmacion_hash" in texto_002


@pytest.mark.asyncio
async def test_c05_turno_staff_mantiene_hash_null(sesion_pg):
    """Task 4.1 PG: staff intacto (origen secretaria, hash NULL, sin token)."""
    from app.esquemas.turno import TurnoOut
    from app.servicios import agenda_servicio

    assert "token_confirmacion_hash" not in TurnoOut.model_fields
    paciente, profesional, sillon = await _semilla(sesion_pg)
    turnos, pacientes, profesionales, sillones = _repos_reales(sesion_pg)
    turno = await agenda_servicio.crear_turno(
        turnos, pacientes, profesionales, sillones,
        paciente_id=paciente.id, profesional_id=profesional.id, sillon_id=sillon.id,
        inicio=LUNES_9_BA, fin=LUNES_9_BA + timedelta(minutes=30),
        origen="secretaria", ahora=AHORA_BASE,
    )
    assert turno.estado == "confirmado"
    assert turno.token_confirmacion_hash is None
