"""C-05 task 2.4: GET /disponibilidad publica (RED -> GREEN sin PG).

Rama sin auth junto a la staff (D-04): mismo calculo, solo [{inicio, fin}],
profesional_id siempre requerido. Desvio documentado del delta-spec: anonimo
sin profesional_id -> 422 (nunca vuelca agenda) en vez de 401; staff con
Bearer intacta (401/403 y mismos huecos).
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c03_fakes import FakeRepo, fabricar_usuario  # noqa: E402
from c04_fakes import (  # noqa: E402
    FakeEntidadRepo,
    FakeProfesionalRepo,
    FakeTurnoRepo,
    fabricar_turno,
)

LUNES_DESDE = "2026-10-12T00:00:00+00:00"
LUNES_HASTA = "2026-10-13T00:00:00+00:00"


def _profesional_demo():
    return SimpleNamespace(
        id=1,
        matricula="C05-D1",
        agenda_config={
            "duracion_slot_min": 30,
            "horario": {"lunes": [["08:00", "12:00"]]},
        },
    )


def _app_con(turnos=None):
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
    app.dependency_overrides[get_usuario_repo] = lambda: FakeRepo(
        [fabricar_usuario(id=1, rol="secretaria")]
    )
    app.dependency_overrides[get_turno_repo] = lambda: FakeTurnoRepo(turnos)
    app.dependency_overrides[get_paciente_repo] = lambda: FakeEntidadRepo(
        [SimpleNamespace(id=1)]
    )
    app.dependency_overrides[get_profesional_repo] = lambda: FakeProfesionalRepo(
        [_profesional_demo()]
    )
    app.dependency_overrides[get_sillon_repo] = lambda: FakeEntidadRepo(
        [SimpleNamespace(id=1)]
    )

    async def _db():
        class _S:
            async def commit(self):
                return None

            async def rollback(self):
                return None

        yield _S()

    app.dependency_overrides[get_db] = _db
    cliente = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    def _bearer() -> dict[str, str]:
        return {"Authorization": f"Bearer {crear_access_token(1, 'secretaria')}"}

    return app, cliente, _bearer


@pytest.mark.asyncio
async def test_disponibilidad_publica_sin_bearer_200_sin_pacientes():
    """Task 2.4 RED: publica sin auth excluye 09:00 y no filtra pacientes."""
    ocupado = fabricar_turno(
        id=1,
        inicio=datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc),
        fin=datetime(2026, 10, 12, 12, 30, tzinfo=timezone.utc),
        estado="confirmado",
    )
    _, cliente, _ = _app_con([ocupado])
    async with cliente as cli:
        resp = await cli.get(
            "/disponibilidad",
            params={"profesional_id": 1, "desde": LUNES_DESDE, "hasta": LUNES_HASTA},
        )
    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert len(cuerpo) == 7
    assert not any("12:00:00" in h["inicio"] for h in cuerpo)
    assert all(set(h.keys()) == {"inicio", "fin"} for h in cuerpo)


@pytest.mark.asyncio
async def test_disponibilidad_publica_sin_profesional_422():
    """Task 2.4 RED: sin profesional_id nunca vuelca la agenda (-> 422)."""
    _, cliente, _ = _app_con()
    async with cliente as cli:
        resp = await cli.get(
            "/disponibilidad", params={"desde": LUNES_DESDE, "hasta": LUNES_HASTA}
        )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_disponibilidad_publica_mismos_huecos_que_staff():
    """Task 2.4 RED: staff (Bearer) y publica devuelven identicos huecos."""
    _, cliente, bearer = _app_con()
    params = {"profesional_id": 1, "desde": LUNES_DESDE, "hasta": LUNES_HASTA}
    async with cliente as cli:
        staff = await cli.get("/disponibilidad", params=params, headers=bearer())
        publica = await cli.get("/disponibilidad", params=params)
    assert staff.status_code == 200 and publica.status_code == 200
    assert publica.json() == staff.json()


@pytest.mark.asyncio
async def test_disponibilidad_staff_invalida_401_y_rol_403():
    """Triangulacion: Bearer trucho -> 401; rol ajeno -> 403 (RBAC intacto)."""
    from app.core.deps import get_usuario_repo
    from c03_fakes import FakeRepo

    _, cliente, _ = _app_con()
    async with cliente as cli:
        trucho = await cli.get(
            "/disponibilidad",
            params={"profesional_id": 1, "desde": LUNES_DESDE, "hasta": LUNES_HASTA},
            headers={"Authorization": "Bearer token-trucho"},
        )
        assert trucho.status_code == 401
    app2, cliente2, _ = _app_con()
    app2.dependency_overrides[get_usuario_repo] = lambda: FakeRepo(
        [fabricar_usuario(id=9, rol="paciente")]
    )
    from app.core.security import crear_access_token

    async with cliente2 as cli:
        prohibido = await cli.get(
            "/disponibilidad",
            params={"profesional_id": 1, "desde": LUNES_DESDE, "hasta": LUNES_HASTA},
            headers={"Authorization": f"Bearer {crear_access_token(9, 'paciente')}"},
        )
        assert prohibido.status_code == 403
