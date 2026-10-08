"""C-02 tasks 2.1 + 2.4: Rol + Usuario (identidad, FK simple) contra PG real."""
import sys
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: F401  (fixture PG real con skip sin Docker)


@pytest.mark.asyncio
async def test_crear_usuario_con_rol_valido_persiste(sesion_pg):
    """Task 2.1 GREEN: usuario con rol secretaria persiste activo y con tz."""
    from app.modelos import Rol, Usuario
    from app.repos import RolRepository, UsuarioRepository

    rol_repo = RolRepository(sesion_pg)
    usu_repo = UsuarioRepository(sesion_pg)
    rol = await rol_repo.crear(nombre="secretaria")
    usuario = await usu_repo.crear(
        nombre="Secre Demo",
        email="secre@demo.test",
        password_hash="placeholder",
        rol_id=rol.id,
    )
    assert usuario.id is not None
    assert usuario.activo is True
    assert usuario.created_at is not None
    assert usuario.created_at.tzinfo is not None, "created_at debe tener zona horaria"


@pytest.mark.asyncio
async def test_rol_fuera_de_catalogo_rechazado(sesion_pg):
    """Spec: nombre de rol fuera del catalogo viola CHECK (sin rol dueno)."""
    from sqlalchemy import text

    # El CHECK rechaza en el execute (no espera al flush): ambas llamadas
    # van dentro del bloque que exige IntegrityError.
    with pytest.raises(IntegrityError):
        await sesion_pg.execute(
            text("INSERT INTO rol (nombre) VALUES ('dueno')")
        )
        await sesion_pg.flush()


@pytest.mark.asyncio
async def test_usuario_sin_rol_valido_rechazado(sesion_pg):
    """FK rol simple: rol_id inexistente viola la FK."""
    from app.repos import UsuarioRepository

    usu_repo = UsuarioRepository(sesion_pg)
    with pytest.raises(IntegrityError):
        await usu_repo.crear(
            nombre="Sin Rol",
            email="sinrol@demo.test",
            password_hash="placeholder",
            rol_id=999999,
        )


@pytest.mark.asyncio
async def test_email_duplicado_case_insensitive_rechazado(sesion_pg):
    """Task 2.4 GREEN: Admin@demo.test vs admin@demo.test -> IntegrityError."""
    from app.repos import RolRepository, UsuarioRepository

    rol_repo = RolRepository(sesion_pg)
    usu_repo = UsuarioRepository(sesion_pg)
    rol = await rol_repo.crear(nombre="admin")
    await usu_repo.crear(
        nombre="Admin Uno",
        email="Admin@demo.test",
        password_hash="placeholder",
        rol_id=rol.id,
    )
    with pytest.raises(IntegrityError):
        await usu_repo.crear(
            nombre="Admin Dos",
            email="admin@demo.test",
            password_hash="placeholder",
            rol_id=rol.id,
        )


def test_usuario_un_solo_rol_por_modelo():
    """Spec: segundo rol imposible por modelo (sin tabla usuario_rol)."""
    from app.modelos import Base, Usuario

    assert "usuario_rol" not in Base.metadata.tables, (
        "NUNCA tabla usuario_rol (IN-02): rol simple por FK"
    )
    assert "rol_id" in Usuario.__table__.columns, "usuario debe tener rol_id FK simple"
    assert "dueno" not in [
        c.name for c in Usuario.__table__.columns
    ], "usuario no debe tener campo de segundo rol"
