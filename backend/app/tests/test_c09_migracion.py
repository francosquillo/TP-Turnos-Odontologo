"""C-09 grupo 1: migración 006_presupuestos_cc encadenada a 005_clinica (D-01, D-12).

Las pruebas estáticas corren siempre; las de upgrade/downgrade usan Alembic
real sobre Postgres real (skip sin Docker). Datos 100% ficticios.
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
MIGRACION = ALEMBIC_DIR / "versions" / "006_presupuestos_cc.py"
TABLAS = ("presupuesto", "item_presupuesto", "cuenta_corriente", "movimiento")


def _normalizar(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def test_c09_cabeza_unica_006_sobre_005():
    from alembic.script import ScriptDirectory

    script = ScriptDirectory(str(ALEMBIC_DIR))
    # La cabeza avanzó con C-11 (008); 006 sigue colgando de 005 y 007 de 006.
    assert script.get_heads() == ["009_auditoria_admin"]
    assert script.get_revision("006_presupuestos_cc").down_revision == "005_clinica"
    assert script.get_revision("007_caja_recibos").down_revision == "006_presupuestos_cc"


def test_c09_migracion_declara_checks_e_indices_del_modelo():
    from app.modelos import CuentaCorriente, ItemPresupuesto, Movimiento, Presupuesto

    texto = MIGRACION.read_text(encoding="utf-8")
    # Lo que C-10 agregó a `movimiento` (D-15) vive en 007_caja_recibos.py, no en 006.
    de_c10 = {"fk_movimiento_recibo", "ix_movimiento_recibo_id", "uq_movimiento_pago_recibo",
              "ck_movimiento_pago_con_recibo"}
    # Lo que C-11 agregó (D-03, D-05, D-07) vive en 008_obras_sociales.py.
    de_c11 = {"uq_movimiento_cobertura_presupuesto", "ix_presupuesto_plan_id",
              "ix_item_presupuesto_arancel_id", "ck_item_cubierto_no_negativo"}
    for modelo in (Presupuesto, ItemPresupuesto, CuentaCorriente, Movimiento):
        nombres = {c.name for c in modelo.__table__.constraints if c.name}
        nombres |= {i.name for i in modelo.__table__.indexes}
        nombres -= de_c10 | de_c11
        assert nombres, modelo
        for nombre in nombres:
            assert nombre in texto, f"{nombre} está en el modelo pero no en 006_presupuestos_cc.py"
    assert "def downgrade" in texto


def test_c09_migracion_no_agrega_fk_a_recibo_ni_columna_saldo():
    texto = MIGRACION.read_text(encoding="utf-8")
    assert "recibo.id" not in texto and "recibo\"" not in texto
    assert '"saldo"' not in texto


def _cargar_migracion():
    import importlib.util

    spec = importlib.util.spec_from_file_location("mig006", MIGRACION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_c09_trigger_migracion_igual_a_modelo():
    """La migración repite los literales del DDL: no pueden divergir del modelo (D-12)."""
    from app.modelos.cuenta_corriente import (
        FUNCION_INMUTABLE_DDL, FUNCION_INMUTABLE_DROP, TRIGGER_INMUTABLE_DDL,
    )

    mig = _cargar_migracion()
    assert _normalizar(mig.FUNCION_INMUTABLE_DDL) == _normalizar(FUNCION_INMUTABLE_DDL)
    assert _normalizar(mig.TRIGGER_INMUTABLE_DDL) == _normalizar(TRIGGER_INMUTABLE_DDL)
    assert _normalizar(mig.FUNCION_INMUTABLE_DROP) == _normalizar(FUNCION_INMUTABLE_DROP)
    # Cada sentencia es una sola (asyncpg no acepta varias en un execute).
    assert ";" not in _normalizar(mig.TRIGGER_INMUTABLE_DDL)


def test_c09_comparacion_detecta_divergencia():
    """Control: la normalización distingue un literal distinto (el test no es vacuo)."""
    from app.modelos.cuenta_corriente import TRIGGER_INMUTABLE_DDL

    assert _normalizar(TRIGGER_INMUTABLE_DDL) != _normalizar(
        TRIGGER_INMUTABLE_DDL.replace("UPDATE OR DELETE", "DELETE")
    )


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
async def test_c09_downgrade_upgrade_limpio(monkeypatch):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from db_utils import dsn_test, reset_estado_base

    from alembic import command

    cfg = await _cfg(monkeypatch)
    await reset_estado_base(cfg, dsn_test())
    await asyncio.to_thread(command.upgrade, cfg, "head")
    await asyncio.to_thread(command.downgrade, cfg, "005_clinica")
    engine = create_async_engine(dsn_test())
    try:
        async with engine.connect() as conn:
            for tabla in TABLAS:
                assert await conn.scalar(text("SELECT to_regclass(:t)"), {"t": f"public.{tabla}"}) is None
            assert await conn.scalar(text("SELECT to_regproc('movimiento_inmutable')")) is None
            # Las tablas de 005 sobreviven a la reversión de 006.
            assert await conn.scalar(text("SELECT to_regclass('public.hallazgo_odontograma')")) is not None
        await asyncio.to_thread(command.upgrade, cfg, "head")
        async with engine.connect() as conn:
            for tabla in TABLAS:
                assert await conn.scalar(text("SELECT to_regclass(:t)"), {"t": f"public.{tabla}"}) is not None
            assert await conn.scalar(text("SELECT to_regproc('movimiento_inmutable')")) is not None
    finally:
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, cfg, "base")


@pytest.mark.asyncio
async def test_c09_upgrade_deja_el_trigger_y_los_indices_parciales(monkeypatch):
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
            trig = (await conn.execute(text(
                "SELECT tgname FROM pg_trigger WHERE tgrelid = 'movimiento'::regclass AND NOT tgisinternal"
            ))).scalars().all()
            indices = {r[0]: r[1] for r in (await conn.execute(text(
                "SELECT indexname, indexdef FROM pg_indexes WHERE tablename='movimiento'"
            ))).all()}
            columnas = {r[0] for r in (await conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='cuenta_corriente'"
            ))).all()}
            recibo_fk = await conn.scalar(text(
                "SELECT count(*) FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage k USING (constraint_name) "
                "WHERE tc.table_name='movimiento' AND tc.constraint_type='FOREIGN KEY' "
                "AND k.column_name='recibo_id'"
            ))
    finally:
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, cfg, "base")
    assert trig == ["trg_movimiento_inmutable"]
    assert "WHERE (tipo = 'cargo'::text)" in indices["uq_movimiento_cargo_presupuesto"]
    assert "WHERE (anula_a_id IS NOT NULL)" in indices["uq_movimiento_anula_a"]
    assert "saldo" not in columnas
    # Con 006 solo, `recibo_id` no tenía FK; al llegar a la cabeza 007 (C-10, D-15) la tiene.
    assert recibo_fk == 1
