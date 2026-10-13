"""C-05 tasks 2.2/2.3: POST /reservas y confirmar por token via HTTP con fakes.

Publico de verdad: sin Bearer (201/200, nunca 401). Sin PG: fakes C-05 +
FakeStore como tienda de usados. Datos 100% ficticios.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c03_fakes import FakeRepo, FakeStore, fabricar_usuario  # noqa: E402
from c04_fakes import FakeEntidadRepo, FakeProfesionalRepo, fabricar_turno  # noqa: E402
from c05_fakes import FakePacienteRepo, FakeTurnoRepoC05  # noqa: E402

LUNES_9 = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)  # 09:00 BA
MARTES_9 = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)  # sin horario


def _app_con(turnos=None, pacientes=None):
    from app.api.turnos import (
        get_paciente_repo,
        get_profesional_repo,
        get_sillon_repo,
        get_turno_repo,
    )
    from app.core.deps import get_db, get_redis, get_usuario_repo
    from app.main import create_app

    app = create_app()
    # Warmup: compila los TypeAdapter de ReservaIn con datetime real.
    # freezegun parchea datetime y Pydantic no puede construirlos en freeze.
    from app.esquemas.reserva import ReservaIn
    from fastapi._compat import get_cached_model_fields

    get_cached_model_fields(ReservaIn)
    turnos_repo = FakeTurnoRepoC05(turnos)
    tienda = FakeStore()
    app.dependency_overrides[get_usuario_repo] = lambda: FakeRepo(
        [fabricar_usuario(id=1, rol="secretaria")]
    )
    app.dependency_overrides[get_turno_repo] = lambda: turnos_repo
    app.dependency_overrides[get_paciente_repo] = lambda: FakePacienteRepo(pacientes)
    app.dependency_overrides[get_profesional_repo] = lambda: FakeProfesionalRepo(
        [SimpleNamespace(id=1)]
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
    app.dependency_overrides[get_redis] = lambda: tienda
    cliente = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return app, cliente, turnos_repo, tienda


def _cuerpo(inicio=LUNES_9, **cambios) -> dict:
    datos = {
        "profesional_id": 1,
        "sillon_id": 1,
        "inicio": inicio.isoformat(),
        "fin": (inicio + timedelta(minutes=30)).isoformat(),
        "nombre": "Ana Ficticia",
        "telefono": "11 5000-2222",
    }
    datos.update(cambios)
    return datos


@pytest.mark.asyncio
async def test_post_reserva_ok_201():
    """Task 2.2 RED: reserva valida sin Bearer -> 201 pendiente + token."""
    from freezegun import freeze_time

    _, cliente, turnos_repo, _ = _app_con()
    with freeze_time("2026-10-05 12:00:00"):
        async with cliente as cli:
            resp = await cli.post("/reservas", json=_cuerpo())
    assert resp.status_code == 201, resp.text
    cuerpo = resp.json()
    assert cuerpo["estado"] == "pendiente"
    assert cuerpo["token"] and cuerpo["expira_en"]
    turno = await turnos_repo.get(cuerpo["turno_id"])
    assert turno.estado == "pendiente" and turno.origen == "online"
    assert turno.sobre_turno is False and turno.creado_por is None
    assert cuerpo["token"] not in (turno.token_confirmacion_hash or "")


@pytest.mark.asyncio
async def test_post_reserva_fuera_horario_no_crea():
    """Task 2.2 RED: martes sin horario -> 409/422 sin crear turno."""
    _, cliente, turnos_repo, _ = _app_con()
    async with cliente as cli:
        resp = await cli.post("/reservas", json=_cuerpo(inicio=MARTES_9))
    assert resp.status_code in (409, 422), resp.text
    assert len(turnos_repo._turnos) == 0


@pytest.mark.asyncio
async def test_post_reserva_sin_bearer_ok():
    """Task 2.2 RED: via publica sin Authorization -> 201 (no 401).

    Triangula que lo protegido sigue cerrado: GET /turnos sin Bearer -> 401.
    """
    from freezegun import freeze_time

    _, cliente, _, _ = _app_con()
    with freeze_time("2026-10-05 12:00:00"):
        async with cliente as cli:
            ok = await cli.post("/reservas", json=_cuerpo())
            assert ok.status_code == 201, ok.text
            assert (await cli.get("/turnos")).status_code == 401


@pytest.mark.asyncio
async def test_post_reserva_hueco_ocupado_409_con_alternativas():
    """Triangulacion: hueco tomado -> 409 con re-oferta, sin duplicar."""
    ocupado = fabricar_turno(
        id=1, inicio=LUNES_9, fin=LUNES_9 + timedelta(minutes=30),
        estado="confirmado",
    )
    _, cliente, turnos_repo, _ = _app_con(turnos=[ocupado])
    async with cliente as cli:
        resp = await cli.post("/reservas", json=_cuerpo())
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "hueco ocupado"
    assert len(resp.json()["alternativas"]) > 0
    assert len(turnos_repo._turnos) == 1


@pytest.mark.asyncio
async def test_post_reserva_invalida_422():
    """Triangulacion: extra/nombre corto/telefono corto -> 422 sin persistir."""
    _, cliente, turnos_repo, _ = _app_con()
    async with cliente as cli:
        assert (await cli.post("/reservas", json=_cuerpo(campo_x=1))).status_code == 422
        assert (await cli.post("/reservas", json=_cuerpo(nombre="A"))).status_code == 422
        assert (await cli.post("/reservas", json=_cuerpo(telefono="123"))).status_code == 422
    assert len(turnos_repo._turnos) == 0


@pytest.mark.asyncio
async def test_confirmar_endpoint_200_actualiza_agenda():
    """Task 2.3 RED: GET /confirmar/:token valido -> 200 confirmado."""
    from freezegun import freeze_time

    _, cliente, turnos_repo, _ = _app_con()
    with freeze_time("2026-10-05 12:00:00"):
        async with cliente as cli:
            token = (await cli.post("/reservas", json=_cuerpo())).json()["token"]
            resp = await cli.get(f"/confirmar/{token}")
    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert cuerpo["estado"] == "confirmado"
    assert cuerpo["profesional_id"] == 1
    assert "token" not in cuerpo  # nunca expone turnos ajenos ni reemite
    turno = await turnos_repo.get(1)
    assert turno.estado == "confirmado"
    assert turno.token_confirmacion_hash is None


@pytest.mark.asyncio
async def test_confirmar_reuso_410():
    """Task 2.3 RED: segundo GET del mismo token -> 410."""
    from freezegun import freeze_time

    _, cliente, _, _ = _app_con()
    with freeze_time("2026-10-05 12:00:00"):
        async with cliente as cli:
            token = (await cli.post("/reservas", json=_cuerpo())).json()["token"]
            assert (await cli.get(f"/confirmar/{token}")).status_code == 200
            reuso = await cli.get(f"/confirmar/{token}")
    assert reuso.status_code == 410, reuso.text


@pytest.mark.asyncio
async def test_confirmar_expirado_410_contacto():
    """Task 2.3 RED: token viejo -> 410 con contacto, sigue pendiente."""
    from freezegun import freeze_time

    _, cliente, turnos_repo, _ = _app_con()
    with freeze_time("2026-10-05 12:00:00"):
        async with cliente as cli:
            token = (await cli.post("/reservas", json=_cuerpo())).json()["token"]
            turno = await turnos_repo.get(1)
            turno.created_at = datetime.now(timezone.utc) - timedelta(hours=73)
            resp = await cli.get(f"/confirmar/{token}")
    assert resp.status_code == 410, resp.text
    assert resp.json()["contacto"]
    assert (await turnos_repo.get(1)).estado == "pendiente"


@pytest.mark.asyncio
async def test_confirmar_desconocido_404():
    """Task 2.3 RED: token jamas emitido -> 404 generico."""
    _, cliente, _, _ = _app_con()
    async with cliente as cli:
        resp = await cli.get("/confirmar/" + "x" * 43)
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_confirmar_alias_post_200_y_cancelado_410():
    """Triangulacion: alias POST confirma; cancelado -> 410 honesto."""
    from freezegun import freeze_time

    from app.servicios import agenda_servicio

    _, cliente, turnos_repo, _ = _app_con()
    with freeze_time("2026-10-05 12:00:00"):
        async with cliente as cli:
            token = (await cli.post("/reservas", json=_cuerpo())).json()["token"]
            via_post = await cli.post(f"/confirmar/{token}")
            assert via_post.status_code == 200, via_post.text
            assert via_post.json()["estado"] == "confirmado"
            token2 = (
                await cli.post(
                    "/reservas",
                    json=_cuerpo(inicio=LUNES_9 + timedelta(minutes=30)),
                )
            ).json()["token"]
            turno2 = await turnos_repo.get(2)
            await agenda_servicio.cambiar_estado(
                turnos_repo, turno2.id, "cancelado", motivo="cierre demo"
            )
            cancelado = await cli.get(f"/confirmar/{token2}")
        assert cancelado.status_code == 410, cancelado.text
        assert "cancelado" in cancelado.json()["detail"]
