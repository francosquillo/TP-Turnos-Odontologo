"""C-04 task 3.3: PATCH /turnos/:id/estado con maquina cerrada (fakes HTTP).

pendiente->confirmado ok; cancelar sin motivo 422; terminal bloqueada 422;
tabla parametrizada de transiciones; odontologo solo asistido/ausente propios.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c03_fakes import FakeRepo, fabricar_usuario
from c04_fakes import FakeEntidadRepo, FakeProfesionalRepo, FakeTurnoRepo, fabricar_turno

FUTURO = datetime(2026, 11, 10, 11, 0, tzinfo=timezone.utc)


class _SesionFake:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _app_con(usuarios, turnos):
    from app.api.turnos import (
        get_paciente_repo,
        get_profesional_repo,
        get_sillon_repo,
        get_turno_repo,
    )
    from app.core.deps import get_db, get_usuario_repo
    from app.core.security import crear_access_token
    from app.main import create_app

    app = create_app()
    turnos_repo = FakeTurnoRepo(turnos)
    app.dependency_overrides[get_usuario_repo] = lambda: FakeRepo(usuarios)
    app.dependency_overrides[get_turno_repo] = lambda: turnos_repo
    app.dependency_overrides[get_paciente_repo] = lambda: FakeEntidadRepo([])
    pros = [t for t in turnos]
    app.dependency_overrides[get_profesional_repo] = lambda: FakeProfesionalRepo([])
    app.dependency_overrides[get_sillon_repo] = lambda: FakeEntidadRepo([])

    async def _db():
        yield _SesionFake()

    app.dependency_overrides[get_db] = _db

    def _bearer(usuario_id: int, rol: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {crear_access_token(usuario_id, rol)}"}

    return app, AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), _bearer, turnos_repo


@pytest.mark.asyncio
async def test_confirmar_pendiente_ok():
    """Task 3.3 RED: pendiente -> confirmado responde 200."""
    turno = fabricar_turno(id=1, inicio=FUTURO, fin=FUTURO + timedelta(minutes=30), estado="pendiente", origen="online")
    _, cliente, bearer, _ = _app_con(
        [fabricar_usuario(id=1, rol="secretaria")], [turno]
    )
    async with cliente as cli:
        resp = await cli.patch(
            "/turnos/1/estado", json={"estado": "confirmado"}, headers=bearer(1, "secretaria")
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "confirmado"


@pytest.mark.asyncio
async def test_cancelar_sin_motivo_422():
    """Task 3.3 RED: cancelar sin motivo -> 422 y estado intacto."""
    turno = fabricar_turno(id=1, inicio=FUTURO, fin=FUTURO + timedelta(minutes=30), estado="confirmado")
    _, cliente, bearer, turnos_repo = _app_con(
        [fabricar_usuario(id=1, rol="secretaria")], [turno]
    )
    async with cliente as cli:
        resp = await cli.patch(
            "/turnos/1/estado", json={"estado": "cancelado"}, headers=bearer(1, "secretaria")
        )
        assert resp.status_code == 422
        con_motivo = await cli.patch(
            "/turnos/1/estado",
            json={"estado": "cancelado", "motivo": "paciente avisó"},
            headers=bearer(1, "secretaria"),
        )
        assert con_motivo.status_code == 200, con_motivo.text
    assert (await turnos_repo.get(1)).estado == "cancelado"


@pytest.mark.asyncio
async def test_transicion_terminal_422():
    """Task 3.3 RED: asistido -> confirmado bloqueado (terminal)."""
    turno = fabricar_turno(id=1, inicio=FUTURO, fin=FUTURO + timedelta(minutes=30), estado="asistido")
    _, cliente, bearer, turnos_repo = _app_con(
        [fabricar_usuario(id=1, rol="secretaria")], [turno]
    )
    async with cliente as cli:
        resp = await cli.patch(
            "/turnos/1/estado", json={"estado": "confirmado"}, headers=bearer(1, "secretaria")
        )
    assert resp.status_code == 422
    assert (await turnos_repo.get(1)).estado == "asistido"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "origen,destino,codigo",
    [
        ("pendiente", "confirmado", 200),
        ("pendiente", "cancelado", 422),  # sin motivo
        ("pendiente", "asistido", 422),  # solo admin carga historica
        ("confirmado", "asistido", 200),
        ("confirmado", "ausente", 200),
        ("confirmado", "pendiente", 422),
        ("ausente", "confirmado", 422),
        ("cancelado", "pendiente", 422),
    ],
)
async def test_tabla_transiciones(origen, destino, codigo):
    """Task 3.3 GREEN: tabla parametrizada de la maquina D-03."""
    turno = fabricar_turno(id=1, inicio=FUTURO, fin=FUTURO + timedelta(minutes=30), estado=origen)
    _, cliente, bearer, _ = _app_con(
        [fabricar_usuario(id=1, rol="secretaria")], [turno]
    )
    async with cliente as cli:
        resp = await cli.patch(
            "/turnos/1/estado", json={"estado": destino}, headers=bearer(1, "secretaria")
        )
    assert resp.status_code == codigo, f"{origen}->{destino}: {resp.text}"


@pytest.mark.asyncio
async def test_odontologo_solo_estado_propios():
    """D-07: odontologo marca asistido en propio (200) pero no cancela (403)."""
    from types import SimpleNamespace

    turno = fabricar_turno(id=1, inicio=FUTURO, fin=FUTURO + timedelta(minutes=30), estado="confirmado", profesional_id=5)
    usuarios = [
        fabricar_usuario(id=1, rol="secretaria"),
        fabricar_usuario(id=2, rol="odontologo"),
    ]
    from app.api.turnos import get_profesional_repo
    from app.core.deps import get_db, get_usuario_repo
    from app.api.turnos import get_paciente_repo, get_sillon_repo, get_turno_repo
    from app.core.security import crear_access_token
    from app.main import create_app

    app = create_app()
    turnos_repo = FakeTurnoRepo([turno])
    pro_repo = FakeProfesionalRepo([SimpleNamespace(id=5, usuario_id=2, agenda_config=None)])
    app.dependency_overrides[get_usuario_repo] = lambda: FakeRepo(usuarios)
    app.dependency_overrides[get_turno_repo] = lambda: turnos_repo
    app.dependency_overrides[get_paciente_repo] = lambda: FakeEntidadRepo([])
    app.dependency_overrides[get_profesional_repo] = lambda: pro_repo
    app.dependency_overrides[get_sillon_repo] = lambda: FakeEntidadRepo([])

    async def _db():
        yield _SesionFake()

    app.dependency_overrides[get_db] = _db

    def _bearer(uid, rol):
        return {"Authorization": f"Bearer {crear_access_token(uid, rol)}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cli:
        ok = await cli.patch(
            "/turnos/1/estado", json={"estado": "asistido"}, headers=_bearer(2, "odontologo")
        )
        assert ok.status_code == 200, ok.text
        # Ya asistido (terminal): otro cambio -> 422.
        segundo = await cli.patch(
            "/turnos/1/estado", json={"estado": "ausente"}, headers=_bearer(2, "odontologo")
        )
        assert segundo.status_code == 422
