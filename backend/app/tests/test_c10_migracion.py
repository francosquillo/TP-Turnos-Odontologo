"""C-10 grupo 1: migración 007_caja_recibos encadenada a 006_presupuestos_cc (D-01, D-14, D-15, D-25).

Las pruebas estáticas corren siempre; las de upgrade/downgrade usan Alembic real sobre
Postgres real (skip sin Docker). Datos 100% ficticios.
"""
import asyncio
import re
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "backend" / "alembic.ini"
ALEMBIC_DIR = REPO_ROOT / "backend" / "alembic"
MIGRACION = ALEMBIC_DIR / "versions" / "007_caja_recibos.py"
TABLAS = ("caja", "recibo", "recibo_contador", "movimiento_caja")
FUNCIONES = (
    "caja_proteger", "recibo_proteger", "movimiento_caja_inmutable", "movimiento_caja_caja_abierta",
)
PARES_DDL = (
    "FUNCION_CAJA_PROTEGER_DDL", "TRIGGER_CAJA_PROTEGER_DDL", "FUNCION_CAJA_PROTEGER_DROP",
    "FUNCION_RECIBO_PROTEGER_DDL", "TRIGGER_RECIBO_PROTEGER_DDL", "FUNCION_RECIBO_PROTEGER_DROP",
    "FUNCION_MOVCAJA_INMUTABLE_DDL", "TRIGGER_MOVCAJA_INMUTABLE_DDL",
    "FUNCION_MOVCAJA_INMUTABLE_DROP", "FUNCION_MOVCAJA_CAJA_ABIERTA_DDL",
    "TRIGGER_MOVCAJA_CAJA_ABIERTA_DDL", "FUNCION_MOVCAJA_CAJA_ABIERTA_DROP",
)


