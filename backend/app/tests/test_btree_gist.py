"""Task 1.2 RED: init SQL btree_gist presente + test integracion contra Postgres real.

Unit (siempre corre): archivo existe y contiene CREATE EXTENSION IF NOT EXISTS btree_gist.
Integracion (requiere compose up): pg_extension tiene la fila; si no hay DB, se skipea
con mensaje accionable (Docker no disponible en este entorno).
"""
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
INIT_SQL = REPO_ROOT / "backend" / "db" / "init" / "01-btree-gist.sql"


def test_btree_gist_extension_present():
    assert INIT_SQL.exists(), f"falta {INIT_SQL}"
    sql = INIT_SQL.read_text(encoding="utf-8")
    assert "btree_gist" in sql
    assert "CREATE EXTENSION IF NOT EXISTS" in sql


def test_btree_gist_init_montado_en_compose():
    import yaml

    compose = REPO_ROOT / "docker-compose.yml"
    assert compose.exists(), "falta docker-compose.yml (task 1.1)"
    data = yaml.safe_load(compose.read_text(encoding="utf-8"))
    volumes = str(data["services"]["db"].get("volumes", []))
    assert "docker-entrypoint-initdb.d" in volumes


@pytest.mark.asyncio
async def test_btree_gist_extension_en_postgres_real():
    """Integracion: requiere Postgres real del compose (NUNCA SQLite)."""
    try:
        import asyncpg  # type: ignore
    except ImportError:
        pytest.skip("asyncpg no instalado")
    dsn = os.getenv("DATABASE_URL_TEST", "postgresql://turnos:turnos@localhost:5432/turnos")
    # asyncpg no entiende el dialecto SQLAlchemy (+asyncpg): mismo strippeo
    # que db_utils.pg_reachable (fix verify C-04: sin esto el test skipeaba
    # aun con PG arriba por "invalid DSN").
    dsn = dsn.replace("+asyncpg", "")
    try:
        conn = await asyncpg.connect(dsn, timeout=3)
    except Exception as exc:
        pytest.skip(f"Postgres no reachable (¿compose down / sin Docker?): {exc}")
    try:
        row = await conn.fetchrow("SELECT * FROM pg_extension WHERE extname = 'btree_gist'")
        assert row is not None, "btree_gist no habilitada en Postgres real"
    finally:
        await conn.close()
