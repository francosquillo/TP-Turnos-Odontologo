"""C-06 task 5.4 RED: GET /notificaciones/pendientes staff sin PHI (D-06).

Solo fallidas proyectadas a {turno_id, inicio, paciente_nombre, motivo},
paginado, con require_role(secretaria|admin). Sin Bearer 401; rol paciente
403; nunca campos clinicos. Datos ficticios.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c03_fakes import FakeRepo, fabricar_usuario  # noqa: E402
from c04_fakes import fabricar_turno  # noqa: E402
from c05_fakes import FakePacienteRepo, fabricar_paciente  # noqa: E402
from c06_fakes import FakeNotifRepo, FakeTurnoRepoC06  # noqa: E402

FUTURO = datetime(2026, 11, 10, 11, 0, tzinfo=timezone.utc)


def _app_con(rol="secretaria"):
    from app.api.notificaciones import (
        get_notif_repo,
        get_paciente_repo_notif,
        get_turno_repo_notif,
    )
    from app.core.deps import get_db, get_usuario_repo
    from app.core.security import crear_access_token
    from app.main import create_app

    app = create_app()
    turnos = FakeTurnoRepoC06([fabricar_turno(
        id=1, paciente_id=5, estado="pendiente", inicio=FUTURO,
        fin=FUTURO + timedelta(minutes=30))])
    pacientes = FakePacienteRepo(
        [fabricar_paciente(id=5, nombre="Ana", telefono=None, email=None)])
    notifs = FakeNotifRepo()
    app.dependency_overrides[get_usuario_repo] = lambda: FakeRepo(
        [fabricar_usuario(id=1, rol=rol)]
    )
    app.dependency_overrides[get_turno_repo_notif] = lambda: turnos
    app.dependency_overrides[get_paciente_repo_notif] = lambda: pacientes
    app.dependency_overrides[get_notif_repo] = lambda: notifs

    class _S:
        async def commit(self):
            return None

        async def rollback(self):
            return None

    async def _db():
        yield _S()

    app.dependency_overrides[get_db] = _db
    bearer = {"Authorization": f"Bearer {crear_access_token(1, rol)}"}
    cliente = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return app, cliente, bearer, notifs


@pytest.mark.asyncio
async def test_pendientes_staff_ok_sin_phi():
    """Task 5.4 RED: secretaria ve fallidas proyectadas sin campos clinicos."""
    _, cliente, bearer, notifs = _app_con("secretaria")
    await notifs.crear(
        turno_id=1, canal="whatsapp", plantilla="recordatorio_48h",
        estado="fallida", payload={"nombre_pila": "Ana"},
        ultimo_error="sin_numero_valido",
    )
    async with cliente as cli:
        resp = await cli.get("/notificaciones/pendientes", headers=bearer)
    assert resp.status_code == 200, resp.text
    elementos = resp.json()
    assert len(elementos) == 1
    unico = elementos[0]
    assert set(unico) == {"turno_id", "inicio", "paciente_nombre", "motivo"}
    assert unico["turno_id"] == 1
    assert unico["paciente_nombre"] == "Ana"
    assert unico["motivo"] == "sin_numero_valido"
    crudo = resp.text.lower()
    for prohibido in ("caries", "diagnost", "telefono", "114000", "historia"):
        assert prohibido not in crudo


@pytest.mark.asyncio
async def test_pendientes_sin_bearer_401():
    """Task 5.4 RED: sin Bearer -> 401; rol paciente -> 403."""
    _, cliente, _, notifs = _app_con("secretaria")
    await notifs.crear(
        turno_id=1, canal="whatsapp", plantilla="recordatorio_48h",
        estado="fallida", payload={"nombre_pila": "Ana"},
        ultimo_error="sin_numero_valido",
    )
    async with cliente as cli:
        anonimo = await cli.get("/notificaciones/pendientes")
        assert anonimo.status_code == 401
    _, cliente_p, bearer_p, _ = _app_con("paciente")
    async with cliente_p as cli:
        assert (await cli.get("/notificaciones/pendientes",
                              headers=bearer_p)).status_code in (401, 403)
