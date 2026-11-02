"""C-12 4.1: seed demo con pacientes ficticios, sin caja ni recibos (D-06).

Primera parte: datos del seed (corre sin Postgres). Segunda parte: seed real sobre Postgres
(sin Postgres se saltea y debe reportarse como NO EJECUTADA).
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: E402, F401


# --- datos del seed (sin Postgres) -----------------------------------------------------------------

def test_pacientes_demo_telefonos_son_digitos_validos_para_la_reserva_y_distintos():
    from app.db.seed import PACIENTES_DEMO
    from app.servicios.reserva_servicio import normalizar_telefono

    telefonos = [p.telefono for p in PACIENTES_DEMO]
    assert len(set(telefonos)) == len(telefonos) >= 4
    for telefono in telefonos:
        # Ya normalizado: la reserva busca por el telefono en digitos, tal cual.
        assert normalizar_telefono(telefono) == telefono
        assert telefono.startswith("54911") and "0000" in telefono


def test_pacientes_demo_dni_unicos_con_prefijo_de_prueba_y_emails_example():
    from app.db.seed import PACIENTES_DEMO

    dnis = [p.dni for p in PACIENTES_DEMO]
    assert len(set(dnis)) == len(dnis)
    assert all(d.startswith("9000") for d in dnis)
    assert all(p.email.endswith("@example.com") for p in PACIENTES_DEMO)


def test_pacientes_demo_hay_uno_con_plan_base_otro_con_plus_y_alguno_sin_plan():
    from app.db.seed import OBRA_SOCIAL_DEMO, PACIENTES_DEMO, PLANES_DEMO

    planes = {p.plan for p in PACIENTES_DEMO}
    assert set(PLANES_DEMO) <= planes
    assert None in planes
    assert OBRA_SOCIAL_DEMO == "OS Ficticia Demo"


# --- Postgres real ---------------------------------------------------------------------------------

@pytest.fixture
def env_seed(monkeypatch):
    monkeypatch.setenv("SEED_ADMIN_EMAIL", "admin@demo.test")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "demo-ficticia-123")


async def _contar(sesion, *modelos) -> dict[str, int]:
    from sqlalchemy import func, select

    return {
        m.__tablename__: await sesion.scalar(select(func.count()).select_from(m)) for m in modelos
    }


@pytest.mark.asyncio
async def test_pg_seed_en_base_limpia_deja_paciente_demo_con_plan_y_telefono_valido(sesion_pg, env_seed):
    from sqlalchemy import select

    from app.db.seed import run_seed
    from app.modelos import ObraSocial, Paciente, Plan
    from app.servicios.reserva_servicio import normalizar_telefono

    await run_seed(sesion_pg)
    filas = (
        await sesion_pg.execute(
            select(Paciente.telefono, Plan.nombre, ObraSocial.nombre)
            .join(Plan, Paciente.plan_id == Plan.id)
            .join(ObraSocial, Plan.obra_social_id == ObraSocial.id)
        )
    ).all()
    assert filas, "debe existir al menos un paciente demo con plan"
    assert all(os_nombre == "OS Ficticia Demo" for _, _, os_nombre in filas)
    assert {plan for _, plan, _ in filas} == {"Plan Base", "Plan Plus"}
    for telefono, _, _ in filas:
        assert normalizar_telefono(telefono) == telefono


@pytest.mark.asyncio
async def test_pg_seed_no_crea_cajas_movimientos_de_caja_ni_recibos(sesion_pg, env_seed):
    from app.db.seed import run_seed
    from app.modelos import Caja, MovimientoCaja, Recibo

    await run_seed(sesion_pg)
    assert await _contar(sesion_pg, Caja, MovimientoCaja, Recibo) == {
        "caja": 0, "movimiento_caja": 0, "recibo": 0,
    }


@pytest.mark.asyncio
async def test_pg_seed_doble_ejecucion_deja_iguales_los_conteos_pacientes_incluidos(sesion_pg, env_seed):
    from app.db.seed import run_seed
    from app.modelos import Paciente, Plan

    primera = await run_seed(sesion_pg)
    pacientes_1 = await _contar(sesion_pg, Paciente, Plan)
    segunda = await run_seed(sesion_pg)
    pacientes_2 = await _contar(sesion_pg, Paciente, Plan)
    assert primera == segunda
    assert primera["pacientes"] == pacientes_1["paciente"] >= 4
    assert pacientes_1 == pacientes_2


@pytest.mark.asyncio
async def test_pg_seed_no_pisa_un_paciente_demo_existente_con_otros_datos(sesion_pg, env_seed):
    from sqlalchemy import select

    from app.db.seed import PACIENTES_DEMO, run_seed
    from app.modelos import Paciente

    await run_seed(sesion_pg)
    demo = PACIENTES_DEMO[0]
    fila = await sesion_pg.scalar(select(Paciente).where(Paciente.dni == demo.dni))
    fila.notas = "editado por secretaria"
    fila.plan_id = None
    await sesion_pg.flush()
    await run_seed(sesion_pg)
    sesion_pg.expire_all()
    fila = await sesion_pg.scalar(select(Paciente).where(Paciente.dni == demo.dni))
    assert fila.notas == "editado por secretaria" and fila.plan_id is None
