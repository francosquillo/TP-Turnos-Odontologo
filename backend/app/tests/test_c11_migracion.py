"""C-11 grupo 1: migración 008_obras_sociales encadenada a 007_caja_recibos (D-01, D-14).

Las pruebas estáticas corren siempre; las de upgrade/downgrade usan Alembic real sobre
Postgres real (skip sin Docker). Datos 100% ficticios.
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
MIGRACION = ALEMBIC_DIR / "versions" / "008_obras_sociales.py"
TABLAS_NUEVAS = ("obra_social", "plan", "arancel", "liquidacion", "item_liquidacion")


def test_c11_cabeza_unica_008_sobre_007():
    from alembic.script import ScriptDirectory

    script = ScriptDirectory(str(ALEMBIC_DIR))
    assert script.get_heads() == ["009_auditoria_admin"]  # C-12 R3 avanzo la cabeza
    assert script.get_revision("008_obras_sociales").down_revision == "007_caja_recibos"


def test_c11_migracion_declara_todos_los_nombres_del_modelo():
    from app.modelos import (
        Arancel, ItemLiquidacion, ItemPresupuesto, Liquidacion, Movimiento, MovimientoCaja,
        ObraSocial, Paciente, Plan, Presupuesto,
    )

    texto = MIGRACION.read_text(encoding="utf-8")
    for modelo in (ObraSocial, Plan, Arancel, Liquidacion, ItemLiquidacion):
        nombres = {c.name for c in modelo.__table__.constraints if c.name}
        nombres |= {i.name for i in modelo.__table__.indexes}
        assert nombres, modelo
        for nombre in nombres:
            assert nombre in texto, f"{nombre} está en el modelo pero no en 008_obras_sociales.py"
    # Lo que 008 agrega sobre tablas existentes.
    agregados = {
        Movimiento: ("uq_movimiento_cobertura_presupuesto",),
        MovimientoCaja: (
            "ck_movcaja_una_referencia", "ix_movcaja_liquidacion_id",
            "uq_movcaja_liq_ingreso", "uq_movcaja_liq_reversion",
        ),
        Paciente: ("ix_paciente_plan_id",),
        Presupuesto: ("ix_presupuesto_plan_id",),
        ItemPresupuesto: ("ix_item_presupuesto_arancel_id", "ck_item_cubierto_no_negativo"),
    }
    for modelo, nombres in agregados.items():
        en_modelo = {c.name for c in modelo.__table__.constraints if c.name} | {
            i.name for i in modelo.__table__.indexes}
        for nombre in nombres:
            assert nombre in en_modelo, f"{nombre} falta en el modelo {modelo.__name__}"
            assert nombre in texto, f"{nombre} falta en 008_obras_sociales.py"
    assert "def downgrade" in texto


def test_c11_movimiento_caja_acepta_recibo_o_liquidacion():
    from app.modelos import MovimientoCaja

    columnas = MovimientoCaja.__table__.c
    assert columnas.recibo_id.nullable is True
    assert columnas.liquidacion_id.nullable is True


def test_c11_literales_de_indices_parciales_iguales_en_modelo_y_migracion():
    """La migración repite el predicado de los índices parciales del modelo."""
    texto = MIGRACION.read_text(encoding="utf-8")
    for fragmento in (
        "num_nonnulls(recibo_id, liquidacion_id) = 1",
        "tipo = 'ajuste' AND anula_a_id IS NULL AND recibo_id IS NULL AND monto < 0",
        "daterange(vigencia_desde, vigencia_hasta, '[]')",
    ):
        assert fragmento in texto, fragmento


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
async def test_c11_upgrade_crea_tablas_y_constraints(monkeypatch):
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
            for tabla in TABLAS_NUEVAS:
                assert await conn.scalar(text("SELECT to_regclass(:t)"), {"t": f"public.{tabla}"})
            exclusion = await conn.scalar(text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ex_arancel_sin_solape'"))
            una_ref = await conn.scalar(text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_movcaja_una_referencia'"))
            nulable = await conn.scalar(text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name='movimiento_caja' AND column_name='recibo_id'"))
            triggers = (await conn.execute(text(
                "SELECT tgname FROM pg_trigger WHERE tgrelid = 'movimiento_caja'::regclass "
                "AND NOT tgisinternal ORDER BY tgname"))).scalars().all()
    finally:
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, cfg, "base")
    assert "EXCLUDE USING gist" in exclusion
    assert "num_nonnulls" in una_ref
    assert nulable == "YES"
    assert triggers == ["trg_movimiento_caja_caja_abierta", "trg_movimiento_caja_inmutable"]


@pytest.mark.asyncio
async def test_c11_downgrade_a_007_sin_datos_y_upgrade_limpio(monkeypatch):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from db_utils import dsn_test, reset_estado_base

    from alembic import command

    cfg = await _cfg(monkeypatch)
    await reset_estado_base(cfg, dsn_test())
    await asyncio.to_thread(command.upgrade, cfg, "head")
    await asyncio.to_thread(command.downgrade, cfg, "007_caja_recibos")
    engine = create_async_engine(dsn_test())
    try:
        async with engine.connect() as conn:
            for tabla in TABLAS_NUEVAS:
                assert await conn.scalar(text("SELECT to_regclass(:t)"), {"t": f"public.{tabla}"}) is None
            assert await conn.scalar(text(
                "SELECT count(*) FROM information_schema.columns WHERE "
                "table_name='paciente' AND column_name='plan_id'")) == 0
            assert await conn.scalar(text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name='movimiento_caja' AND column_name='recibo_id'")) == "NO"
        await asyncio.to_thread(command.upgrade, cfg, "head")
    finally:
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, cfg, "base")
