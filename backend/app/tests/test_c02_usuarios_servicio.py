"""C-02 task 2.3: guard ultimo-admin a nivel servicio (RN-AU-03).

Unit con repos mockeados (siempre corre) + integracion en PG real.
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: F401  (fixture PG real con skip sin Docker)


def _usuario(id, rol_nombre, activo=True):
    return SimpleNamespace(
        id=id, rol=SimpleNamespace(nombre=rol_nombre), activo=activo
    )


def _repo_mock(usuario, admins_activos):
    async def _actualizar(ent, **cambios):
        for k, v in cambios.items():
            setattr(ent, k, v)
        return ent

    repo = AsyncMock()
    repo.get.return_value = usuario
    repo.listar_admins_activos.return_value = admins_activos
    repo.actualizar.side_effect = _actualizar
    return repo


@pytest.mark.asyncio
async def test_deshabilitar_ultimo_admin_bloqueado():
    """Task 2.3 RED->GREEN: desactivar al unico admin activo aborta."""
    from app.servicios.usuarios_servicio import (
        UltimoAdminError,
        desactivar_usuario,
    )

    unico = _usuario(1, "admin", activo=True)
    repo = _repo_mock(unico, [unico])
    with pytest.raises(UltimoAdminError):
        await desactivar_usuario(repo, 1)
    repo.actualizar.assert_not_called()
    assert unico.activo is True


@pytest.mark.asyncio
async def test_deshabilitar_con_otro_admin_ok():
    """Triangulacion: con 2 admins activos, desactivar uno funciona."""
    from app.servicios.usuarios_servicio import desactivar_usuario

    objetivo = _usuario(1, "admin", activo=True)
    otro = _usuario(2, "admin", activo=True)
    repo = _repo_mock(objetivo, [objetivo, otro])
    resultado = await desactivar_usuario(repo, 1)
    assert resultado.activo is False
    repo.actualizar.assert_called_once()


@pytest.mark.asyncio
async def test_deshabilitar_no_admin_ok_sin_contar():
    """Triangulacion: desactivar secretaria no consulta admins."""
    from app.servicios.usuarios_servicio import desactivar_usuario

    secre = _usuario(5, "secretaria", activo=True)
    repo = _repo_mock(secre, [])
    resultado = await desactivar_usuario(repo, 5)
    assert resultado.activo is False
    repo.listar_admins_activos.assert_not_called()


@pytest.mark.asyncio
async def test_eliminar_ultimo_admin_bloqueado():
    """Task 2.3: eliminar al unico admin activo aborta."""
    from app.servicios.usuarios_servicio import UltimoAdminError, eliminar_usuario

    unico = _usuario(1, "admin", activo=True)
    repo = _repo_mock(unico, [unico])
    with pytest.raises(UltimoAdminError):
        await eliminar_usuario(repo, 1)
    repo.eliminar.assert_not_called()


@pytest.mark.asyncio
async def test_usuario_inexistente_falla_explicito():
    """Triangulacion: id inexistente -> UsuarioNoEncontradoError."""
    from app.servicios.usuarios_servicio import (
        UsuarioNoEncontradoError,
        desactivar_usuario,
    )

    repo = AsyncMock()
    repo.get.return_value = None
    with pytest.raises(UsuarioNoEncontradoError):
        await desactivar_usuario(repo, 999)


@pytest.mark.asyncio
async def test_deshabilitar_ultimo_admin_bloqueado_integracion(sesion_pg):
    """Task 2.3 integracion PG: el admin sigue activo tras el bloqueo."""
    from app.repos import RolRepository, UsuarioRepository
    from app.servicios.usuarios_servicio import (
        UltimoAdminError,
        desactivar_usuario,
    )

    rol_repo = RolRepository(sesion_pg)
    usu_repo = UsuarioRepository(sesion_pg)
    rol = await rol_repo.crear(nombre="admin")
    admin = await usu_repo.crear(
        nombre="Admin Unico",
        email="unico@demo.test",
        password_hash="placeholder",
        rol_id=rol.id,
    )
    with pytest.raises(UltimoAdminError):
        await desactivar_usuario(usu_repo, admin.id)
    # Sin rollback: el servicio aborta ANTES de escribir, y un rollback aqui
    # borraria tambien el setup (rol+admin solo con flush, sin commit) dejando
    # get(admin.id) en None. La fixture ya limpia al final del test.
    sigue = await usu_repo.get(admin.id)
    assert sigue.activo is True
