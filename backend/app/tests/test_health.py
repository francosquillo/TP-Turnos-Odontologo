"""Task 2.3 RED: GET /health 200 / 503 sin secretos, via httpx.AsyncClient.

RED inicial: ModuleNotFoundError app.main.
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.mark.asyncio
async def test_health_ok():
    import os

    os.environ.setdefault("JWT_SECRET", "t" * 32)
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/t")
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code in (200, 503)  # 503 si no hay postgres/redis reales
    body = resp.json()
    assert "status" in body
    assert "DATABASE_URL" not in str(body) and "JWT_SECRET" not in str(body)


@pytest.mark.asyncio
async def test_health_503_servicio_caido():
    import os

    from httpx import ASGITransport, AsyncClient

    os.environ.setdefault("JWT_SECRET", "t" * 32)
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/t")
    from app import main as main_mod
    from app.main import app

    async def pg_caido() -> str:
        return "down"

    async def redis_caido() -> str:
        return "down"

    app.dependency_overrides[main_mod.check_postgres] = pg_caido
    app.dependency_overrides[main_mod.check_redis] = redis_caido
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "degraded"
        assert "Traceback" not in str(body) and "JWT_SECRET" not in str(body)
    finally:
        app.dependency_overrides.clear()


# --- C-12 11.3: check_postgres con URL de SQLAlchemy -------------------------
def test_url_asyncpg_normaliza_el_esquema_sqlalchemy():
    from app.main import _url_para_asyncpg

    assert (
        _url_para_asyncpg("postgresql+asyncpg://u:p@localhost:5433/turnos")
        == "postgresql://u:p@localhost:5433/turnos"
    )
    # Una URL ya plana, o con otro driver, tambien queda lista para asyncpg.
    assert _url_para_asyncpg("postgresql://u:p@h/db") == "postgresql://u:p@h/db"
    assert _url_para_asyncpg("postgres+asyncpg://u:p@h/db") == "postgresql://u:p@h/db"


@pytest.mark.asyncio
async def test_check_postgres_conecta_con_url_asyncpg_de_sqlalchemy(monkeypatch):
    """asyncpg.connect recibe un DSN sin '+asyncpg' (con el esquema SQLAlchemy daba 'down')."""
    import asyncpg

    from app import main as main_mod

    recibido: dict[str, str] = {}

    class _Conn:
        async def fetchval(self, _sql: str) -> int:
            return 1

        async def close(self) -> None:
            return None

    async def conectar(dsn: str, **_kw: object) -> _Conn:
        recibido["dsn"] = dsn
        if "+" in dsn.split("://")[0]:
            raise ValueError("invalid DSN: scheme is expected to be postgresql")
        return _Conn()

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5433/turnos")
    monkeypatch.setenv("JWT_SECRET", "t" * 32)
    monkeypatch.setattr(asyncpg, "connect", conectar)
    assert await main_mod.check_postgres() == "up"
    assert recibido["dsn"] == "postgresql://u:p@localhost:5433/turnos"
