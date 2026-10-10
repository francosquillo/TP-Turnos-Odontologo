"""C-04 task 1.3: EXCLUDE a nivel DB contra Postgres REAL (nunca SQLite).

Inserts crudos concurrentes: solape mismo profesional/sillon -> raise;
contiguo y cancelado/ausente -> ok. Skipean sin compose.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: F401

BASE = datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)


async def _sembrar_base(sesion_pg, matricula="C04-EX1", sillon="Sillón C04-EX1"):
    from app.modelos import Paciente, Profesional, Sillon

    paciente = Paciente(nombre="Demo", apellido="Exclude", consentimiento_datos=True)
    profesional = Profesional(matricula=matricula, agenda_config={})
    sillon_obj = Sillon(nombre=sillon)
    sesion_pg.add_all([paciente, profesional, sillon_obj])
    await sesion_pg.flush()
    return paciente, profesional, sillon_obj


def _es_violacion_exclusion(exc: Exception) -> bool:
    texto = str(exc).lower() + str(getattr(exc, "orig", "")).lower()
    return "exclusion" in texto or "23p01" in texto or "conflicting key value" in texto


@pytest.mark.asyncio
async def test_exclude_profesional_rechaza_solape(sesion_pg):
    """Task 1.3 RED: dos turnos activos solapados mismo profesional -> raise."""
    from app.modelos import Turno

    paciente, profesional, sillon_obj = await _sembrar_base(sesion_pg)
    sesion_pg.add(
        Turno(
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            sillon_id=sillon_obj.id,
            inicio=BASE,
            fin=BASE + timedelta(minutes=30),
            estado="confirmado",
        )
    )
    await sesion_pg.flush()
    sesion_pg.add(
        Turno(
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            sillon_id=sillon_obj.id,
            inicio=BASE + timedelta(minutes=15),
            fin=BASE + timedelta(minutes=45),
            estado="confirmado",
        )
    )
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        await sesion_pg.flush()
    assert _es_violacion_exclusion(exc_info.value)
    await sesion_pg.rollback()


@pytest.mark.asyncio
async def test_exclude_sillon_rechaza_solape(sesion_pg):
    """Task 1.3 RED: mismo sillon, distinto profesional solapado -> raise."""
    from app.modelos import Paciente, Profesional, Turno

    paciente, profesional, sillon_obj = await _sembrar_base(sesion_pg)
    otro_prof = Profesional(matricula="C04-EX2", agenda_config={})
    otro_pac = Paciente(nombre="Otra", apellido="Paciente", consentimiento_datos=True)
    sesion_pg.add_all([otro_prof, otro_pac])
    await sesion_pg.flush()
    sesion_pg.add(
        Turno(
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            sillon_id=sillon_obj.id,
            inicio=BASE,
            fin=BASE + timedelta(minutes=30),
            estado="confirmado",
        )
    )
    await sesion_pg.flush()
    sesion_pg.add(
        Turno(
            paciente_id=otro_pac.id,
            profesional_id=otro_prof.id,
            sillon_id=sillon_obj.id,
            inicio=BASE + timedelta(minutes=15),
            fin=BASE + timedelta(minutes=45),
            estado="pendiente",
        )
    )
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        await sesion_pg.flush()
    assert _es_violacion_exclusion(exc_info.value)
    await sesion_pg.rollback()


@pytest.mark.asyncio
async def test_exclude_permite_contiguo_y_cancelado(sesion_pg):
    """Task 1.3 GREEN: contiguo ok; cancelado/ausente liberan el hueco."""
    from sqlalchemy import select
    from app.modelos import Turno

    paciente, profesional, sillon_obj = await _sembrar_base(
        sesion_pg, matricula="C04-EX3", sillon="Sillón C04-EX3"
    )
    cancelado = Turno(
        paciente_id=paciente.id,
        profesional_id=profesional.id,
        sillon_id=sillon_obj.id,
        inicio=BASE,
        fin=BASE + timedelta(minutes=30),
        estado="cancelado",
        motivo_cancelacion="paciente avisó",
    )
    sesion_pg.add(cancelado)
    await sesion_pg.flush()
    # Mismo hueco que el cancelado: permitido.
    sesion_pg.add(
        Turno(
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            sillon_id=sillon_obj.id,
            inicio=BASE,
            fin=BASE + timedelta(minutes=30),
            estado="confirmado",
        )
    )
    await sesion_pg.flush()
    # Contiguo [10:30, 11:00): permitido (rangos medio-abiertos).
    sesion_pg.add(
        Turno(
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            sillon_id=sillon_obj.id,
            inicio=BASE + timedelta(minutes=30),
            fin=BASE + timedelta(minutes=60),
            estado="confirmado",
        )
    )
    await sesion_pg.flush()
    await sesion_pg.commit()
    filas = (
        await sesion_pg.execute(select(Turno).where(Turno.estado != "cancelado"))
    ).scalars().all()
    assert len(filas) == 2
    # Ausente tambien libera (D-01): pasar uno a ausente habilita el hueco.
    filas[0].estado = "ausente"
    await sesion_pg.flush()
    sesion_pg.add(
        Turno(
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            sillon_id=sillon_obj.id,
            inicio=filas[0].inicio,
            fin=filas[0].fin,
            estado="pendiente",
        )
    )
    await sesion_pg.flush()
    await sesion_pg.commit()
