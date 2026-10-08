"""C-02 task 5.1: base repository generico async + repos que heredan."""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: F401  (fixture PG real con skip sin Docker)


def test_repos_heredan_de_base_sin_duplicar():
    """Task 5.1 RED: los 5 repos heredan BaseRepository (unit, sin DB)."""
    from app.repos import (
        PacienteRepository,
        ProfesionalRepository,
        RolRepository,
        SillonRepository,
        UsuarioRepository,
        BaseRepository,
    )

    for repo_cls in (
        RolRepository,
        UsuarioRepository,
        PacienteRepository,
        ProfesionalRepository,
        SillonRepository,
    ):
        assert issubclass(repo_cls, BaseRepository), (
            f"{repo_cls.__name__} debe heredar BaseRepository"
        )
    for metodo in ("get", "list", "crear", "actualizar", "eliminar"):
        assert callable(getattr(BaseRepository, metodo)), (
            f"BaseRepository debe exponer {metodo}"
        )


@pytest.mark.asyncio
async def test_repos_heredan_crud_base(sesion_pg):
    """Task 5.1 GREEN: listar pacientes + get sillon via base generica (PG real)."""
    from app.modelos import Sillon
    from app.repos import PacienteRepository, SillonRepository

    pac_repo = PacienteRepository(sesion_pg)
    sil_repo = SillonRepository(sesion_pg)
    await pac_repo.crear(nombre="Base", apellido="Demo", consentimiento_datos=True)
    pacientes = await pac_repo.list()
    assert len(pacientes) >= 1
    creado = await sil_repo.crear(nombre="Sillón Base 1")
    leido = await sil_repo.get(creado.id)
    assert isinstance(leido, Sillon)
    assert leido.nombre == "Sillón Base 1"
    actualizado = await sil_repo.actualizar(leido, activo=False)
    assert actualizado.activo is False
