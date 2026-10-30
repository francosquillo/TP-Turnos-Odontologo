"""C-07 grupo 1: repos/espera_repo.py matching FIFO compatible (D-01).

RED primero: modulos/funciones inexistentes fallan. Luego GREEN con
repos/espera_repo.py. Tests de lógica de filtrado (siempre corren, sin PG)
+ integración PG/Redis-gated (skipea sin Docker).
Datos 100% ficticios.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]  # backend/app/tests -> backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

LUNES_9 = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)  # lunes 09:00 BA
MARTES_9 = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)  # martes 09:00 BA


def _fabricar_entrada(id, **cambios):
    datos = {
        "id": id,
        "paciente_id": 1,
        "profesional_id": 1,
        "especialidad": "Odontología general",
        "preferencia_horaria": None,
        "estado": "activa",
        "oferta_expira_en": None,
        "token_oferta_hash": None,
        "oferta_hueco": None,
        "motivo_baja": None,
        "created_at": LUNES_9 + timedelta(minutes=id),
    }
    datos.update(cambios)
    return datos


# --- helpers de lógica pura (probables directamente) -------------------------

from app.repos.espera_repo import _cumple_preferencia, _especialidad_compatible  # noqa: E402


@pytest.mark.parametrize(
    "esp_entry, esp_prof, esperado",
    [
        ("Odontología general", "Odontología general, Cirugía", True),
        (None, "Odontología general", True),          # sin especialidad = ok
        ("Cirugía", "Odontología general", False),    # no está en el profesional
        ("Ortodoncia", "", False),                    # profesional sin especialidades
    ],
)
def test_especialidad_compatible(esp_entry, esp_prof, esperado):
    """Task 1.3 RED: especialidad de entry contenida en las del profesional."""
    assert _especialidad_compatible(esp_entry, esp_prof) is esperado


@pytest.mark.parametrize(
    "pref, inicio, esperado",
    [
        (None, LUNES_9, True),                        # sin preferencia = ok
        ({}, LUNES_9, True),                          # vacía = ok
        ({"dias": ["lunes"], "desde": "09:00", "hasta": "13:00"}, LUNES_9, True),
        ({"dias": ["martes"], "desde": "09:00", "hasta": "13:00"}, LUNES_9, False),  # día equivocado
        ({"dias": ["lunes"], "desde": "08:00", "hasta": "09:00"}, LUNES_9, False),   # fuera de franja
        ({"dias": ["lunes"], "desde": "09:00", "hasta": "13:00"}, MARTES_9, False),  # otro día
    ],
)
def test_cumple_preferencia(pref, inicio, esperado):
    """Task 1.3 RED: preferencia_horaria filtra día/franja del inicio."""
    assert _cumple_preferencia(pref, inicio) is esperado


def test_preferencia_se_evalua_en_hora_local_buenos_aires():
    """Los turnos viven en UTC en DB; la franja del paciente es hora local BA (UTC-3)."""
    pref = {"dias": ["lunes"], "desde": "09:00", "hasta": "13:00"}
    nueve_ba = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)   # 09:00 BA
    seis_ba = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)     # 06:00 BA
    domingo_noche_ba = datetime(2026, 10, 12, 1, 0, tzinfo=timezone.utc)  # dom 11/10 22:00 BA (lunes en UTC)

    assert _cumple_preferencia(pref, nueve_ba) is True
    assert _cumple_preferencia(pref, seis_ba) is False
    assert _cumple_preferencia({"dias": ["domingo"]}, domingo_noche_ba) is True


# --- activas_compatibles con sesión mockeada ---------------------------------

@pytest.mark.asyncio
async def test_matching_fifo_primero_compatible():
    """Task 1.3 RED: 3 activas, la 1a incompatible por franja -> elige la 2a."""
    from app.repos.espera_repo import EsperaRepository

    entradas_ns = [
        type("E", (), _fabricar_entrada(
            1,
            profesional_id=1,
            especialidad="Odontología general",
            preferencia_horaria={"dias": ["martes"], "desde": "09:00", "hasta": "13:00"},
            created_at=LUNES_9,
        ))(),
        type("E", (), _fabricar_entrada(
            2,
            profesional_id=1,
            especialidad="Odontología general",
            preferencia_horaria=None,
            created_at=LUNES_9 + timedelta(minutes=1),
        ))(),
        type("E", (), _fabricar_entrada(
            3,
            profesional_id=1,
            especialidad="Odontología general",
            preferencia_horaria=None,
            created_at=LUNES_9 + timedelta(minutes=2),
        ))(),
    ]

    sesion = AsyncMock()
    resultado = MagicMock()
    resultado.scalars.return_value.all.return_value = entradas_ns
    sesion.execute.return_value = resultado

    repo = EsperaRepository(sesion)
    compatibles = await repo.activas_compatibles(
        profesional_id=1,
        especialidades_profesional="Odontología general",
        inicio=LUNES_9,
    )
    assert len(compatibles) == 2
    assert compatibles[0].id == 2  # la 2a (la 1a excluida por franja martes)
    assert compatibles[1].id == 3


@pytest.mark.asyncio
async def test_matching_sin_preferencia_acepta_todo():
    """Task 1.3 RED: preferencia NULL o {} acepta cualquier hueco."""
    from app.repos.espera_repo import EsperaRepository

    entradas_ns = [
        type("E", (), _fabricar_entrada(
            1, profesional_id=None, especialidad=None,
            preferencia_horaria=None, created_at=LUNES_9,
        ))(),
        type("E", (), _fabricar_entrada(
            2, profesional_id=None, especialidad=None,
            preferencia_horaria={}, created_at=LUNES_9 + timedelta(minutes=1),
        ))(),
    ]
    sesion = AsyncMock()
    resultado = MagicMock()
    resultado.scalars.return_value.all.return_value = entradas_ns
    sesion.execute.return_value = resultado

    repo = EsperaRepository(sesion)
    compatibles = await repo.activas_compatibles(
        profesional_id=1,
        especialidades_profesional="Odontología general",
        inicio=LUNES_9,
    )
    assert len(compatibles) == 2
    assert compatibles[0].id == 1
    assert compatibles[1].id == 2


@pytest.mark.asyncio
async def test_matching_filtra_por_profesional():
    """Task 1.3 RED: entry de otro profesional no es compatible."""
    from app.repos.espera_repo import EsperaRepository

    entradas_ns = [
        type("E", (), _fabricar_entrada(1, profesional_id=1, created_at=LUNES_9))(),
        type("E", (), _fabricar_entrada(2, profesional_id=99, created_at=LUNES_9 + timedelta(minutes=1)))(),
    ]
    sesion = AsyncMock()
    resultado = MagicMock()
    resultado.scalars.return_value.all.return_value = entradas_ns
    sesion.execute.return_value = resultado

    repo = EsperaRepository(sesion)
    compatibles = await repo.activas_compatibles(
        profesional_id=1,
        especialidades_profesional="Odontología general",
        inicio=LUNES_9,
    )
    assert len(compatibles) == 1
    assert compatibles[0].id == 1


@pytest.mark.asyncio
async def test_matching_solo_activas():
    """Task 1.3 RED: ofrecida/convertida/vencida no se ofrecen."""
    from app.repos.espera_repo import EsperaRepository

    entradas_ns = [
        type("E", (), _fabricar_entrada(1, estado="ofrecida", created_at=LUNES_9))(),
        type("E", (), _fabricar_entrada(2, estado="activa", created_at=LUNES_9 + timedelta(minutes=1)))(),
        type("E", (), _fabricar_entrada(3, estado="vencida", created_at=LUNES_9 + timedelta(minutes=2)))(),
    ]
    sesion = AsyncMock()
    resultado = MagicMock()
    resultado.scalars.return_value.all.return_value = entradas_ns
    sesion.execute.return_value = resultado

    repo = EsperaRepository(sesion)
    compatibles = await repo.activas_compatibles(
        profesional_id=1,
        especialidades_profesional="Odontología general",
        inicio=LUNES_9,
    )
    assert len(compatibles) == 1
    assert compatibles[0].id == 2


@pytest.mark.asyncio
async def test_matching_orden_fifo_desempata_por_id_en_sql():
    """created_at default now() es hora de TRANSACCION: dos altas juntas empatan; el id desempata."""
    from sqlalchemy.dialects import postgresql

    from app.repos.espera_repo import EsperaRepository

    sesion = AsyncMock()
    resultado = MagicMock()
    resultado.scalars.return_value.all.return_value = []
    sesion.execute.return_value = resultado
    repo = EsperaRepository(sesion)

    await repo.activas_compatibles(profesional_id=1, especialidades_profesional="x", inicio=LUNES_9)
    await repo.listar_fifo()

    for llamada in sesion.execute.await_args_list:
        sql = str(llamada.args[0].compile(dialect=postgresql.dialect())).replace("\n", " ")
        assert "ORDER BY espera_entry.created_at ASC, espera_entry.id ASC" in sql
