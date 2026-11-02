"""C-11 task 2.1: repos de obra social y arancel contra PG real (bordes de vigencia)."""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c11_helpers import crear_arancel, crear_os, crear_plan, sembrar_c11  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401


async def _repo(sesion):
    from app.repos.obra_social_repo import ArancelRepository

    return ArancelRepository(sesion)


@pytest.mark.asyncio
async def test_arancel_vigente_bordes_inclusivos(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    repo = await _repo(sesion_pg)
    a1 = await crear_arancel(sesion_pg, m.plan_plus, "N-050", "100.00",
                             desde=date(2026, 1, 1), hasta=date(2026, 9, 30))
    a2 = await crear_arancel(sesion_pg, m.plan_plus, "N-050", "130.00", desde=date(2026, 10, 1))
    id1, id2 = a1.id, a2.id
    assert (await repo.arancel_vigente(m.plan_plus.id, "N-050", date(2026, 1, 1))).id == id1
    assert (await repo.arancel_vigente(m.plan_plus.id, "N-050", date(2026, 9, 30))).id == id1
    assert (await repo.arancel_vigente(m.plan_plus.id, "N-050", date(2026, 10, 1))).id == id2
    assert (await repo.arancel_vigente(m.plan_plus.id, "N-050", date(2099, 1, 1))).id == id2


@pytest.mark.asyncio
async def test_arancel_vigente_none_antes_de_la_vigencia_o_otro_plan_o_codigo(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    repo = await _repo(sesion_pg)
    assert await repo.arancel_vigente(m.plan_base.id, "N-003", date(2025, 12, 31)) is None
    assert await repo.arancel_vigente(m.plan_base.id, "N-999", date(2026, 6, 1)) is None
    plan_ajeno = await crear_plan(sesion_pg, await crear_os(sesion_pg), "Otro")
    assert await repo.arancel_vigente(plan_ajeno.id, "N-003", date(2026, 6, 1)) is None


@pytest.mark.asyncio
async def test_arancel_vigente_con_cierre_no_cubre_el_dia_siguiente(sesion_pg):
    m = await sembrar_c11(sesion_pg)
    repo = await _repo(sesion_pg)
    await crear_arancel(sesion_pg, m.plan_plus, "N-060", "100.00",
                        desde=date(2026, 3, 1), hasta=date(2026, 3, 31))
    vigente = await repo.arancel_vigente(m.plan_plus.id, "N-060", date(2026, 3, 31))
    assert vigente is not None and vigente.precio == Decimal("100.00")
    assert await repo.arancel_vigente(m.plan_plus.id, "N-060", date(2026, 4, 1)) is None


@pytest.mark.asyncio
async def test_listar_planes_con_obra_y_filtro_por_obra(sesion_pg):
    from app.repos.obra_social_repo import PlanRepository

    m = await sembrar_c11(sesion_pg)
    otra = await crear_os(sesion_pg, "Otra OS")
    await crear_plan(sesion_pg, otra, "Unico")
    repo = PlanRepository(sesion_pg)
    todos = await repo.listar()
    de_demo = await repo.listar(m.os.id)
    assert {p.plan.nombre for p in todos} == {"Plan Base", "Plan Plus", "Unico"}
    assert {p.plan.nombre for p in de_demo} == {"Plan Base", "Plan Plus"}
    assert all(p.obra_social.id == m.os.id for p in de_demo)
