"""Task 3.3 RED: CORS por env + extra='forbid' (422 ante campo extra)."""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_esquema_base_rechaza_campos_extra():
    from pydantic import ValidationError

    from app.esquemas.base import BaseSchema

    class Demo(BaseSchema):
        nombre: str

    with pytest.raises(ValidationError):
        Demo(nombre="x", intruso="y")


@pytest.mark.asyncio
async def test_payload_extra_retorna_422():
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.esquemas.base import BaseSchema

    class DemoIn(BaseSchema):
        nombre: str

    mini = FastAPI()

    @mini.post("/demo")
    def crear(demo: DemoIn) -> dict[str, str]:
        return {"nombre": demo.nombre}

    transport = ASGITransport(app=mini)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/demo", json={"nombre": "x", "intruso": "y"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cors_origen_no_permitido_rechazado(monkeypatch):
    import os

    from httpx import ASGITransport, AsyncClient

    os.environ.setdefault("JWT_SECRET", "t" * 32)
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/t")
    monkeypatch.setenv("CORS_ORIGINS", '["http://permitido.test"]')
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        preflight = await client.options(
            "/health",
            headers={
                "Origin": "http://malicioso.test",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert preflight.status_code == 400
        ok = await client.get("/health", headers={"Origin": "http://permitido.test"})
        assert ok.headers.get("access-control-allow-origin") == "http://permitido.test"
