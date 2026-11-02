"""C-12 7.1: migracion 009_auditoria_admin encadenada a 008_obras_sociales (R3, D-10).

Las pruebas estaticas corren siempre; las de upgrade/downgrade y la inmutabilidad usan Alembic y
Postgres reales (skip sin Docker: deben reportarse como NO EJECUTADAS). Datos ficticios.
"""
import asyncio
import importlib.util
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
MIGRACION = ALEMBIC_DIR / "versions" / "009_auditoria_admin.py"
PARES_DDL = ("FUNCION_AUDITORIA_INMUTABLE_DDL", "TRIGGER_AUDITORIA_INMUTABLE_DDL",
             "FUNCION_AUDITORIA_INMUTABLE_DROP")


def _normalizar(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def _cargar_migracion():
    spec = importlib.util.spec_from_file_location("mig009", MIGRACION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_c12_cabeza_unica_009_sobre_008():
    from alembic.script import ScriptDirectory

    script = ScriptDirectory(str(ALEMBIC_DIR))
    assert script.get_heads() == ["009_auditoria_admin"]
    assert script.get_revision("009_auditoria_admin").down_revision == "008_obras_sociales"


def test_c12_migracion_declara_todos_los_nombres_del_modelo_y_tiene_downgrade():
    from app.modelos import EventoAuditoria

    texto = MIGRACION.read_text(encoding="utf-8")
    nombres = {c.name for c in EventoAuditoria.__table__.constraints if c.name}
    nombres |= {i.name for i in EventoAuditoria.__table__.indexes}
    assert {"ck_evento_auditoria_accion", "ix_evento_auditoria_created_at",
            "ix_evento_auditoria_actor_id"} <= nombres
    for nombre in nombres:
        assert nombre in texto, f"{nombre} está en el modelo pero no en 009_auditoria_admin.py"
    assert "def downgrade" in texto


def test_c12_trigger_y_acciones_de_la_migracion_iguales_a_las_del_modelo():
    from app.modelos import auditoria as modelo

    mig = _cargar_migracion()
    for nombre in PARES_DDL:
        assert _normalizar(getattr(mig, nombre)) == _normalizar(getattr(modelo, nombre)), nombre
        assert "%" not in getattr(modelo, nombre)  # DDL() interpola con %
    assert ";" not in _normalizar(mig.TRIGGER_AUDITORIA_INMUTABLE_DDL)  # una sentencia por execute
    assert tuple(mig.ACCIONES) == tuple(modelo.ACCIONES)
    assert "UPDATE OR DELETE" in modelo.TRIGGER_AUDITORIA_INMUTABLE_DDL


def test_c12_acciones_cubren_las_auditadas_por_la_spec():
    from app.modelos.auditoria import ACCIONES

    assert set(ACCIONES) == {
        "usuario_alta", "usuario_edicion", "usuario_desactivacion", "usuario_eliminacion",
        "pacientes_importacion", "exportacion_total",
    }


# --- Postgres real ---------------------------------------------------------------------------------

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
async def test_pg_upgrade_crea_tabla_con_trigger_y_downgrade_a_008_la_quita_limpia(monkeypatch):
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
            assert await conn.scalar(text("SELECT to_regclass('public.evento_auditoria')"))
            triggers = (await conn.execute(text(
                "SELECT tgname FROM pg_trigger WHERE tgrelid = 'evento_auditoria'::regclass "
                "AND NOT tgisinternal"))).scalars().all()
        assert triggers == ["trg_evento_auditoria_inmutable"]
        await asyncio.to_thread(command.downgrade, cfg, "008_obras_sociales")
        async with engine.connect() as conn:
            assert await conn.scalar(text("SELECT to_regclass('public.evento_auditoria')")) is None
            assert await conn.scalar(text(
                "SELECT count(*) FROM pg_proc WHERE proname = 'evento_auditoria_inmutable'")) == 0
        await asyncio.to_thread(command.upgrade, cfg, "head")
    finally:
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, cfg, "base")


@pytest.mark.asyncio
async def test_pg_update_y_delete_sobre_un_evento_fallan(sesion_pg):
    import sqlalchemy as sa
    from sqlalchemy.exc import DBAPIError

    from app.modelos import EventoAuditoria, Rol, Usuario

    rol = Rol(nombre="admin")
    sesion_pg.add(rol)
    await sesion_pg.flush()
    admin = Usuario(nombre="Admin", email="a@demo.test", password_hash="no-login", rol_id=rol.id)
    sesion_pg.add(admin)
    await sesion_pg.flush()
    evento = EventoAuditoria(actor_id=admin.id, accion="usuario_alta", objeto_tipo="usuario",
                             objeto_id=admin.id, detalle={"rol": "admin"})
    sesion_pg.add(evento)
    await sesion_pg.flush()
    await sesion_pg.commit()
    evento_id = evento.id
    for sentencia in ("UPDATE evento_auditoria SET accion = 'usuario_edicion' WHERE id = :i",
                      "DELETE FROM evento_auditoria WHERE id = :i"):
        with pytest.raises(DBAPIError):
            await sesion_pg.execute(sa.text(sentencia), {"i": evento_id})
        await sesion_pg.rollback()
    assert await sesion_pg.scalar(sa.text("SELECT accion FROM evento_auditoria")) == "usuario_alta"


@pytest.mark.asyncio
async def test_pg_accion_fuera_del_catalogo_viola_el_check(sesion_pg):
    from sqlalchemy.exc import IntegrityError

    from app.modelos import EventoAuditoria, Rol, Usuario

    rol = Rol(nombre="admin")
    sesion_pg.add(rol)
    await sesion_pg.flush()
    admin = Usuario(nombre="Admin", email="a@demo.test", password_hash="no-login", rol_id=rol.id)
    sesion_pg.add(admin)
    await sesion_pg.flush()
    sesion_pg.add(EventoAuditoria(actor_id=admin.id, accion="borrar_todo", objeto_tipo="usuario"))
    with pytest.raises(IntegrityError):
        await sesion_pg.flush()
    await sesion_pg.rollback()


from db_utils import sesion_pg  # noqa: E402, F401
