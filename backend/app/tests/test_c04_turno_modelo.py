"""C-04 task 1.2: modelo Turno SQLAlchemy 2 async (Mapped + type hints).

PG real (skipea sin compose): insert+select redondo.
Sin PG: metadata trae tabla turno con doble EXCLUDE + CHECK fin>inicio.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: F401


def test_turno_registrado_en_base_con_doble_exclude():
    """Task 1.2 RED: Base.metadata.turno con 2 EXCLUDE y CHECK fin>inicio."""
    from sqlalchemy.dialects.postgresql import ExcludeConstraint

    from app.modelos import Base, Turno

    assert "turno" in Base.metadata.tables
    tabla = Base.metadata.tables["turno"]
    excludes = [c for c in tabla.constraints if isinstance(c, ExcludeConstraint)]
    assert len(excludes) == 2, f"se esperaban 2 EXCLUDE, hay {len(excludes)}"
    ddl = str(excludes[0].where) + str(excludes[1].where)
    assert "sobre_turno" in ddl
    checks = " ".join(str(c.sqltext) for c in tabla.constraints if c.__class__.__name__ == "CheckConstraint")
    assert "fin" in checks and "inicio" in checks
    assert issubclass(Turno, Base)
    assert Turno.__tablename__ == "turno"


def test_turno_token_nullable_y_defaults():
    """Triangulacion: token nullable, sobre_turno default false, estado pendiente."""
    from app.modelos import Base

    tabla = Base.metadata.tables["turno"]
    assert tabla.c.token_confirmacion_hash.nullable is True
    assert tabla.c.sobre_turno.nullable is False
    assert tabla.c.estado.server_default is not None


@pytest.mark.asyncio
async def test_turno_mapeo_redondo_pg(sesion_pg):
    """Task 1.2 GREEN: insert+select por repo contra PG real."""
    from app.modelos import Paciente, Profesional, Sillon
    from app.repos.turno_repo import TurnoRepository

    ahora = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    paciente = Paciente(nombre="Demo", apellido="Redondo", consentimiento_datos=True)
    profesional = Profesional(matricula="C04-0001", agenda_config={})
    sillon = Sillon(nombre="Sillón C04-1")
    sesion_pg.add_all([paciente, profesional, sillon])
    await sesion_pg.flush()
    repo = TurnoRepository(sesion_pg)
    turno = await repo.crear(
        paciente_id=paciente.id,
        profesional_id=profesional.id,
        sillon_id=sillon.id,
        inicio=ahora,
        fin=ahora + timedelta(minutes=30),
    )
    await sesion_pg.commit()
    leido = await repo.get(turno.id)
    assert leido is not None
    assert leido.estado == "pendiente"
    assert leido.sobre_turno is False
    assert leido.token_confirmacion_hash is None
