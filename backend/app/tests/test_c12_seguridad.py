"""C-12 1.1: GET /seguridad publico, con hechos derivados de la configuracion real (D-05).

Sin Postgres ni Redis: el endpoint no hace I/O.
"""
import json
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import create_app  # noqa: E402


async def _get_seguridad() -> tuple[int, dict, str]:
    transporte = ASGITransport(app=create_app())
    async with AsyncClient(transport=transporte, base_url="http://test") as cli:
        r = await cli.get("/seguridad")
    return r.status_code, r.json(), r.text


@pytest.mark.asyncio
async def test_seguridad_sin_token_responde_200_con_datos_ficticios():
    status, cuerpo, _ = await _get_seguridad()
    assert status == 200
    assert cuerpo["datos_ficticios"] is True
    assert cuerpo["hash_contrasenas"] == "argon2"
    assert cuerpo["refresh_rotativo"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("minutos", [15, 45])
async def test_seguridad_vida_del_token_sigue_a_la_configuracion(monkeypatch, minutos):
    monkeypatch.setenv("JWT_EXPIRE_MIN", str(minutos))
    _, cuerpo, _ = await _get_seguridad()
    assert cuerpo["access_token_min"] == minutos


@pytest.mark.asyncio
@pytest.mark.parametrize("mock", ["true", "false"])
async def test_seguridad_whatsapp_modo_sigue_a_la_configuracion(monkeypatch, mock):
    monkeypatch.setenv("WHATSAPP_MOCK", mock)
    _, cuerpo, _ = await _get_seguridad()
    assert cuerpo["whatsapp_modo"] == ("mock" if mock == "true" else "real")
    assert cuerpo["whatsapp_sin_datos_clinicos"] is True


@pytest.mark.asyncio
async def test_seguridad_no_incluye_secretos(monkeypatch):
    secretos = {
        "JWT_SECRET": "valor-jwt-secreto-0123456789abcdef",
        "WHATSAPP_TOKEN": "valor-whatsapp-token-xyz987",
        "GCAL_SECRET": "valor-gcal-secreto-qrs654",
        "GCAL_CLIENT_ID": "valor-gcal-client-id-abc321",
    }
    for nombre, valor in secretos.items():
        monkeypatch.setenv(nombre, valor)
    _, _, texto = await _get_seguridad()
    for valor in secretos.values():
        assert valor not in texto


@pytest.mark.asyncio
async def test_seguridad_no_afirma_cifrado_ni_tls_y_lo_declara_pendiente():
    _, cuerpo, texto = await _get_seguridad()
    assert "pendiente" in cuerpo["cifrado"].lower()
    assert "RN-GL-03" in cuerpo["cifrado"]
    # Ningun campo booleano declara cifrado/TLS activos.
    claves_booleanas = {k for k, v in cuerpo.items() if isinstance(v, bool)}
    assert not {k for k in claves_booleanas if "tls" in k or "cifrado" in k}
    assert "tls activo" not in texto.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("client_id", "secret", "esperado"),
    [
        ("", "", False),
        ("id-real", "", False),
        ("CHANGEME-placeholder", "CHANGEME-placeholder", False),
        ("id-real", "secreto-real", True),
    ],
)
async def test_seguridad_google_calendar_habilitado_solo_con_credenciales_reales(
    monkeypatch, client_id, secret, esperado
):
    monkeypatch.setenv("GCAL_CLIENT_ID", client_id)
    monkeypatch.setenv("GCAL_SECRET", secret)
    _, cuerpo, _ = await _get_seguridad()
    assert cuerpo["google_calendar_habilitado"] is esperado


@pytest.mark.asyncio
async def test_seguridad_auditoria_y_respaldos_son_listas_de_hechos_no_vacias():
    _, cuerpo, _ = await _get_seguridad()
    assert any("aranceles" in a for a in cuerpo["auditoria"])
    assert any("sobreturno" in a.lower() for a in cuerpo["auditoria"])
    assert cuerpo["respaldos"]
    json.dumps(cuerpo)  # serializable y sin objetos raros


def test_seguridad_esquema_es_estricto_y_router_tiene_prefix_y_tags():
    from app.api import seguridad
    from app.esquemas.seguridad import SeguridadOut

    assert SeguridadOut.model_config.get("extra") == "forbid"
    assert seguridad.router.tags


@pytest.mark.asyncio
async def test_seguridad_respaldos_menciona_la_exportacion_total_porque_existe():
    from importlib.util import find_spec

    assert find_spec("app.servicios.exportacion_servicio") is not None
    _, cuerpo, _ = await _get_seguridad()
    assert any("exportación total" in r for r in cuerpo["respaldos"])
    assert any("volumen Docker" in r for r in cuerpo["respaldos"])
