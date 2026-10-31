"""C-08 grupo 1: migración 005_clinica encadenada a 004_espera (D-01, D-04).

Las pruebas estáticas corren siempre; las de upgrade/downgrade usan Alembic
real sobre Postgres real (skip sin Docker). Datos 100% ficticios.
"""
import asyncio
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "backend" / "alembic.ini"
ALEMBIC_DIR = REPO_ROOT / "backend" / "alembic"
TABLAS = ("estado_hallazgo_catalogo", "historia_clinica", "hallazgo_odontograma", "tratamiento")


def test_c08_cabeza_unica_005_sobre_004():
    from alembic.script import ScriptDirectory

    script = ScriptDirectory(str(ALEMBIC_DIR))
    # La cabeza avanzó con C-09 (006); 005 sigue colgando de 004 y 006 de 005.
    assert script.get_heads() == ["006_presupuestos_cc"]
    assert script.get_revision("005_clinica").down_revision == "004_espera"
    assert script.get_revision("006_presupuestos_cc").down_revision == "005_clinica"


def test_c08_migracion_declara_checks_e_indices_del_modelo():
    from app.modelos import (
        EstadoHallazgoCatalogo, HallazgoOdontograma, HistoriaClinica, Tratamiento,
    )

    texto = (ALEMBIC_DIR / "versions" / "005_clinica.py").read_text(encoding="utf-8")
    for modelo in (EstadoHallazgoCatalogo, HallazgoOdontograma, HistoriaClinica, Tratamiento):
        nombres = {c.name for c in modelo.__table__.constraints if c.name}
        nombres |= {i.name for i in modelo.__table__.indexes}
        assert nombres, modelo
        for nombre in nombres:
            assert nombre in texto, f"{nombre} está en el modelo pero no en 005_clinica.py"
    assert "def downgrade" in texto


def test_c08_catalogo_migracion_igual_a_constante():
    """La migración repite los literales: no pueden divergir de la constante (D-04)."""
    import importlib.util

    from app.modelos.hallazgo_odontograma import CATALOGO_ESTADOS_V1, CATALOGO_VERSION_V1

    spec = importlib.util.spec_from_file_location(
        "mig005", ALEMBIC_DIR / "versions" / "005_clinica.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert tuple(mod.CATALOGO_V1) == tuple(CATALOGO_ESTADOS_V1)
    assert mod.VERSION_V1 == CATALOGO_VERSION_V1


async def _cfg(monkeypatch):
    from db_utils import dsn_test, pg_reachable

    from alembic.config import Config

    ok, motivo = await pg_reachable()
    if not ok:
        pytest.skip(f"Postgres no reachable (¿compose down / sin Docker?): {motivo}")
    monkeypatch.setenv("DATABASE_URL", dsn_test())
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", dsn_test())
    return cfg


@pytest.mark.asyncio
async def test_c08_upgrade_carga_catalogo_sin_seed(monkeypatch):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from db_utils import dsn_test, reset_estado_base

    from alembic import command

    cfg = await _cfg(monkeypatch)
    await reset_estado_base(cfg, dsn_test())
    await asyncio.to_thread(command.upgrade, cfg, "head")
    engine = create_async_engine(dsn_test())
    try:
        async with engine.connect() as conn:
            filas = (await conn.execute(text(
                "SELECT codigo, nombre, alcance, version, vigente FROM estado_hallazgo_catalogo"
            ))).all()
            indices = {r[0] for r in (await conn.execute(text(
                "SELECT indexname FROM pg_indexes WHERE tablename='hallazgo_odontograma'"
            ))).all()}
    finally:
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, cfg, "base")
    from app.modelos.hallazgo_odontograma import CATALOGO_ESTADOS_V1

    assert {(f[0], f[1], f[2]) for f in filas} == set(CATALOGO_ESTADOS_V1)
    assert all(f[3] == 1 and f[4] is True for f in filas)
    assert "ix_hallazgo_hc_pieza" in indices and "uq_hallazgo_corrige_a" in indices


@pytest.mark.asyncio
async def test_c08_downgrade_upgrade_limpio(monkeypatch):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from db_utils import dsn_test, reset_estado_base

    from alembic import command

    cfg = await _cfg(monkeypatch)
    await reset_estado_base(cfg, dsn_test())
    await asyncio.to_thread(command.upgrade, cfg, "head")
    await asyncio.to_thread(command.downgrade, cfg, "004_espera")
    engine = create_async_engine(dsn_test())
    try:
        async with engine.connect() as conn:
            for tabla in TABLAS:
                assert await conn.scalar(text("SELECT to_regclass(:t)"), {"t": f"public.{tabla}"}) is None
            # La tabla de 004 sobrevive a la reversión de 005.
            assert await conn.scalar(text("SELECT to_regclass('public.espera_entry')")) is not None
        await asyncio.to_thread(command.upgrade, cfg, "head")
        async with engine.connect() as conn:
            for tabla in TABLAS:
                assert await conn.scalar(text("SELECT to_regclass(:t)"), {"t": f"public.{tabla}"}) is not None
    finally:
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, cfg, "base")
