"""C-02 tasks 3.1-3.3: Paciente (CRUD + soft-delete + DNI) contra PG real."""
import sys
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: F401  (fixture PG real con skip sin Docker)


@pytest.mark.asyncio
async def test_crud_paciente_ficticio_ok(sesion_pg):
    """Task 3.1 GREEN: crear/leer/actualizar paciente ficticio."""
    from app.repos import PacienteRepository

    repo = PacienteRepository(sesion_pg)
    creado = await repo.crear(
        nombre="Juan",
        apellido="Demo",
        dni="30000001",
        telefono="1100000001",
        consentimiento_datos=True,
    )
    assert creado.id is not None
    leido = await repo.get(creado.id)
    assert leido.apellido == "Demo"
    actualizado = await repo.actualizar(leido, telefono="1100000002")
    assert actualizado.telefono == "1100000002"


@pytest.mark.asyncio
async def test_paciente_soft_delete_oculto_en_listado(sesion_pg):
    """Task 3.2 GREEN: eliminado no lista pero la fila persiste con deleted_at."""
    from sqlalchemy import select
    from app.modelos import Paciente
    from app.repos import PacienteRepository

    repo = PacienteRepository(sesion_pg)
    paciente = await repo.crear(
        nombre="Ana", apellido="Demo", consentimiento_datos=True
    )
    await repo.soft_delete(paciente)
    activos = await repo.listar_activos()
    assert all(p.id != paciente.id for p in activos)
    fila = (
        await sesion_pg.execute(
            select(Paciente).where(Paciente.id == paciente.id)
        )
    ).scalar_one()
    assert fila.deleted_at is not None, "soft-delete debe setear deleted_at"


@pytest.mark.asyncio
async def test_dni_duplicado_rechazado_y_nulo_multiple_permitido(sesion_pg):
    """Task 3.3 GREEN: mismo DNI -> IntegrityError; dos NULL -> ok."""
    from app.repos import PacienteRepository

    repo = PacienteRepository(sesion_pg)
    await repo.crear(
        nombre="Uno", apellido="Demo", dni="30000002", consentimiento_datos=True
    )
    with pytest.raises(IntegrityError):
        await repo.crear(
            nombre="Dos", apellido="Demo", dni="30000002", consentimiento_datos=True
        )
    await sesion_pg.rollback()
    await repo.crear(nombre="Tres", apellido="Demo", consentimiento_datos=True)
    await repo.crear(nombre="Cuatro", apellido="Demo", consentimiento_datos=True)
