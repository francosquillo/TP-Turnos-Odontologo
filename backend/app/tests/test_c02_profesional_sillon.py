"""C-02 task 4.1: Profesional + Sillon (demo operativa)."""
import sys
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: F401  (fixture PG real con skip sin Docker)

AGENDA_DEMO = {
    "duracion_slot_min": 30,
    "horario": {"lunes": [["09:00", "13:00"]]},
}


@pytest.mark.asyncio
async def test_profesional_demo_agenda_valida(sesion_pg):
    """Task 4.1 GREEN: profesional demo con agenda semanal valida."""
    from app.esquemas.profesional import AgendaConfig
    from app.repos import ProfesionalRepository

    repo = ProfesionalRepository(sesion_pg)
    prof = await repo.crear(
        matricula="DEMO-0001",
        especialidades="Odontología general",
        agenda_config=AGENDA_DEMO,
    )
    assert prof.id is not None
    assert prof.usuario_id is None, "profesional demo sin cuenta (nullable)"
    agenda = AgendaConfig.model_validate(prof.agenda_config)
    assert agenda.duracion_slot_min > 0


@pytest.mark.asyncio
async def test_sillon_sede_texto_libre_default_y_nombre_unico(sesion_pg):
    """Spec: sillon con sede texto por defecto y nombre unico."""
    from app.repos import SillonRepository

    repo = SillonRepository(sesion_pg)
    sillon = await repo.crear(nombre="Sillón Demo 1")
    assert sillon.sede == "Sede única", "default sede unica v1.0 (texto libre)"
    assert sillon.activo is True
    with pytest.raises(IntegrityError):
        await repo.crear(nombre="Sillón Demo 1")


@pytest.mark.asyncio
async def test_profesional_usuario_nullable_set_null(sesion_pg):
    """D-05: borrar usuario deja profesional.usuario_id en NULL."""
    from app.modelos import Profesional
    from app.repos import ProfesionalRepository, RolRepository, UsuarioRepository

    rol_repo = RolRepository(sesion_pg)
    usu_repo = UsuarioRepository(sesion_pg)
    prof_repo = ProfesionalRepository(sesion_pg)
    rol = await rol_repo.crear(nombre="odontologo")
    usuario = await usu_repo.crear(
        nombre="Odonto Demo",
        email="odonto@demo.test",
        password_hash="placeholder",
        rol_id=rol.id,
    )
    prof = await prof_repo.crear(
        matricula="DEMO-0002",
        especialidades="Ortodoncia",
        usuario_id=usuario.id,
        agenda_config=AGENDA_DEMO,
    )
    await usu_repo.eliminar(usuario)
    await sesion_pg.flush()
    # El SET NULL lo aplica Postgres por FK; la instancia ORM en el identity
    # map queda con el valor viejo hasta refrescar -> refresh antes de leer.
    await sesion_pg.refresh(prof)
    leido = await prof_repo.get(prof.id)
    assert isinstance(leido, Profesional)
    assert leido.usuario_id is None
