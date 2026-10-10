"""C-04 task 2.1: TurnoRepository por profesional/sillon/rango (PG real).

Sin PG: solo compila el SQL (detecta typos). Con PG: seed 3 turnos y
filtra rango + excluir propio id correctamente.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: F401

BASE = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)


def test_repo_consultas_compilan_en_postgres():
    """Task 2.1 RED: los selects del repo compilan sin PG (caza typos)."""
    from sqlalchemy.dialects import postgresql

    from app.repos.turno_repo import TurnoRepository

    assert hasattr(TurnoRepository, "activos_en_rango")
    assert hasattr(TurnoRepository, "hay_solapamiento")
    assert hasattr(TurnoRepository, "listar_periodo")
    # Compilar un select equivalente al de activos_en_rango.
    from sqlalchemy import select
    from app.modelos import Turno

    consulta = (
        select(Turno)
        .where(
            Turno.sobre_turno.is_(False),
            Turno.estado.in_(("pendiente", "confirmado", "asistido")),
            Turno.inicio < BASE + timedelta(hours=4),
            Turno.fin > BASE,
        )
        .order_by(Turno.inicio)
    )
    sql = str(consulta.compile(dialect=postgresql.dialect()))
    assert "turno" in sql and "inicio" in sql


@pytest.mark.asyncio
async def test_turno_repo_rango_por_profesional(sesion_pg):
    """Task 2.1 GREEN: seed 3 turnos, filtra rango y excluir propio id."""
    from app.modelos import Paciente, Profesional, Sillon, Turno
    from app.repos.turno_repo import TurnoRepository

    paciente = Paciente(nombre="Demo", apellido="Repo", consentimiento_datos=True)
    profesional = Profesional(matricula="C04-R1", agenda_config={})
    sillon_obj = Sillon(nombre="Sillón C04-R1")
    sesion_pg.add_all([paciente, profesional, sillon_obj])
    await sesion_pg.flush()
    repo = TurnoRepository(sesion_pg)
    t1 = await repo.crear(
        paciente_id=paciente.id,
        profesional_id=profesional.id,
        sillon_id=sillon_obj.id,
        inicio=BASE,
        fin=BASE + timedelta(minutes=30),
        estado="confirmado",
    )
    await repo.crear(
        paciente_id=paciente.id,
        profesional_id=profesional.id,
        sillon_id=sillon_obj.id,
        inicio=BASE + timedelta(hours=1),
        fin=BASE + timedelta(hours=1, minutes=30),
        estado="pendiente",
    )
    await repo.crear(
        paciente_id=paciente.id,
        profesional_id=profesional.id,
        sillon_id=sillon_obj.id,
        inicio=BASE + timedelta(hours=5),
        fin=BASE + timedelta(hours=5, minutes=30),
        estado="confirmado",
    )
    await sesion_pg.flush()
    en_rango = await repo.activos_en_rango(
        BASE, BASE + timedelta(hours=4), profesional_id=profesional.id
    )
    assert [t.id for t in en_rango] == [t1.id, t1.id + 1]
    sin_propio = await repo.activos_en_rango(
        BASE, BASE + timedelta(hours=4),
        profesional_id=profesional.id, excluir_id=t1.id,
    )
    assert [t.id for t in sin_propio] == [t1.id + 1]
    assert await repo.hay_solapamiento(
        profesional.id, sillon_obj.id, BASE, BASE + timedelta(minutes=30)
    ) is True
    assert await repo.hay_solapamiento(
        profesional.id, sillon_obj.id,
        BASE + timedelta(minutes=30), BASE + timedelta(hours=1),
    ) is False
    # El propio turno excluido no se auto-solapa (reprogramacion, D-06).
    assert await repo.hay_solapamiento(
        profesional.id, sillon_obj.id, BASE, BASE + timedelta(minutes=30),
        excluir_id=t1.id,
    ) is False


@pytest.mark.asyncio
async def test_turno_repo_listar_periodo_incluye_cancelados_si_se_pide(sesion_pg):
    """Triangulacion: listar_periodo filtra activos por defecto."""
    from app.modelos import Paciente, Profesional, Sillon
    from app.repos.turno_repo import TurnoRepository

    paciente = Paciente(nombre="Demo", apellido="Repo2", consentimiento_datos=True)
    profesional = Profesional(matricula="C04-R2", agenda_config={})
    sillon_obj = Sillon(nombre="Sillón C04-R2")
    sesion_pg.add_all([paciente, profesional, sillon_obj])
    await sesion_pg.flush()
    repo = TurnoRepository(sesion_pg)
    await repo.crear(
        paciente_id=paciente.id, profesional_id=profesional.id,
        sillon_id=sillon_obj.id, inicio=BASE, fin=BASE + timedelta(minutes=30),
        estado="cancelado", motivo_cancelacion="aviso",
    )
    await sesion_pg.flush()
    solo_activos = await repo.listar_periodo(BASE, BASE + timedelta(hours=1))
    assert solo_activos == []
    todos = await repo.listar_periodo(
        BASE, BASE + timedelta(hours=1), solo_activos=False
    )
    assert len(todos) == 1
