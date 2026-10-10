"""C-02 tasks 1.1-1.3 + 5.2: Alembic + migracion 001 + convenciones.

Unit (siempre corre): ini/env/migracion presentes y bien configurados.
Integracion (requiere compose up): upgrade/downgrade + information_schema.
"""
import asyncio
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/app/tests -> backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "backend" / "alembic.ini"
ALEMBIC_DIR = REPO_ROOT / "backend" / "alembic"
VERSIONS_DIR = ALEMBIC_DIR / "versions"

TABLAS_ESPERADAS = ("rol", "usuario", "paciente", "profesional", "sillon")


async def _reset_estado_base(cfg, dsn: str) -> None:
    """Delega en db_utils.reset_estado_base (incluye `turno`, fix C-04)."""
    from db_utils import reset_estado_base

    await reset_estado_base(cfg, dsn)


def test_alembic_importable():
    """Task 1.1 RED: alembic instalable e importable."""
    from alembic import command
    from alembic.config import Config

    assert Config is not None
    assert command is not None


def test_alembic_ini_existe_y_apunta_a_backend_alembic():
    """Task 1.1 RED: alembic.ini versionado, sin URL hardcodeada."""
    assert ALEMBIC_INI.exists(), f"falta {ALEMBIC_INI}"
    contenido = ALEMBIC_INI.read_text(encoding="utf-8")
    assert "script_location" in contenido
    assert ALEMBIC_DIR.is_dir(), "script_location no resuelve a backend/alembic"
    assert (ALEMBIC_DIR / "env.py").is_file(), "falta backend/alembic/env.py"
    for secreto in ("turnos:turnos@", "CHANGEME", "localhost"):
        assert secreto not in contenido, f"alembic.ini no debe hardcodear {secreto!r}"


def test_alembic_env_async_con_target_metadata():
    """Task 1.2 RED: env.py async con target_metadata=Base.metadata desde DATABASE_URL."""
    env = ALEMBIC_DIR / "env.py"
    assert env.exists(), f"falta {env}"
    src = env.read_text(encoding="utf-8")
    assert "target_metadata" in src, "env.py debe exponer target_metadata"
    assert "Base" in src, "env.py debe importar Base de app.modelos"
    assert "async_engine_from_config" in src, "env.py debe ser async (D-01)"
    assert "DATABASE_URL" in src, "env.py debe leer DATABASE_URL del entorno"


def test_base_declarativa_importable():
    """Task 1.2 RED: Base declarativa en app.modelos."""
    from app.modelos import Base

    assert hasattr(Base, "metadata")
    assert hasattr(Base, "registry")


def test_migracion_001_existe_con_upgrade_y_downgrade():
    """Task 1.3 RED: migracion 001 crea las 5 tablas y sabe revertirlas."""
    assert VERSIONS_DIR.is_dir(), f"falta {VERSIONS_DIR}"
    migraciones = list(VERSIONS_DIR.glob("*001*.py"))
    assert len(migraciones) >= 1, "falta la migracion 001_core_identidad_pacientes"
    src = migraciones[0].read_text(encoding="utf-8")
    assert "def upgrade" in src and "def downgrade" in src
    for tabla in TABLAS_ESPERADAS:
        assert tabla in src, f"migracion 001 no menciona la tabla {tabla}"


