"""C-04 tasks 4.1/4.2: GET /disponibilidad y GET /agenda via HTTP con fakes.

Disponibilidad respeta horario y turnos; fuera de horario vacia.
Agenda dia ordenada por inicio; vista invalida 422.
"""
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c03_fakes import FakeRepo, fabricar_usuario
from c04_fakes import FakeEntidadRepo, FakeProfesionalRepo, FakeTurnoRepo, fabricar_turno

MARTES = date(2026, 10, 13)  # martes (sin horario demo: solo lunes)


def _profesional_demo(**cambios):
    datos = {
        "id": 1,
        "matricula": "C04-AG1",
        "agenda_config": {
            "duracion_slot_min": 30,
            "horario": {"lunes": [["08:00", "12:00"]]},
        },
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def _app_con(usuarios, turnos=None, profesionales=None):
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
    app.dependency_overrides[get_usuario_repo] = lambda: FakeRepo(usuarios)
    app.dependency_overrides[get_turno_repo] = lambda: FakeTurnoRepo(turnos)
    app.dependency_overrides[get_paciente_repo] = lambda: FakeEntidadRepo(
        [SimpleNamespace(id=1, nombre="Demo", apellido="Paciente")]
    )
    app.dependency_overrides[get_profesional_repo] = lambda: FakeProfesionalRepo(
        profesionales if profesionales is not None else [_profesional_demo()]
    )
    app.dependency_overrides[get_sillon_repo] = lambda: FakeEntidadRepo(
        [SimpleNamespace(id=1, nombre="Sillón 1")]
    )

    async def _db():
        class _S:
            async def commit(self):
                return None

            async def rollback(self):
                return None

        yield _S()

    app.dependency_overrides[get_db] = _db

    def _bearer(uid: int, rol: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {crear_access_token(uid, rol)}"}

    return app, AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), _bearer


@pytest.mark.asyncio
async def test_disponibilidad_respeta_horario_y_turnos():
    """Task 4.1 RED: lunes con turno 09:00-09:30 no ofrece 09:00."""
    ocupado = fabricar_turno(
        id=1,
        inicio=datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc),  # 09:00 BA
        fin=datetime(2026, 10, 12, 12, 30, tzinfo=timezone.utc),
        estado="confirmado",
    )
    _, cliente, bearer = _app_con(
        [fabricar_usuario(id=1, rol="secretaria")], [ocupado]
    )
    async with cliente as cli:
        resp = await cli.get(
            "/disponibilidad",
            params={
                "profesional_id": 1,
                "desde": "2026-10-12T00:00:00+00:00",
                "hasta": "2026-10-13T00:00:00+00:00",
            },
            headers=bearer(1, "secretaria"),
        )
    assert resp.status_code == 200, resp.text
    inicios = [h["inicio"] for h in resp.json()]
    assert len(inicios) == 7  # 8 slots menos el ocupado
    assert not any("12:00:00" in h for h in inicios)


@pytest.mark.asyncio
async def test_disponibilidad_fuera_horario_vacia():
    """Task 4.1 RED: martes sin horario -> [] (nunca huecos inventados)."""
    _, cliente, bearer = _app_con([fabricar_usuario(id=1, rol="secretaria")])
    async with cliente as cli:
        resp = await cli.get(
            "/disponibilidad",
            params={
                "profesional_id": 1,
                "desde": "2026-10-13T00:00:00+00:00",
                "hasta": "2026-10-14T00:00:00+00:00",
            },
            headers=bearer(1, "secretaria"),
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_agenda_dia_lista_ordenada():
    """Task 4.2 RED: vista dia con turnos ordenados y estado visible."""
    t_tarde = fabricar_turno(
        id=2,
        inicio=datetime(2026, 10, 12, 14, 0, tzinfo=timezone.utc),
        fin=datetime(2026, 10, 12, 14, 30, tzinfo=timezone.utc),
        estado="pendiente",
    )
    t_madrugada = fabricar_turno(
        id=1,
        inicio=datetime(2026, 10, 12, 11, 0, tzinfo=timezone.utc),
        fin=datetime(2026, 10, 12, 11, 30, tzinfo=timezone.utc),
        estado="confirmado",
    )
    _, cliente, bearer = _app_con(
        [fabricar_usuario(id=2, rol="odontologo")],
        [t_tarde, t_madrugada],
        [_profesional_demo(usuario_id=2)],
    )
    async with cliente as cli:
        resp = await cli.get(
            "/agenda",
            params={"vista": "dia", "fecha": "2026-10-12"},
            headers=bearer(2, "odontologo"),
        )
    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert [t["id"] for t in cuerpo] == [1, 2]
    assert cuerpo[0]["estado"] == "confirmado"
    assert cuerpo[0]["paciente_nombre"] == "Demo Paciente"
    assert cuerpo[0]["sillon_nombre"] == "Sillón 1"


@pytest.mark.asyncio
async def test_agenda_vista_invalida_422():
    """Task 4.2 RED: vista=anio -> 422; sin Bearer -> 401."""
    _, cliente, bearer = _app_con([fabricar_usuario(id=1, rol="secretaria")])
    async with cliente as cli:
        mala = await cli.get(
            "/agenda", params={"vista": "anio", "fecha": "2026-10-12"},
            headers=bearer(1, "secretaria"),
        )
        assert mala.status_code == 422
        assert (await cli.get("/agenda", params={"vista": "dia", "fecha": "2026-10-12"})).status_code == 401
