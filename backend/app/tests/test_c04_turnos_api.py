"""C-04 tasks 3.2 + 3.4: CRUD /turnos y reprogramacion via HTTP con fakes.

Sin PG: dependency_overrides con FakeRepos (patron C-03). RBAC D-07:
admin|secretaria escriben, odontologo no crea; sin Bearer 401.
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
from c04_fakes import (
    FakeEntidadRepo,
    FakeProfesionalRepo,
    FakeTurnoRepo,
    fabricar_entidad,
    fabricar_turno,
)

FUTURO = datetime(2026, 11, 10, 11, 0, tzinfo=timezone.utc)  # martes


class _SesionFake:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


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
    turnos_repo = FakeTurnoRepo(turnos)
    app.dependency_overrides[get_usuario_repo] = lambda: FakeRepo(usuarios)
    app.dependency_overrides[get_turno_repo] = lambda: turnos_repo
    app.dependency_overrides[get_paciente_repo] = lambda: FakeEntidadRepo(
        [fabricar_entidad(1)]
    )
    app.dependency_overrides[get_profesional_repo] = lambda: FakeProfesionalRepo(
        profesionales if profesionales is not None else [fabricar_entidad(1)]
    )
    app.dependency_overrides[get_sillon_repo] = lambda: FakeEntidadRepo(
        [fabricar_entidad(1)]
    )

    async def _db():
        yield _SesionFake()

    app.dependency_overrides[get_db] = _db
    transporte = ASGITransport(app=app)
    cliente = AsyncClient(transport=transporte, base_url="http://test")

    def _bearer(usuario_id: int, rol: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {crear_access_token(usuario_id, rol)}"}

    return app, cliente, _bearer, turnos_repo


def _cuerpo(inicio=FUTURO, **cambios) -> dict:
    datos = {
        "paciente_id": 1,
        "profesional_id": 1,
        "sillon_id": 1,
        "inicio": inicio.isoformat(),
        "fin": (inicio + timedelta(minutes=30)).isoformat(),
    }
    datos.update(cambios)
    return datos


@pytest.mark.asyncio
async def test_post_turno_ok_201():
    """Task 3.2 RED: secretaria crea turno valido -> 201 confirmado."""
    _, cliente, bearer, _ = _app_con([fabricar_usuario(id=1, rol="secretaria")])
    async with cliente as cli:
        resp = await cli.post("/turnos", json=_cuerpo(), headers=bearer(1, "secretaria"))
    assert resp.status_code == 201, resp.text
    cuerpo = resp.json()
    assert cuerpo["estado"] == "confirmado"
    assert cuerpo["sobre_turno"] is False
    assert "token_confirmacion_hash" not in cuerpo


@pytest.mark.asyncio
async def test_post_turno_solapado_409_con_alternativas():
    """Task 3.2 RED: solape -> 409 con alternativas no vacias."""
    existente = fabricar_turno(
        id=1, inicio=FUTURO, fin=FUTURO + timedelta(minutes=30), estado="confirmado"
    )
    _, cliente, bearer, _ = _app_con(
        [fabricar_usuario(id=1, rol="secretaria")], turnos=[existente]
    )
    async with cliente as cli:
        resp = await cli.post(
            "/turnos",
            json=_cuerpo(inicio=FUTURO + timedelta(minutes=15)),
            headers=bearer(1, "secretaria"),
        )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "hueco ocupado"
    assert len(resp.json()["alternativas"]) > 0


@pytest.mark.asyncio
async def test_get_turnos_sin_bearer_401():
    """Task 3.2 RED: sin Bearer -> 401; odontologo no puede crear -> 403."""
    _, cliente, bearer, _ = _app_con(
        [
            fabricar_usuario(id=1, rol="secretaria"),
            fabricar_usuario(id=2, rol="odontologo"),
        ]
    )
    async with cliente as cli:
        assert (await cli.get("/turnos")).status_code == 401
        assert (await cli.get("/turnos/1")).status_code == 401
        prohibido = await cli.post(
            "/turnos", json=_cuerpo(), headers=bearer(2, "odontologo")
        )
        assert prohibido.status_code == 403


@pytest.mark.asyncio
async def test_post_turno_campo_extra_422_y_pasado_solo_admin():
    """Triangulacion: extra -> 422; pasado secretaria 422 pero admin 201."""
    from freezegun import freeze_time

    _, cliente, bearer, _ = _app_con(
        [
            fabricar_usuario(id=1, rol="secretaria"),
            fabricar_usuario(id=9, rol="admin"),
        ]
    )
    async with cliente as cli:
        extra = await cli.post(
            "/turnos", json=_cuerpo(campo_fantasma=1), headers=bearer(1, "secretaria")
        )
        assert extra.status_code == 422
        with freeze_time("2026-11-01 12:00:00"):
            pasado = {
                "paciente_id": 1,
                "profesional_id": 1,
                "sillon_id": 1,
                "inicio": "2026-10-01T10:00:00+00:00",
                "fin": "2026-10-01T10:30:00+00:00",
            }
            r_secre = await cli.post(
                "/turnos", json=pasado, headers=bearer(1, "secretaria")
            )
            assert r_secre.status_code == 422
            r_admin = await cli.post("/turnos", json=pasado, headers=bearer(9, "admin"))
            assert r_admin.status_code == 201, r_admin.text


@pytest.mark.asyncio
async def test_reprogramar_a_ocupado_409_conserva_horario():
    """Task 3.4 RED: mover a hueco ocupado -> 409 y horario original intacto."""
    t1 = fabricar_turno(
        id=1, inicio=FUTURO, fin=FUTURO + timedelta(minutes=30), estado="confirmado"
    )
    t2 = fabricar_turno(
        id=2,
        inicio=FUTURO + timedelta(hours=1),
        fin=FUTURO + timedelta(hours=1, minutes=30),
        estado="confirmado",
    )
    _, cliente, bearer, turnos_repo = _app_con(
        [fabricar_usuario(id=1, rol="secretaria")], turnos=[t1, t2]
    )
    async with cliente as cli:
        resp = await cli.patch(
            "/turnos/2",
            json={
                "inicio": FUTURO.isoformat(),
                "fin": (FUTURO + timedelta(minutes=30)).isoformat(),
            },
            headers=bearer(1, "secretaria"),
        )
    assert resp.status_code == 409, resp.text
    conservado = await turnos_repo.get(2)
    assert conservado.inicio == FUTURO + timedelta(hours=1)


@pytest.mark.asyncio
async def test_reprogramar_a_libre_ok():
    """Task 3.4 RED: mover a hueco libre -> 200 con nuevo horario."""
    t1 = fabricar_turno(
        id=1, inicio=FUTURO, fin=FUTURO + timedelta(minutes=30), estado="confirmado"
    )
    _, cliente, bearer, _ = _app_con(
        [fabricar_usuario(id=1, rol="secretaria")], turnos=[t1]
    )
    nuevo = FUTURO + timedelta(hours=2)
    async with cliente as cli:
        resp = await cli.patch(
            "/turnos/1",
            json={
                "inicio": nuevo.isoformat(),
                "fin": (nuevo + timedelta(minutes=30)).isoformat(),
            },
            headers=bearer(1, "secretaria"),
        )
    assert resp.status_code == 200, resp.text
    assert datetime.fromisoformat(resp.json()["inicio"]) == nuevo
