"""Helper C-02: sesiones contra Postgres REAL (NUNCA SQLite).

Patron heredado de test_btree_gist.py (C-01): si no hay Postgres reachable se
hace skip con mensaje accionable (Docker no disponible en este entorno).
"""
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

BACKEND_DIR = Path(__file__).resolve().parents[1]  # backend/app/tests -> backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def dsn_test() -> str:
    """DSN del Postgres real de compose (override via DATABASE_URL_TEST)."""
    return os.getenv(
        "DATABASE_URL_TEST",
        "postgresql+asyncpg://turnos:turnos@localhost:5432/turnos",
    )

async def _engine_or_skip():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(dsn_test(), connect_args={"timeout": 3})
    reachable = await pg_reachable()
    if not reachable[0]:
        await engine.dispose()
        pytest.skip(f"Postgres no reachable (¿compose down / sin Docker?): {reachable[1]}")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"Postgres no reachable (¿compose down / sin Docker?): {exc}")
    return engine


async def pg_reachable() -> tuple[bool, str]:
    """Chequeo liviano via asyncpg (evita warnings de Alembic al skipear)."""
    try:
        import asyncpg
    except ImportError:
        return False, "asyncpg no instalado"
    # dsn asyncpg: postgresql://... (sin +asyncpg)
    dsn = dsn_test().replace("+asyncpg", "")
    try:
        conn = await asyncpg.connect(dsn, timeout=3)
    except Exception as exc:
        return False, str(exc)
    try:
        await conn.fetchval("SELECT 1")
    finally:
        await conn.close()
    return True, "ok"


@pytest_asyncio.fixture
async def sesion_pg():
    """AsyncSession sobre PG real con schema creado via metadata y drop al final."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.modelos import Base

    engine = await _engine_or_skip()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as sesion:
            yield sesion
            await sesion.rollback()
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
