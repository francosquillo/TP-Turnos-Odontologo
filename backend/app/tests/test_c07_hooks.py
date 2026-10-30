"""C-07 grupo 4.2: ganchos aditivos de cancelación (D-02) con fakes HTTP.

Cancelar por staff (PATCH /turnos/:id/estado) y NO por webhook disparan la
oferta DESPUÉS del commit del cancelado; `ausente` y demás transiciones no.
Un fallo de la oferta jamás revierte el cancelado. Datos 100% ficticios.
"""
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c03_fakes import fabricar_usuario  # noqa: E402
from c04_fakes import fabricar_turno  # noqa: E402
from c05_fakes import fabricar_paciente  # noqa: E402
from c07_fakes import armar_app, fabricar_entry  # noqa: E402

INI = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)  # lunes 09:00 BA
FIN = INI + timedelta(minutes=30)
SECRETO = "webhook-secreto-demo-32-caracteres!"
STAFF = [fabricar_usuario(id=1, rol="secretaria")]
PACIENTES = [fabricar_paciente(id=1, nombre="Ana", telefono="1140001111"),
             fabricar_paciente(id=2, nombre="Beto", telefono="1140002222")]


def _turno(estado="confirmado"):
    return fabricar_turno(id=5, paciente_id=2, estado=estado, inicio=INI, fin=FIN)


