"""C-04 tasks 2.2/2.3/2.4: servicio agenda con fakes (sin PG) + PG real.

Huecos = agenda_config − ocupados (puro, siempre corre); crear_turno valida
FKs/fin>inicio/solape/sobreturno auditado; carrera concurrente un ganador.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c04_fakes import (
    AGENDA_LUNES,
    FakeEntidadRepo,
    FakeProfesionalRepo,
    FakeTurnoRepo,
    fabricar_entidad,
    fabricar_turno,
)
from db_utils import sesion_pg  # noqa: F401

LUNES = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)  # lunes
UTC = timezone.utc


def _repos(profesional_id=1, sillon_id=1, turnos=None):
    turnos_repo = FakeTurnoRepo(turnos)
    pacientes = FakeEntidadRepo([fabricar_entidad(1)])
    profesionales = FakeProfesionalRepo([fabricar_entidad(profesional_id)])
    sillones = FakeEntidadRepo([fabricar_entidad(sillon_id)])
    return turnos_repo, pacientes, profesionales, sillones


def test_huecos_resta_turnos_existentes():
    """Task 2.2 RED: lunes 08-12 con turno 09:00-09:30 no ofrece 09:00."""
    from app.servicios.agenda_servicio import calcular_huecos

    # Turno 09:00-09:30 hora Buenos Aires (= 12:00-12:30 UTC, UTC-3 todo el año).
    ocupados = [
        (
            datetime(2026, 10, 12, 12, 0, tzinfo=UTC),
            datetime(2026, 10, 12, 12, 30, tzinfo=UTC),
        )
    ]
    huecos = calcular_huecos(
        {
            "duracion_slot_min": 30,
            "horario": {"lunes": [["08:00", "12:00"]]},
        },
        LUNES,
        LUNES + timedelta(days=1),
        ocupados,
        None,
    )
    inicios = [h[0].strftime("%H:%M") for h in huecos]
    assert "08:00" in inicios and "08:30" in inicios
    assert "09:00" not in inicios
    assert "09:30" in inicios
    assert all(h[0].hour < 12 for h in huecos)


def test_huecos_fuera_de_horario_vacio():
    """Task 2.2 RED: domingo sin horario (o config vacia) -> []."""
    from app.servicios.agenda_servicio import calcular_huecos

    domingo = datetime(2026, 10, 11, 0, 0, tzinfo=UTC)
    assert (
        calcular_huecos(
            {"duracion_slot_min": 30, "horario": {"lunes": [["08:00", "12:00"]]}},
            domingo,
            domingo + timedelta(days=1),
            [],
            None,
        )
        == []
    )
    assert calcular_huecos({}, LUNES, LUNES + timedelta(days=1), [], None) == []


@pytest.mark.asyncio
async def test_crear_solape_sin_flag_409():
    """Task 2.3 RED: solape sin sobre_turno -> HuecoOcupadoError + alternativas."""
    from app.servicios.agenda_servicio import HuecoOcupadoError, crear_turno

    existente = fabricar_turno(
        id=1,
        inicio=datetime(2026, 10, 12, 8, 0, tzinfo=UTC),
        fin=datetime(2026, 10, 12, 8, 30, tzinfo=UTC),
    )
    turnos_repo, pacientes, profesionales, sillones = _repos(turnos=[existente])
    with pytest.raises(HuecoOcupadoError) as exc_info:
        await crear_turno(
            turnos_repo,
            pacientes,
            profesionales,
            sillones,
            paciente_id=1,
            profesional_id=1,
            sillon_id=1,
            inicio=datetime(2026, 10, 12, 8, 15, tzinfo=UTC),
            fin=datetime(2026, 10, 12, 8, 45, tzinfo=UTC),
            creado_por=7,
        )
    assert len(exc_info.value.alternativas) > 0
    assert len((await turnos_repo.listar_periodo(LUNES, LUNES + timedelta(days=1), solo_activos=False))) == 1


@pytest.mark.asyncio
async def test_sobreturno_sin_motivo_rechazado():
    """Task 2.3 RED: flag sin motivo (o motivo corto) -> 422 de validacion."""
    from app.servicios.agenda_servicio import MotivoRequeridoError, crear_turno

    existente = fabricar_turno(id=1)
    for motivo in (None, "", "abc"):
        turnos_repo, pacientes, profesionales, sillones = _repos(turnos=[existente])
        with pytest.raises(MotivoRequeridoError):
            await crear_turno(
                turnos_repo,
                pacientes,
                profesionales,
                sillones,
                paciente_id=1,
                profesional_id=1,
                sillon_id=1,
                inicio=existente.inicio + timedelta(minutes=10),
                fin=existente.fin + timedelta(minutes=10),
                sobre_turno=True,
                motivo_sobreturno=motivo,
                creado_por=7,
            )


@pytest.mark.asyncio
async def test_sobreturno_con_motivo_audita():
    """Task 2.3 RED: flag + motivo crea sobreturno con auditoria."""
    from app.servicios.agenda_servicio import crear_turno

    existente = fabricar_turno(id=1)
    turnos_repo, pacientes, profesionales, sillones = _repos(turnos=[existente])
    turno = await crear_turno(
        turnos_repo,
        pacientes,
        profesionales,
        sillones,
        paciente_id=1,
        profesional_id=1,
        sillon_id=1,
        inicio=existente.inicio + timedelta(minutes=10),
        fin=existente.fin + timedelta(minutes=10),
        sobre_turno=True,
        motivo_sobreturno="urgencia con dolor",
        creado_por=7,
    )
    assert turno.sobre_turno is True
    assert turno.motivo_sobreturno == "urgencia con dolor"
    assert turno.creado_por == 7


@pytest.mark.asyncio
async def test_crear_turno_staff_nace_confirmado_y_online_pendiente():
    """Triangulacion: origen secretaria -> confirmado; online -> pendiente."""
    from app.servicios.agenda_servicio import crear_turno

    turnos_repo, pacientes, profesionales, sillones = _repos()
    staff = await crear_turno(
        turnos_repo,
        pacientes,
        profesionales,
        sillones,
        paciente_id=1,
        profesional_id=1,
        sillon_id=1,
        inicio=datetime(2026, 10, 12, 8, 0, tzinfo=UTC),
        fin=datetime(2026, 10, 12, 8, 30, tzinfo=UTC),
        origen="secretaria",
        creado_por=7,
    )
    assert staff.estado == "confirmado"
    assert staff.token_confirmacion_hash is None
    online = await crear_turno(
        turnos_repo,
        pacientes,
        profesionales,
        sillones,
        paciente_id=1,
        profesional_id=1,
        sillon_id=1,
        inicio=datetime(2026, 10, 12, 9, 0, tzinfo=UTC),
        fin=datetime(2026, 10, 12, 9, 30, tzinfo=UTC),
        origen="online",
    )
    assert online.estado == "pendiente"


@pytest.mark.asyncio
async def test_crear_turno_fk_inexistente_y_fin_invalido_422():
    """Triangulacion: FK rota y fin<=inicio -> EntidadNoEncontrada/ValueError."""
    from app.servicios.agenda_servicio import EntidadNoEncontradaError, crear_turno

    turnos_repo, pacientes, profesionales, sillones = _repos()
    with pytest.raises(EntidadNoEncontradaError):
        await crear_turno(
            turnos_repo,
            pacientes,
            profesionales,
            sillones,
            paciente_id=999,
            profesional_id=1,
            sillon_id=1,
            inicio=datetime(2026, 10, 12, 8, 0, tzinfo=UTC),
            fin=datetime(2026, 10, 12, 8, 30, tzinfo=UTC),
        )
    with pytest.raises(ValueError):
        await crear_turno(
            turnos_repo,
            pacientes,
            profesionales,
            sillones,
            paciente_id=1,
            profesional_id=1,
            sillon_id=1,
            inicio=datetime(2026, 10, 12, 8, 30, tzinfo=UTC),
            fin=datetime(2026, 10, 12, 8, 30, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_creacion_concurrente_mismo_hueco_un_ganador():
    """Task 2.4 RED: 2 tareas mismo hueco -> 1 turno, la otra 409."""
    import asyncio

    from app.servicios.agenda_servicio import HuecoOcupadoError, crear_turno

    turnos_repo, pacientes, profesionales, sillones = _repos()

    async def _intento():
        try:
            turno = await crear_turno(
                turnos_repo,
                pacientes,
                profesionales,
                sillones,
                paciente_id=1,
                profesional_id=1,
                sillon_id=1,
                inicio=datetime(2026, 10, 12, 8, 0, tzinfo=UTC),
                fin=datetime(2026, 10, 12, 8, 30, tzinfo=UTC),
                creado_por=7,
            )
            return ("ok", turno.id)
        except HuecoOcupadoError:
            return ("conflicto", None)

    resultados = await asyncio.gather(_intento(), _intento())
    assert sorted(r[0] for r in resultados) == ["conflicto", "ok"]
    persistidos = await turnos_repo.listar_periodo(
        LUNES, LUNES + timedelta(days=1), solo_activos=False
    )
    assert len(persistidos) == 1


@pytest.mark.asyncio
async def test_creacion_concurrente_mismo_hueco_un_ganador_pg(sesion_pg):
    """Task 2.4 GREEN en PG real: la DB decide (una 201, una 409)."""
    import asyncio

    pytest.importorskip("asyncpg")
    from db_utils import dsn_test, pg_reachable

    ok, motivo = await pg_reachable()
    if not ok:
        pytest.skip(f"Postgres no reachable: {motivo}")
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.repos import (
        PacienteRepository,
        ProfesionalRepository,
        SillonRepository,
        TurnoRepository,
    )
    from app.servicios.agenda_servicio import HuecoOcupadoError, crear_turno

    engine = create_async_engine(dsn_test())
    try:
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as base:
            paciente = await PacienteRepository(base).crear(
                nombre="Demo", apellido="Carrera", consentimiento_datos=True
            )
            profesional = await ProfesionalRepository(base).crear(
                matricula="C04-CAR1", agenda_config=dict(AGENDA_LUNES)
            )
            sillon = await SillonRepository(base).crear(nombre="Sillón C04-CAR1")
            await base.commit()
            ids = (paciente.id, profesional.id, sillon.id)

        async def _intento():
            async with Session() as sesion:
                try:
                    turno = await crear_turno(
                        TurnoRepository(sesion),
                        PacienteRepository(sesion),
                        ProfesionalRepository(sesion),
                        SillonRepository(sesion),
                        paciente_id=ids[0],
                        profesional_id=ids[1],
                        sillon_id=ids[2],
                        inicio=datetime(2026, 10, 12, 8, 0, tzinfo=UTC),
                        fin=datetime(2026, 10, 12, 8, 30, tzinfo=UTC),
                        # Sin creado_por: no hay usuario seedeado y la FK
                        # (usuario.id) lo rechazaría con 422 (ver test
                        # creado_por_inexistente); la carrera es por EXCLUDE.
                        creado_por=None,
                    )
                    await sesion.commit()
                    return "ok"
                except HuecoOcupadoError:
                    await sesion.rollback()
                    return "conflicto"

        resultados = await asyncio.gather(_intento(), _intento())
        assert sorted(resultados) == ["conflicto", "ok"]
    finally:
        await engine.dispose()


class _OrigenRoto(Exception):
    """IntegrityError.orig falso con pgcode/sqlstate y mensaje realista."""

    def __init__(self, mensaje: str, pgcode: str | None) -> None:
        super().__init__(mensaje)
        self.pgcode = pgcode
        self.sqlstate = pgcode


def _integrity_falso(mensaje: str, pgcode: str | None):
    from sqlalchemy.exc import IntegrityError

    return IntegrityError("INSERT INTO turno ...", {}, _OrigenRoto(mensaje, pgcode))


def test_solo_exclude_es_409_otras_integridades_no():
    """Fix-1 RED (verify): solo la violacion EXCLUDE (23P01) es 409.

    FK (23503) -> 422 y cualquier otra integridad propaga sin mapear.
    """
    from app.servicios import agenda_servicio as svc

    assert svc._es_violacion_exclude(
        _integrity_falso(
            'conflicting key value violates exclusion constraint '
            '"ex_turno_prof_sin_solape" on table "turno"',
            "23P01",
        )
    ) is True
    assert svc._es_violacion_exclude(
        _integrity_falso(
            'conflicting key value violates exclusion constraint '
            '"ex_turno_sillon_sin_solape" on table "turno"',
            None,
        )
    ) is True
    assert svc._es_violacion_exclude(
        _integrity_falso(
            'insert or update on table "turno" violates foreign key '
            'constraint "turno_creado_por_fkey" on table "turno"',
            "23503",
        )
    ) is False
    assert svc._es_violacion_exclude(
        _integrity_falso(
            'new row for relation "turno" violates check constraint '
            '"ck_turno_fin_mayor_inicio"',
            "23514",
        )
    ) is False
    assert svc._es_violacion_fk(
        _integrity_falso(
            'insert or update on table "turno" violates foreign key '
            'constraint "turno_creado_por_fkey" on table "turno"',
            "23503",
        )
    ) is True
    assert svc._es_violacion_fk(
        _integrity_falso(
            'conflicting key value violates exclusion constraint '
            '"ex_turno_prof_sin_solape" on table "turno"',
            "23P01",
        )
    ) is False


class _TurnoRepoRoto:
    """TurnoRepository falso cuyo crear() lanza el IntegrityError dado."""

    sesion = None

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def hay_solapamiento(self, *args, **kwargs) -> bool:
        return False

    async def activos_en_rango(self, *args, **kwargs) -> list:
        return []

    async def crear(self, **datos):
        raise self._error


@pytest.mark.asyncio
async def test_crear_turno_mapea_fk_a_422_y_exclude_a_409():
    """Fix-1 RED (verify): FK rota -> EntidadNoEncontradaError (422).

    EXCLUDE -> HuecoOcupadoError (409); CHECK u otra integridad propaga.
    """
    from sqlalchemy.exc import IntegrityError

    from app.servicios.agenda_servicio import (
        EntidadNoEncontradaError,
        HuecoOcupadoError,
        crear_turno,
    )

    inicio = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
    fin = datetime(2026, 10, 12, 8, 30, tzinfo=UTC)

    _, pacientes, profesionales, sillones = _repos()
    with pytest.raises(EntidadNoEncontradaError):
        await crear_turno(
            _TurnoRepoRoto(
                _integrity_falso(
                    'insert or update on table "turno" violates foreign key '
                    'constraint "turno_creado_por_fkey" on table "turno"',
                    "23503",
                )
            ),
            pacientes,
            profesionales,
            sillones,
            paciente_id=1,
            profesional_id=1,
            sillon_id=1,
            inicio=inicio,
            fin=fin,
            creado_por=999999,
        )

    _, pacientes, profesionales, sillones = _repos()
    with pytest.raises(HuecoOcupadoError):
        await crear_turno(
            _TurnoRepoRoto(
                _integrity_falso(
                    'conflicting key value violates exclusion constraint '
                    '"ex_turno_prof_sin_solape" on table "turno"',
                    "23P01",
                )
            ),
            pacientes,
            profesionales,
            sillones,
            paciente_id=1,
            profesional_id=1,
            sillon_id=1,
            inicio=inicio,
            fin=fin,
        )

    _, pacientes, profesionales, sillones = _repos()
    with pytest.raises(IntegrityError):
        await crear_turno(
            _TurnoRepoRoto(
                _integrity_falso(
                    'new row for relation "turno" violates check constraint '
                    '"ck_turno_fin_mayor_inicio"',
                    "23514",
                )
            ),
            pacientes,
            profesionales,
            sillones,
            paciente_id=1,
            profesional_id=1,
            sillon_id=1,
            inicio=inicio,
            fin=fin,
        )


@pytest.mark.asyncio
async def test_crear_turno_creado_por_inexistente_422_en_pg(sesion_pg):
    """Fix-1 RED (verify, PG real): creado_por fantasma -> 422, no 409."""
    pytest.importorskip("asyncpg")
    from db_utils import dsn_test, pg_reachable

    ok, motivo = await pg_reachable()
    if not ok:
        pytest.skip(f"Postgres no reachable: {motivo}")
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.repos import (
        PacienteRepository,
        ProfesionalRepository,
        SillonRepository,
        TurnoRepository,
    )
    from app.servicios.agenda_servicio import (
        EntidadNoEncontradaError,
        crear_turno,
    )

    engine = create_async_engine(dsn_test())
    try:
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as base:
            paciente = await PacienteRepository(base).crear(
                nombre="Demo", apellido="FK422", consentimiento_datos=True
            )
            profesional = await ProfesionalRepository(base).crear(
                matricula="C04-FK422", agenda_config=dict(AGENDA_LUNES)
            )
            sillon = await SillonRepository(base).crear(nombre="Sillón C04-FK422")
            await base.commit()
            ids = (paciente.id, profesional.id, sillon.id)
        async with Session() as sesion:
            with pytest.raises(EntidadNoEncontradaError):
                await crear_turno(
                    TurnoRepository(sesion),
                    PacienteRepository(sesion),
                    ProfesionalRepository(sesion),
                    SillonRepository(sesion),
                    paciente_id=ids[0],
                    profesional_id=ids[1],
                    sillon_id=ids[2],
                    inicio=datetime(2026, 10, 12, 8, 0, tzinfo=UTC),
                    fin=datetime(2026, 10, 12, 8, 30, tzinfo=UTC),
                    creado_por=999999,
                )
            await sesion.rollback()
    finally:
        await engine.dispose()
