"""C-02 tasks 6.1-6.2: seed idempotente con demo ficticia (PG real)."""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: F401  (fixture PG real con skip sin Docker)


async def _conteos(sesion_pg):
    from sqlalchemy import func, select
    from app.modelos import Profesional, Rol, Sillon, Usuario

    async def contar(modelo):
        return await sesion_pg.scalar(select(func.count()).select_from(modelo))
    return {
        "roles": await contar(Rol),
        "usuarios": await contar(Usuario),
        "sillones": await contar(Sillon),
        "profesionales": await contar(Profesional),
    }


@pytest.mark.asyncio
async def test_seed_doble_ejecucion_no_duplica(sesion_pg, monkeypatch):
    """Task 6.1 GREEN: dos corridas -> mismos conteos, sin IntegrityError."""
    from app.db.seed import run_seed

    monkeypatch.setenv("SEED_ADMIN_EMAIL", "admin@demo.test")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "demo-ficticia-123")
    await run_seed(sesion_pg)
    primera = await _conteos(sesion_pg)
    await run_seed(sesion_pg)
    segunda = await _conteos(sesion_pg)
    assert primera == segunda, f"el seed debe ser idempotente: {primera} vs {segunda}"


@pytest.mark.asyncio
async def test_seed_deja_roles_admin_sillon_profesional(sesion_pg, monkeypatch):
    """Task 6.2 GREEN: 3 roles sin dueno, 1 admin activo, sillon + profesional demo."""
    from sqlalchemy import select
    from app.db.seed import run_seed
    from app.esquemas.profesional import AgendaConfig
    from app.modelos import Profesional, Rol, Sillon, Usuario

    monkeypatch.setenv("SEED_ADMIN_EMAIL", "admin@demo.test")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "demo-ficticia-123")
    await run_seed(sesion_pg)

    roles = (await sesion_pg.execute(select(Rol.nombre))).scalars().all()
    assert sorted(roles) == ["admin", "odontologo", "secretaria"]
    assert "dueno" not in roles

    admins = (
        await sesion_pg.execute(
            select(Usuario).join(Rol).where(Rol.nombre == "admin", Usuario.activo.is_(True))
        )
    ).scalars().all()
    assert len(admins) == 1

    sillones = (
        await sesion_pg.execute(select(Sillon).where(Sillon.activo.is_(True)))
    ).scalars().all()
    assert len(sillones) >= 1
    assert all(s.nombre for s in sillones)

    profesionales = (await sesion_pg.execute(select(Profesional))).scalars().all()
    assert len(profesionales) >= 1
    agenda = AgendaConfig.model_validate(profesionales[0].agenda_config)
    assert agenda.duracion_slot_min > 0
    assert any(franjas for franjas in agenda.horario.values())


@pytest.mark.asyncio
async def test_seed_sin_password_aborta_fail_fast(sesion_pg, monkeypatch):
    """D-04: sin SEED_ADMIN_PASSWORD el seed falla explicito (no hardcodeo)."""
    from app.db.seed import run_seed

    monkeypatch.setenv("SEED_ADMIN_EMAIL", "admin@demo.test")
    monkeypatch.delenv("SEED_ADMIN_PASSWORD", raising=False)
    with pytest.raises(RuntimeError):
        await run_seed(sesion_pg)
