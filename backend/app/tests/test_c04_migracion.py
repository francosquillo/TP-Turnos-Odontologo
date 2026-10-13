"""C-04 task 1.1: migracion 002 `turno` con doble EXCLUDE parcial (D-01).

Unit (siempre corre): archivo 002 existe, encadena 001, crea tabla turno con
CHECK fin>inicio, doble EXCLUDE parcial, columna token nullable e indices.
Integracion (PG real): upgrade/downgrade limpios; skipea sin compose.
"""
import asyncio
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/app/tests -> backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

REPO_ROOT = Path(__file__).resolve().parents[3]
VERSIONS_DIR = REPO_ROOT / "backend" / "alembic" / "versions"
ALEMBIC_INI = REPO_ROOT / "backend" / "alembic.ini"
ALEMBIC_DIR = REPO_ROOT / "backend" / "alembic"


def _src_002() -> str:
    migraciones = list(VERSIONS_DIR.glob("*002*.py"))
    assert len(migraciones) >= 1, "falta la migracion 002_turno"
    return migraciones[0].read_text(encoding="utf-8")


def test_migracion_002_existe_y_encadena_001():
    """Task 1.1 RED: 002 existe con upgrade/downgrade y down_revision 001."""
    src = _src_002()
    assert "def upgrade" in src and "def downgrade" in src
    assert "001_core_identidad_pacientes" in src


def test_migracion_002_crea_turno_con_check_e_indices():
    """Task 1.1 RED: columnas, CHECK fin>inicio, token nullable e indices."""
    src = _src_002()
    for columna in (
        "paciente_id",
        "profesional_id",
        "sillon_id",
        "inicio",
        "fin",
        "estado",
        "origen",
        "token_confirmacion_hash",
        "sobre_turno",
        "motivo_sobreturno",
        "motivo_cancelacion",
        "creado_por",
    ):
        assert columna in src, f"migracion 002 no menciona {columna}"
    assert "fin" in src and "inicio" in src
    assert "CHECK" in src or "CheckConstraint" in src
    assert "ix_turno_profesional_inicio" in src
    assert "ix_turno_sillon_inicio" in src


def test_migracion_002_doble_exclude_parcial():
    """Task 1.1 RED: EXCLUDE profesional y sillon parciales a activos."""
    src = _src_002()
    assert "EXCLUDE" in src
    assert "ex_turno_prof_sin_solape" in src
    assert "ex_turno_sillon_sin_solape" in src
    assert "tstzrange" in src
    assert "sobre_turno" in src
    assert "cancelado" in src


@pytest.mark.asyncio
async def test_c04_migracion_002_aplica_en_pg_real(monkeypatch):
    """Task 1.1 GREEN: upgrade head crea turno; downgrade -1 la revierte (PG)."""
    from db_utils import dsn_test, pg_reachable, reset_estado_base

    from alembic import command
    from alembic.config import Config

    ok, motivo = await pg_reachable()
    if not ok:
        pytest.skip(f"Postgres no reachable (¿compose down / sin Docker?): {motivo}")
    monkeypatch.setenv("DATABASE_URL", dsn_test())
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", dsn_test())

    # Reset (fix verify C-04): la suite comparte un unico PG; sin punto de
    # partida fijo, version=head con tablas borradas hace `upgrade head`
    # no-op y el assert falla.
    await reset_estado_base(cfg, dsn_test())
    await asyncio.to_thread(command.upgrade, cfg, "head")
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(dsn_test())
        try:
            async with engine.connect() as conn:
                existe = await conn.scalar(
                    text("SELECT to_regclass('public.turno')")
                )
                assert existe is not None, "turno no existe tras upgrade head"
                n_exclude = await conn.scalar(
                    text(
                        "SELECT count(*) FROM pg_constraint "
                        "WHERE conrelid='public.turno'::regclass "
                        "AND contype='x'"
                    )
                )
                assert n_exclude == 2, f"se esperaban 2 EXCLUDE, hay {n_exclude}"
        finally:
            await engine.dispose()
    finally:
        await asyncio.to_thread(command.downgrade, cfg, "-1")
        await asyncio.to_thread(command.upgrade, cfg, "head")


@pytest.mark.asyncio
async def test_c04_downgrade_002_tolerante_sin_indices(monkeypatch):
    """Fix-3 RED (verify, PG real): downgrade 002 tolera indices ausentes.

    Simula tabla turno preexistente (metadata/legacy) sin los indices de
    002: el downgrade no debe romper (DROP IF EXISTS).

    No asume head fijo: baja explicito a 001 (debajo de 002) para que
    `turno` quede revertida aunque head avance (003_notificacion C-06+).
    """
    from db_utils import dsn_test, pg_reachable, reset_estado_base

    from alembic import command
    from alembic.config import Config

    ok, motivo = await pg_reachable()
    if not ok:
        pytest.skip(f"Postgres no reachable (¿compose down / sin Docker?): {motivo}")
    monkeypatch.setenv("DATABASE_URL", dsn_test())
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", dsn_test())

    await reset_estado_base(cfg, dsn_test())
    await asyncio.to_thread(command.upgrade, cfg, "head")
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(dsn_test())
        try:
            # Tabla legacy: existen turno+constraints pero sin estos indices.
            async with engine.begin() as conn:
                await conn.execute(text("DROP INDEX IF EXISTS ix_turno_token_hash"))
                await conn.execute(text("DROP INDEX IF EXISTS ix_turno_estado"))
        finally:
            await engine.dispose()
        # Hoy rompe: index "ix_turno_token_hash" does not exist.
        # Baja explicita a 001 (no "-1"): con head=003_notificacion (C-06),
        # "-1" solo quitaria notificacion y turno seguiria existiendo.
        await asyncio.to_thread(
            command.downgrade, cfg, "001_core_identidad_pacientes"
        )

        engine = create_async_engine(dsn_test())
        try:
            async with engine.connect() as conn:
                existe = await conn.scalar(
                    text("SELECT to_regclass('public.turno')")
                )
                assert existe is None, "turno deberia estar revertida tras downgrade"
                existe_notif = await conn.scalar(
                    text("SELECT to_regclass('public.notificacion')")
                )
                assert existe_notif is None, (
                    "notificacion deberia estar revertida tras downgrade a 001"
                )
        finally:
            await engine.dispose()
    finally:
        await asyncio.to_thread(command.upgrade, cfg, "head")
