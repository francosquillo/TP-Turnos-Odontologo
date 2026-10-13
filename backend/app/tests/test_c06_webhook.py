"""C-06 tasks 5.1/5.2/5.3 RED: webhook firmado + eventos (D-05, RN-AU-04, RN-TU-03).

HTTP con fakes (siempre corre): sin firma 401, firma invalida 401 sin PHI en
log, challenge ok; SI confirma pendiente (+confirmacion); NO cancela
confirmado (motivo respuesta_paciente, hueco libre); doble SI idempotente;
terminales 200 sin mutar; estado_mensaje actualiza sin tocar turno.
Vocabulario cerrado (resolucion 2026-10-13 P3-A); NO cancela directo (P2-A).
NUNCA PHI en logs (ni telefonos completos).
"""
import hashlib
import hmac
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c03_fakes import FakeRepo, FakeStore, fabricar_usuario  # noqa: E402
from c04_fakes import FakeTurnoRepo, fabricar_turno  # noqa: E402
from c05_fakes import FakePacienteRepo, fabricar_paciente  # noqa: E402
from c06_fakes import CuentaCliente, FakeNotifRepo, FakeRedis  # noqa: E402

SECRETO = "webhook-secreto-demo-32-caracteres!"
FUTURO = datetime(2026, 11, 10, 11, 0, tzinfo=timezone.utc)


