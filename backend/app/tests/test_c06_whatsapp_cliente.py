"""C-06 tasks 2.1/2.2 RED: cliente WhatsApp mock/real + fallback stub (D-07, RN-NO-03).

Unit (siempre corre): mock sin HTTP costo 0; real sin creds fail-fast en
arranque; real con HTTP moqueado costo 0.026; fallback email tras 3 fallos
(misma fila, canal mutado, via_fallback, costo 0); fallback sms stub sin
email; sin numero ni email -> fallida. NUNCA contra la API real de Meta.
Datos ficticios; logs sin PHI (ultimos 4 digitos).
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_mock_no_hace_http_y_costo_cero():
    """Task 2.1 RED: WHATSAPP_MOCK=true simula sin HTTP, costo 0."""
    import asyncio

    from app.servicios.whatsapp_cliente import MockWhatsAppCliente

    cliente = MockWhatsAppCliente()
    resultado = asyncio.run(cliente.enviar(
        "1140001111", "recordatorio_48h", {"nombre_pila": "Ana"}
    ))
    assert resultado.estado == "enviada"
    assert resultado.message_id.startswith("mock-")
    assert resultado.costo == 0
    assert len(cliente.envios) == 1  # registrado, sin HTTP


def test_real_sin_creds_falla_en_arranque():
    """Task 2.1 RED: WHATSAPP_MOCK=false sin TOKEN/PHONE_ID -> fail-fast."""
    from app.servicios.whatsapp_cliente import (
        ConfiguracionWhatsAppError,
        MetaCliente,
        crear_cliente,
    )

    with pytest.raises(ConfiguracionWhatsAppError):
        MetaCliente(token="", phone_id="")
    with pytest.raises(ConfiguracionWhatsAppError):
        MetaCliente(token="tok", phone_id="")
    with pytest.raises(ConfiguracionWhatsAppError):
        crear_cliente(mock=False, token="", phone_id="x")
    assert isinstance(crear_cliente(mock=True), object)


@pytest.mark.asyncio
async def test_real_envia_con_costo_0026(monkeypatch):
    """Task 2.1/3.3 RED: real con HTTP moqueado -> enviada, costo 0.026."""
    import httpx

    from app.servicios.whatsapp_cliente import COSTO_META_USD_REF, MetaCliente

    assert COSTO_META_USD_REF == 0.026
    vistos: dict = {}

    class _Resp:
        def json(self):
            return {"messages": [{"id": "wamid-demo-1"}]}

        def raise_for_status(self):
            return None

    async def _post(self, url, **kwargs):
        vistos["url"] = url
        vistos["json"] = kwargs.get("json")
        return _Resp()

    monkeypatch.setattr(httpx.AsyncClient, "post", _post)
    cliente = MetaCliente(token="tok-demo", phone_id="pid-demo")
    resultado = await cliente.enviar(
        "1140001111", "recordatorio_48h", {"nombre_pila": "Ana"}
    )
    assert resultado.estado == "enviada"
    assert resultado.message_id == "wamid-demo-1"
    assert resultado.costo == 0.026
    assert "pid-demo" in vistos["url"]
    assert vistos["json"]["to"] == "1140001111"


@pytest.mark.asyncio
async def test_fallback_email_tras_3_fallos_whatsapp():
    """Task 2.2 RED: 3 fallos + email -> misma fila canal=email enviada."""
    from c06_fakes import FakeNotifRepo, FallaCliente
    from app.servicios import notificacion_servicio as svc

    repo = FakeNotifRepo()
    fila = await repo.crear(
        turno_id=1, canal="whatsapp", plantilla="recordatorio_48h",
        destinatario_ref="1140001111", payload={"nombre_pila": "Ana"},
    )
    resultado = await svc.enviar_con_reintentos(
        repo, fila, FallaCliente(), email="ana@ficticio.test",
    )
    assert resultado.estado == "enviada"
    assert fila.canal == "email"
    assert fila.payload.get("via_fallback") is True
    assert fila.costo == 0
    assert fila.intentos == 3


@pytest.mark.asyncio
async def test_fallback_sms_stub_sin_email():
    """Task 2.2 RED: 3 fallos sin email -> sms stub en la misma fila."""
    from c06_fakes import FakeNotifRepo, FallaCliente
    from app.servicios import notificacion_servicio as svc

    repo = FakeNotifRepo()
    fila = await repo.crear(
        turno_id=2, canal="whatsapp", plantilla="recordatorio_48h",
        destinatario_ref="1140002222", payload={"nombre_pila": "Bruno"},
    )
    resultado = await svc.enviar_con_reintentos(repo, fila, FallaCliente())
    assert resultado.estado == "enviada"
    assert fila.canal == "sms"
    assert fila.payload.get("via_fallback") is True
    assert fila.costo == 0


@pytest.mark.asyncio
async def test_sin_numero_ni_email_marca_fallida():
    """Triangulacion: sin telefono ni email no hay canal posible -> fallida."""
    from c06_fakes import FakeNotifRepo, FallaCliente
    from app.servicios import notificacion_servicio as svc

    repo = FakeNotifRepo()
    fila = await repo.crear(
        turno_id=3, canal="whatsapp", plantilla="recordatorio_48h",
        destinatario_ref=None, payload={"nombre_pila": "Sin Tel"},
    )
    resultado = await svc.enviar_con_reintentos(repo, fila, FallaCliente())
    assert resultado.estado == "fallida"
    assert fila.estado == "fallida"
    assert fila.intentos == 3
    assert "fallida" in (fila.ultimo_error or "fallida")