def _normalizar(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def _cargar_migracion():
    import importlib.util

    spec = importlib.util.spec_from_file_location("mig007", MIGRACION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_c10_cabeza_unica_007_sobre_006():
    from alembic.script import ScriptDirectory

    script = ScriptDirectory(str(ALEMBIC_DIR))
    assert script.get_heads() == ["007_caja_recibos"]
    assert script.get_revision("007_caja_recibos").down_revision == "006_presupuestos_cc"


def test_c10_migracion_declara_checks_e_indices_del_modelo():
    from app.modelos import Caja, Movimiento, MovimientoCaja, Recibo, ReciboContador

    texto = MIGRACION.read_text(encoding="utf-8")
    for modelo in (Caja, Recibo, ReciboContador, MovimientoCaja):
        nombres = {c.name for c in modelo.__table__.constraints if c.name}
        nombres |= {i.name for i in modelo.__table__.indexes}
        assert nombres, modelo
        for nombre in nombres:
            assert nombre in texto, f"{nombre} está en el modelo pero no en 007_caja_recibos.py"
    # Lo que 007 agrega sobre `movimiento` (D-15).
    for nombre in ("fk_movimiento_recibo", "ix_movimiento_recibo_id",
                   "uq_movimiento_pago_recibo", "ck_movimiento_pago_con_recibo"):
        assert nombre in texto
        en_modelo = {c.name for c in Movimiento.__table__.constraints if c.name} | {
            i.name for i in Movimiento.__table__.indexes}
        assert nombre in en_modelo
    assert "def downgrade" in texto


def test_c10_triggers_migracion_iguales_a_modelo():
    """La migración repite los literales del DDL: no pueden divergir del modelo (D-14)."""
    from app.modelos import caja as modelo

    mig = _cargar_migracion()
    for nombre in PARES_DDL:
        assert _normalizar(getattr(mig, nombre)) == _normalizar(getattr(modelo, nombre)), nombre
        # Una sola sentencia por execute (asyncpg) y sin `%` (DDL() interpola con %).
        assert "%" not in getattr(modelo, nombre)
    for nombre in PARES_DDL:
        if nombre.startswith("TRIGGER_"):
            assert ";" not in _normalizar(getattr(mig, nombre))


def test_c10_comparacion_detecta_divergencia():
    """Control: la normalización distingue un literal distinto (el test no es vacuo)."""
    from app.modelos.caja import TRIGGER_RECIBO_PROTEGER_DDL

    assert _normalizar(TRIGGER_RECIBO_PROTEGER_DDL) != _normalizar(
        TRIGGER_RECIBO_PROTEGER_DDL.replace("UPDATE OR DELETE", "DELETE")
    )


def test_c10_clave_regex_de_migracion_igual_a_modelo():
    from app.modelos.caja import CLAVE_REGEX

    assert _cargar_migracion().CLAVE_REGEX == CLAVE_REGEX


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
async def test_c10_fk_recibo_existe_tras_upgrade(monkeypatch):
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
            fk = await conn.scalar(text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'fk_movimiento_recibo'"))
            indices = {r[0]: r[1] for r in (await conn.execute(text(
                "SELECT indexname, indexdef FROM pg_indexes WHERE tablename='movimiento'"
            ))).all()}
            checks = (await conn.execute(text(
                "SELECT conname FROM pg_constraint WHERE conrelid = 'movimiento'::regclass "
                "AND contype = 'c'"))).scalars().all()
            triggers = {t: (await conn.execute(text(
                f"SELECT tgname FROM pg_trigger WHERE tgrelid = '{t}'::regclass "
                "AND NOT tgisinternal ORDER BY tgname"))).scalars().all() for t in TABLAS}
            clave = await conn.scalar(text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_recibo_clave_formato'"))
    finally:
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, cfg, "base")
    assert "FOREIGN KEY (recibo_id) REFERENCES recibo(id) ON DELETE RESTRICT" in fk
    assert "WHERE (tipo = 'pago'::text)" in indices["uq_movimiento_pago_recibo"]
    assert "ix_movimiento_recibo_id" in indices
    assert "ck_movimiento_pago_con_recibo" in checks
    assert triggers["caja"] == ["trg_caja_proteger"]
    assert triggers["recibo"] == ["trg_recibo_proteger"]
    assert triggers["movimiento_caja"] == [
        "trg_movimiento_caja_caja_abierta", "trg_movimiento_caja_inmutable"]
    assert triggers["recibo_contador"] == []
    assert "4[0-9a-f]{3}" in clave


@pytest.mark.asyncio
async def test_c10_downgrade_upgrade_limpio(monkeypatch):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from db_utils import dsn_test, reset_estado_base

    from alembic import command

    cfg = await _cfg(monkeypatch)
    await reset_estado_base(cfg, dsn_test())
    await asyncio.to_thread(command.upgrade, cfg, "head")
    await asyncio.to_thread(command.downgrade, cfg, "006_presupuestos_cc")
    engine = create_async_engine(dsn_test())
    try:
        async with engine.connect() as conn:
            for tabla in TABLAS:
                assert await conn.scalar(text("SELECT to_regclass(:t)"), {"t": f"public.{tabla}"}) is None
            for funcion in FUNCIONES:
                assert await conn.scalar(text("SELECT to_regproc(:f)"), {"f": funcion}) is None
            # Las tablas de 006 sobreviven y `movimiento` pierde lo que agregó 007.
            assert await conn.scalar(text("SELECT to_regclass('public.movimiento')")) is not None
            assert await conn.scalar(text(
                "SELECT count(*) FROM pg_constraint WHERE conname IN "
                "('fk_movimiento_recibo', 'ck_movimiento_pago_con_recibo')")) == 0
            assert await conn.scalar(text(
                "SELECT count(*) FROM pg_indexes WHERE indexname IN "
                "('ix_movimiento_recibo_id', 'uq_movimiento_pago_recibo')")) == 0
        await asyncio.to_thread(command.upgrade, cfg, "head")
        async with engine.connect() as conn:
            for tabla in TABLAS:
                assert await conn.scalar(text("SELECT to_regclass(:t)"), {"t": f"public.{tabla}"}) is not None
            for funcion in FUNCIONES:
                assert await conn.scalar(text("SELECT to_regproc(:f)"), {"f": funcion}) is not None
    finally:
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, cfg, "base")