def _firma(cuerpo: bytes) -> dict[str, str]:
    digest = hmac.new(SECRETO.encode(), cuerpo, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={digest}"}


def _app_con(turnos, empresa_cliente=None):
    import os

    os.environ["WHATSAPP_WEBHOOK_SECRET"] = SECRETO
    os.environ["WHATSAPP_MOCK"] = "true"
    from app.api.notificaciones import get_notif_repo
    from app.api.turnos import get_paciente_repo, get_turno_repo
    from app.api.webhooks import get_cliente_whatsapp
    from app.core.deps import get_db, get_redis, get_usuario_repo
    from app.main import create_app

    app = create_app()
    turnos_repo = FakeTurnoRepo(turnos)
    notifs_repo = FakeNotifRepo()
    tienda = FakeRedis()
    app.dependency_overrides[get_usuario_repo] = lambda: FakeRepo(
        [fabricar_usuario(id=1, rol="secretaria")]
    )
    app.dependency_overrides[get_turno_repo] = lambda: turnos_repo
    app.dependency_overrides[get_paciente_repo] = lambda: FakePacienteRepo(
        [fabricar_paciente(id=1, nombre="Ana", telefono="1140001111",
                           email="ana@ficticio.test")]
    )
    app.dependency_overrides[get_notif_repo] = lambda: notifs_repo
    app.dependency_overrides[get_cliente_whatsapp] = (
        lambda: empresa_cliente or CuentaCliente()
    )

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


def _cuerpo_respuesta(turno_id: int, texto: str) -> bytes:
    return json.dumps(
        {"evento": "respuesta_paciente", "turno_id": turno_id, "texto": texto}
    ).encode()


@pytest.mark.asyncio
async def test_webhook_sin_firma_401():
    """Task 5.1 RED: POST sin firma -> 401 y nada muta."""
    _, cliente, turnos_repo, _ = _app_con(
        [fabricar_turno(id=1, estado="pendiente", inicio=FUTURO,
                        fin=FUTURO + timedelta(minutes=30))]
    )
    async with cliente as cli:
        resp = await cli.post(
            "/webhooks/whatsapp", content=_cuerpo_respuesta(1, "SI"))
    assert resp.status_code == 401
    assert (await turnos_repo.get(1)).estado == "pendiente"


@pytest.mark.asyncio
async def test_webhook_firma_invalida_401(caplog):
    """Task 5.1 RED: firma incorrecta -> 401 + log sin PHI."""
    import logging

    _, cliente, turnos_repo, _ = _app_con(
        [fabricar_turno(id=1, estado="pendiente", inicio=FUTURO,
                        fin=FUTURO + timedelta(minutes=30))]
    )
    cuerpo = _cuerpo_respuesta(1, "SI")
    async with cliente as cli:
        with caplog.at_level(logging.WARNING, logger="app.api.webhooks"):
            resp = await cli.post(
                "/webhooks/whatsapp", content=cuerpo,
                headers={"X-Hub-Signature-256": "sha256=00" * 32})
    assert resp.status_code == 401
    assert (await turnos_repo.get(1)).estado == "pendiente"
    for registro in caplog.records:
        assert "114000" not in registro.getMessage()
        assert "SI" not in registro.getMessage() or "motivo" in registro.getMessage()


@pytest.mark.asyncio
async def test_webhook_challenge_ok():
    """Task 5.1 RED: GET verifica challenge con token env."""
    _, cliente, _, _ = _app_con([])
    async with cliente as cli:
        resp = await cli.get(
            "/webhooks/whatsapp",
            params={"hub.mode": "subscribe",
                    "hub.verify_token": SECRETO,
                    "hub.challenge": "4321"},
        )
        assert resp.status_code == 200
        assert resp.text == "4321"
        malo = await cli.get(
            "/webhooks/whatsapp",
            params={"hub.mode": "subscribe",
                    "hub.verify_token": "otro",
                    "hub.challenge": "4321"},
        )
        assert malo.status_code == 403


@pytest.mark.asyncio
async def test_webhook_si_confirma_pendiente():
    """Task 5.2 RED: SI en pendiente -> confirmado + confirmacion encolada."""
    _, cliente, turnos_repo, notifs = _app_con(
        [fabricar_turno(id=1, estado="pendiente", inicio=FUTURO,
                        fin=FUTURO + timedelta(minutes=30))]
    )
    cuerpo = _cuerpo_respuesta(1, "SI")
    async with cliente as cli:
        resp = await cli.post(
            "/webhooks/whatsapp", content=cuerpo, headers=_firma(cuerpo))
    assert resp.status_code == 200, resp.text
    assert (await turnos_repo.get(1)).estado == "confirmado"
    assert await notifs.activa_de_turno(1, "confirmacion") is not None


@pytest.mark.asyncio
async def test_webhook_no_cancela_confirmado():
    """Task 5.2 RED: NO en confirmado -> cancelado motivo respuesta_paciente."""
    from app.repos.turno_repo import TurnoRepository  # noqa: F401
    from app.servicios import agenda_servicio as agenda

    _, cliente, turnos_repo, _ = _app_con(
        [fabricar_turno(id=1, estado="confirmado", inicio=FUTURO,
                        fin=FUTURO + timedelta(minutes=30))]
    )
    cuerpo = _cuerpo_respuesta(1, "NO")
    async with cliente as cli:
        resp = await cli.post(
            "/webhooks/whatsapp", content=cuerpo, headers=_firma(cuerpo))
    assert resp.status_code == 200, resp.text
    turno = await turnos_repo.get(1)
    assert turno.estado == "cancelado"
    assert turno.motivo_cancelacion == "respuesta_paciente"
    # Hueco liberado: sin solapamiento activo para C-07.
    assert not await turnos_repo.hay_solapamiento(1, 1, FUTURO,
                                                 FUTURO + timedelta(minutes=30))


@pytest.mark.asyncio
async def test_webhook_respuesta_idempotente():
    """Task 5.2 RED: doble SI -> un solo cambio, segundo 200 sin mutar."""
    _, cliente, turnos_repo, notifs = _app_con(
        [fabricar_turno(id=1, estado="pendiente", inicio=FUTURO,
                        fin=FUTURO + timedelta(minutes=30))]
    )
    cuerpo = _cuerpo_respuesta(1, "SI")
    async with cliente as cli:
        uno = await cli.post(
            "/webhooks/whatsapp", content=cuerpo, headers=_firma(cuerpo))
        dos = await cli.post(
            "/webhooks/whatsapp", content=cuerpo, headers=_firma(cuerpo))
    assert uno.status_code == 200 and dos.status_code == 200
    assert (await turnos_repo.get(1)).estado == "confirmado"
    confirmaciones = [
        f for f in notifs._filas.values() if f.plantilla == "confirmacion"
    ]
    assert len(confirmaciones) == 1


@pytest.mark.asyncio
async def test_webhook_terminal_sin_mutar():
    """Triangulacion: SI en asistido -> 200 sin mutar ni encolar."""
    _, cliente, turnos_repo, notifs = _app_con(
        [fabricar_turno(id=1, estado="asistido", inicio=FUTURO,
                        fin=FUTURO + timedelta(minutes=30))]
    )
    cuerpo = _cuerpo_respuesta(1, "SI")
    async with cliente as cli:
        resp = await cli.post(
            "/webhooks/whatsapp", content=cuerpo, headers=_firma(cuerpo))
    assert resp.status_code == 200
    assert (await turnos_repo.get(1)).estado == "asistido"
    assert await notifs.activa_de_turno(1, "confirmacion") is None


@pytest.mark.asyncio
async def test_webhook_no_reconocida_sin_mutar():
    """Resolucion P3-A: texto fuera del vocabulario -> 200 sin mutar."""
    _, cliente, turnos_repo, _ = _app_con(
        [fabricar_turno(id=1, estado="pendiente", inicio=FUTURO,
                        fin=FUTURO + timedelta(minutes=30))]
    )
    cuerpo = _cuerpo_respuesta(1, "quizás mañana les aviso")
    async with cliente as cli:
        resp = await cli.post(
            "/webhooks/whatsapp", content=cuerpo, headers=_firma(cuerpo))
    assert resp.status_code == 200
    assert (await turnos_repo.get(1)).estado == "pendiente"


@pytest.mark.asyncio
async def test_webhook_estado_actualiza_sin_tocar_turno():
    """Task 5.3 RED: delivered con message_id -> entregada, turno intacto."""
    from app.servicios import notificacion_servicio as svc

    app, cliente, turnos_repo, notifs = _app_con(
        [fabricar_turno(id=1, estado="confirmado", inicio=FUTURO,
                        fin=FUTURO + timedelta(minutes=30))]
    )
    fila = await notifs.crear(
        turno_id=1, canal="whatsapp", plantilla="recordatorio_48h",
        estado="enviada", payload={"message_id": "wamid-demo-9"},
    )
    assert fila.estado == "enviada"
    cuerpo = json.dumps(
        {"evento": "estado_mensaje", "message_id": "wamid-demo-9",
         "estado": "delivered"}
    ).encode()
    async with cliente as cli:
        resp = await cli.post(
            "/webhooks/whatsapp", content=cuerpo, headers=_firma(cuerpo))
    assert resp.status_code == 200, resp.text
    assert fila.estado == "entregada"
    assert (await turnos_repo.get(1)).estado == "confirmado"
