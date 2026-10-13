"""C-06 tasks 6.1/6.2 RED: reserva online alimenta notificaciones.

- El turno online entra al barrido sin codigo extra (servicio, ya probado en
  test_c06_barrido.py::test_reserva_online_entra_al_barrido).
- `GET /confirmar/:token` exitoso encola `confirmacion` como efecto lateral
  aditivo SIN cambiar su contrato (200/404/410 intactos, best-effort: el hook
  nunca rompe la confirmacion).
- 6.2: `hueco_liberado` acepta `{expira_en}` (probado en
  test_c06_plantillas.py::test_render_hueco_extensible_a_oferta).
Datos ficticios.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c03_fakes import FakeStore  # noqa: E402
from c04_fakes import FakeEntidadRepo, FakeProfesionalRepo  # noqa: E402
from c05_fakes import FakePacienteRepo, FakeTurnoRepoC05  # noqa: E402
from c06_fakes import CuentaCliente, FakeNotifRepo  # noqa: E402

# Lunes futuro (la agenda demo cubre lunes 08-12 BA; hoy real ~10/2026).
LUNES_FUTURO = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


def _app_con(con_notif_override: bool):
    from app.api.notificaciones import get_notif_repo
    from app.api.reservas import get_notif_repo_reserva
    from app.api.turnos import (
        get_paciente_repo,
        get_profesional_repo,
        get_sillon_repo,
        get_turno_repo,
    )
    from app.api.webhooks import get_cliente_whatsapp
    from app.core.deps import get_db, get_redis
    from app.main import create_app

    app = create_app()
    turnos_repo = FakeTurnoRepoC05()
    notifs_repo = FakeNotifRepo()
    tienda = FakeStore()
    app.dependency_overrides[get_turno_repo] = lambda: turnos_repo
    app.dependency_overrides[get_paciente_repo] = lambda: FakePacienteRepo()
    app.dependency_overrides[get_profesional_repo] = lambda: FakeProfesionalRepo(
        [SimpleNamespace(id=1)]
    )
    app.dependency_overrides[get_sillon_repo] = lambda: FakeEntidadRepo(
        [SimpleNamespace(id=1)]
    )
    if con_notif_override:
        app.dependency_overrides[get_notif_repo_reserva] = lambda: notifs_repo
        app.dependency_overrides[get_notif_repo] = lambda: notifs_repo
    app.dependency_overrides[get_cliente_whatsapp] = lambda: CuentaCliente()

    class _S:
        async def commit(self):
            return None

        async def rollback(self):
            return None

    async def _db():
        yield _S()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_redis] = lambda: tienda
    cliente = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return app, cliente, turnos_repo, notifs_repo


def _cuerpo() -> dict:
    return {
        "profesional_id": 1,
        "sillon_id": 1,
        "inicio": LUNES_FUTURO.isoformat(),
        "fin": (LUNES_FUTURO + timedelta(minutes=30)).isoformat(),
        "nombre": "Ana Ficticia",
        "telefono": "11 5000-2222",
    }


@pytest.mark.asyncio
async def test_confirmar_token_encola_confirmacion_sin_cambiar_contrato():
    """Task 6.1 RED: confirmar 200 + fila confirmacion; 404/410 intactos."""
    _, cliente, _, notifs = _app_con(con_notif_override=True)
    async with cliente as cli:
        creado = await cli.post("/reservas", json=_cuerpo())
        assert creado.status_code == 201, creado.text
        token = creado.json()["token"]
        ok = await cli.get(f"/confirmar/{token}")
        assert ok.status_code == 200, ok.text
        assert ok.json()["estado"] == "confirmado"
        assert (await cli.get("/confirmar/invalido-demo")).status_code == 404
        assert (await cli.get(f"/confirmar/{token}")).status_code == 410
    confirmaciones = [
        f for f in notifs._filas.values() if f.plantilla == "confirmacion"
    ]
    assert len(confirmaciones) == 1
    assert confirmaciones[0].estado in ("encolada", "enviada")


@pytest.mark.asyncio
async def test_confirmar_sin_notif_repo_no_rompe_contrato():
    """Triangulacion: hook best-effort (sin override notif sigue 200)."""
    _, cliente, _, _ = _app_con(con_notif_override=False)
    async with cliente as cli:
        creado = await cli.post("/reservas", json=_cuerpo())
        assert creado.status_code == 201, creado.text
        ok = await cli.get(f"/confirmar/{creado.json()['token']}")
        assert ok.status_code == 200, ok.text