@pytest.mark.asyncio
async def test_migracion_001_sube_y_baja_limpio(monkeypatch):
    """Task 1.3 GREEN: upgrade -> downgrade -> upgrade sin error (PG real)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from db_utils import dsn_test, pg_reachable

    from alembic import command
    from alembic.config import Config

    ok, motivo = await pg_reachable()
    if not ok:
        pytest.skip(f"Postgres no reachable (¿compose down / sin Docker?): {motivo}")
    monkeypatch.setenv("DATABASE_URL", dsn_test())
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", dsn_test())

    # Alembic env.py usa asyncio.run() (plantilla sync CLI): correrlo en un
    # worker thread sin loop corriendo para no chocar con pytest-asyncio.
    await _reset_estado_base(cfg, dsn_test())
    await asyncio.to_thread(command.upgrade, cfg, "head")
    await asyncio.to_thread(command.downgrade, cfg, "-1")
    await asyncio.to_thread(command.upgrade, cfg, "head")

    engine = create_async_engine(dsn_test())
    try:
        async with engine.connect() as conn:
            for tabla in TABLAS_ESPERADAS:
                existe = await conn.scalar(
                    text("SELECT to_regclass(:t)"), {"t": f"public.{tabla}"}
                )
                assert existe is not None, f"la tabla {tabla} no existe tras upgrade head"
    finally:
        await asyncio.to_thread(command.downgrade, cfg, "base")
        await engine.dispose()


@pytest.mark.asyncio
async def test_convenciones_tipos_en_catalogo(monkeypatch):
    """Task 5.2 GREEN: PK bigint+identity, tiempos timestamptz, sin serial/varchar/naive."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from db_utils import dsn_test, pg_reachable

    from alembic import command
    from alembic.config import Config

    ok, motivo = await pg_reachable()
    if not ok:
        pytest.skip(f"Postgres no reachable (¿compose down / sin Docker?): {motivo}")
    monkeypatch.setenv("DATABASE_URL", dsn_test())
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", dsn_test())
    # Idem test anterior: env.py sync con asyncio.run() -> worker thread.
    await _reset_estado_base(cfg, dsn_test())
    await asyncio.to_thread(command.upgrade, cfg, "head")

    engine = create_async_engine(dsn_test())
    try:
        async with engine.connect() as conn:
            n_varchar = await conn.scalar(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name IN "
                    "('rol','usuario','paciente','profesional','sillon') "
                    "AND data_type='character varying' "
                    "AND character_maximum_length IS NOT NULL"
                )
            )
            assert n_varchar == 0, "prohibido varchar(n): usar TEXT+CHECK (D-05)"
            n_naive = await conn.scalar(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name IN "
                    "('rol','usuario','paciente','profesional','sillon') "
                    "AND udt_name='timestamp'"
                )
            )
            assert n_naive == 0, "prohibido timestamp naive: usar TIMESTAMPTZ (D-05)"
            n_serial = await conn.scalar(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name IN "
                    "('rol','usuario','paciente','profesional','sillon') "
                    "AND column_default LIKE 'nextval%'"
                )
            )
            assert n_serial == 0, "prohibido serial: usar IDENTITY (D-05)"
            n_pk_no_bigint = await conn.scalar(
                text(
                    "SELECT count(*) FROM information_schema.table_constraints tc "
                    "JOIN information_schema.key_column_usage kcu "
                    "ON tc.constraint_name=kcu.constraint_name "
                    "JOIN information_schema.columns c "
                    "ON c.table_name=kcu.table_name AND c.column_name=kcu.column_name "
                    "WHERE tc.constraint_type='PRIMARY KEY' "
                    "AND tc.table_schema='public' AND tc.table_name IN "
                    "('rol','usuario','paciente','profesional','sillon') "
                    "AND c.data_type<>'bigint'"
                )
            )
            assert n_pk_no_bigint == 0, "toda PK debe ser bigint (D-05)"
            n_pk_sin_identity = await conn.scalar(
                text(
                    "SELECT count(*) FROM information_schema.table_constraints tc "
                    "JOIN information_schema.key_column_usage kcu "
                    "ON tc.constraint_name=kcu.constraint_name "
                    "JOIN information_schema.columns c "
                    "ON c.table_name=kcu.table_name AND c.column_name=kcu.column_name "
                    "WHERE tc.constraint_type='PRIMARY KEY' "
                    "AND tc.table_schema='public' AND tc.table_name IN "
                    "('rol','usuario','paciente','profesional','sillon') "
                    "AND c.is_identity<>'YES'"
                )
            )
            assert n_pk_sin_identity == 0, "toda PK debe ser GENERATED AS IDENTITY (D-05)"
    finally:
        await asyncio.to_thread(command.downgrade, cfg, "base")
        await engine.dispose()