def _firma(cuerpo: bytes) -> dict[str, str]:
    digest = hmac.new(SECRETO.encode(), cuerpo, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={digest}"}


def _evento(texto: str) -> bytes:
    return json.dumps({"evento": "respuesta_paciente", "turno_id": 5, "texto": texto}).encode()


async def _cancelar(cli, bearer):
    return await cli.patch(
        "/turnos/5/estado", json={"estado": "cancelado", "motivo": "paciente avisó"},
        headers=bearer(1, "secretaria"),
    )


# --- cancelar por staff ----------------------------------------------------------

@pytest.mark.asyncio
async def test_cancelar_por_staff_dispara_oferta():
    """Task 4.2 RED: cancelar con una activa compatible -> turno cancelado + entry ofrecida (2 h desde AHORA) + aviso."""
    _, cli, bearer, mundo = armar_app(
        usuarios=STAFF, pacientes=PACIENTES, turnos=[_turno()],
        entradas=[fabricar_entry(1, paciente_id=1), fabricar_entry(2, paciente_id=2)],
    )
    antes = datetime.now(timezone.utc)
    async with cli:
        resp = await _cancelar(cli, bearer)
    despues = datetime.now(timezone.utc)

    assert resp.status_code == 200 and resp.json()["estado"] == "cancelado"
    e1, e2 = await mundo.espera.get(1), await mundo.espera.get(2)
    assert e1.estado == "ofrecida" and e2.estado == "activa"  # FIFO: solo la primera
    # La ventana de 2 h corre desde el momento de la oferta, NO desde el inicio del turno.
    assert antes + timedelta(hours=2) <= e1.oferta_expira_en <= despues + timedelta(hours=2)
    assert e1.oferta_hueco["inicio"] == INI.isoformat() and e1.oferta_hueco["turno_id"] == 5
    assert mundo.sesion.commits == 2  # cancelado + oferta, cada uno persistido
    fila = await mundo.notifs.activa_de_turno(5, "oferta_lista_espera")
    assert fila is not None and fila.destinatario_ref == "1140001111"


@pytest.mark.asyncio
async def test_cancelar_sin_compatible_es_noop():
    """Task 4.2: sin entradas compatibles el cancelado queda y no pasa nada más."""
    _, cli, bearer, mundo = armar_app(
        usuarios=STAFF, pacientes=PACIENTES, turnos=[_turno()],
        entradas=[fabricar_entry(1, profesional_id=99)],  # otro profesional
    )
    async with cli:
        resp = await _cancelar(cli, bearer)

    assert resp.status_code == 200
    assert (await mundo.espera.get(1)).estado == "activa"
    assert mundo.notifs.cantidad_activas() == 0


@pytest.mark.asyncio
async def test_cancelar_si_la_oferta_falla_no_se_revierte():
    """Task 4.2: el cancelado ya commiteado sobrevive a un fallo del servicio de espera."""
    _, cli, bearer, mundo = armar_app(
        usuarios=STAFF, pacientes=PACIENTES, turnos=[_turno()], entradas=[fabricar_entry(1)],
    )
    mundo.espera.falla = True
    async with cli:
        resp = await _cancelar(cli, bearer)

    assert resp.status_code == 200 and resp.json()["estado"] == "cancelado"
    assert (await mundo.turnos.get(5)).estado == "cancelado"
    assert mundo.sesion.commits == 1 and mundo.sesion.rollbacks == 1  # solo se descarta la oferta


@pytest.mark.asyncio
@pytest.mark.parametrize("estado_origen, nuevo", [
    ("confirmado", "ausente"),     # D-02: el ausente NO entra al Flujo 6
    ("confirmado", "asistido"),
    ("pendiente", "confirmado"),
])
async def test_ausente_no_dispara_oferta(estado_origen, nuevo):
    """Task 4.2 RED: solo `cancelado` dispara; ausente/asistido/confirmado no."""
    _, cli, bearer, mundo = armar_app(
        usuarios=STAFF, pacientes=PACIENTES, turnos=[_turno(estado_origen)],
        entradas=[fabricar_entry(1)],
    )
    async with cli:
        resp = await cli.patch("/turnos/5/estado", json={"estado": nuevo}, headers=bearer(1, "secretaria"))

    assert resp.status_code == 200, resp.text
    assert (await mundo.espera.get(1)).estado == "activa"
    assert mundo.notifs.cantidad_activas() == 0
    assert mundo.sesion.commits == 1  # solo el cambio de estado


# --- NO por webhook --------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_no_dispara_oferta():
    """Task 4.2 RED: NO por WhatsApp cancela y ofrece el hueco al primero compatible."""
    os.environ["WHATSAPP_WEBHOOK_SECRET"] = SECRETO
    os.environ["WHATSAPP_MOCK"] = "true"
    from app.api.webhooks import get_cliente_whatsapp

    app, cli, _, mundo = armar_app(
        usuarios=STAFF, pacientes=PACIENTES, turnos=[_turno()],
        entradas=[fabricar_entry(1, paciente_id=1)],
    )
    app.dependency_overrides[get_cliente_whatsapp] = lambda: mundo.cliente
    cuerpo = _evento("NO")
    async with cli:
        resp = await cli.post("/webhooks/whatsapp", content=cuerpo, headers=_firma(cuerpo))

    assert resp.status_code == 200, resp.text
    turno = await mundo.turnos.get(5)
    assert (turno.estado, turno.motivo_cancelacion) == ("cancelado", "respuesta_paciente")
    e1 = await mundo.espera.get(1)
    assert e1.estado == "ofrecida"
    assert e1.oferta_hueco["turno_id"] == 5
    assert mundo.sesion.commits == 2


@pytest.mark.asyncio
async def test_webhook_si_no_dispara_oferta():
    """Triangulación: SI confirma, nunca ofrece."""
    os.environ["WHATSAPP_WEBHOOK_SECRET"] = SECRETO
    os.environ["WHATSAPP_MOCK"] = "true"
    from app.api.webhooks import get_cliente_whatsapp

    app, cli, _, mundo = armar_app(
        usuarios=STAFF, pacientes=PACIENTES, turnos=[_turno("pendiente")], entradas=[fabricar_entry(1)],
    )
    app.dependency_overrides[get_cliente_whatsapp] = lambda: mundo.cliente
    cuerpo = _evento("SI")
    async with cli:
        resp = await cli.post("/webhooks/whatsapp", content=cuerpo, headers=_firma(cuerpo))

    assert resp.status_code == 200
    assert (await mundo.turnos.get(5)).estado == "confirmado"
    assert (await mundo.espera.get(1)).estado == "activa"


@pytest.mark.asyncio
async def test_webhook_no_con_fallo_de_oferta_mantiene_cancelado():
    """Task 4.2: el NO ya cancelado no se revierte si la oferta rompe."""
    os.environ["WHATSAPP_WEBHOOK_SECRET"] = SECRETO
    os.environ["WHATSAPP_MOCK"] = "true"
    from app.api.webhooks import get_cliente_whatsapp

    app, cli, _, mundo = armar_app(
        usuarios=STAFF, pacientes=PACIENTES, turnos=[_turno()], entradas=[fabricar_entry(1)],
    )
    app.dependency_overrides[get_cliente_whatsapp] = lambda: mundo.cliente
    mundo.espera.falla = True
    cuerpo = _evento("NO")
    async with cli:
        resp = await cli.post("/webhooks/whatsapp", content=cuerpo, headers=_firma(cuerpo))

    assert resp.status_code == 200
    assert (await mundo.turnos.get(5)).estado == "cancelado"
