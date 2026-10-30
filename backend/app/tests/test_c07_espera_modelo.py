"""C-07 grupo 1: modelo EsperaEntry + CHECKs + índices (D-01).

RED primero: modulo inexistente -> ImportError. Luego GREEN con
modelos/espera_entry.py. Tests contra PG real via sesion_pg (skipea sin Docker).
Datos 100% ficticios. TZ America/Argentina/Buenos_Aires.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]  # backend/app/tests -> backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: E402, F401

AHORA = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


async def _insertar_entrada(sesion, **datos):
    from app.modelos import EsperaEntry
    entrada = EsperaEntry(**datos)
    sesion.add(entrada)
    await sesion.flush()  # sin flush el CHECK de PG no se evalúa
    return entrada


# --- 1.1 CHECK: estado invalido rechaza --------------------------------------

@pytest.mark.asyncio
async def test_espera_estado_invalido_422(sesion_pg):
    """Task 1.1 RED: CHECK estado rechaza 'dormida' (PG real, nunca SQLite)."""
    from sqlalchemy.exc import IntegrityError
    from app.modelos import EsperaEntry, Paciente, Profesional

    sesion_pg.add_all([
        Paciente(nombre="Ana Ficticia", apellido="Demo", telefono="1140001111"),
        Profesional(matricula="DEMO-0001", especialidades="Odontología general"),
    ])
    await sesion_pg.flush()
    paciente = await sesion_pg.scalar(
        __import__("sqlalchemy").select(Paciente).where(Paciente.nombre == "Ana Ficticia")
    )
    profesional = await sesion_pg.scalar(
        __import__("sqlalchemy").select(Profesional).where(Profesional.matricula == "DEMO-0001")
    )
    with pytest.raises(IntegrityError):
        await _insertar_entrada(
            sesion_pg,
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            estado="dormida",
        )
    await sesion_pg.rollback()


# --- 1.1 CHECK: sin destino rechaza ------------------------------------------

@pytest.mark.asyncio
async def test_espera_sin_destino_422(sesion_pg):
    """Task 1.1 RED: CHECK profesional_id O especialidad (ambos NULL -> rechaza)."""
    from sqlalchemy.exc import IntegrityError
    from app.modelos import EsperaEntry, Paciente

    sesion_pg.add(Paciente(nombre="Ana Ficticia", apellido="Demo", telefono="1140001111"))
    await sesion_pg.flush()
    paciente = await sesion_pg.scalar(
        __import__("sqlalchemy").select(Paciente).where(Paciente.nombre == "Ana Ficticia")
    )
    with pytest.raises(IntegrityError):
        await _insertar_entrada(
            sesion_pg,
            paciente_id=paciente.id,
            profesional_id=None,
            especialidad=None,
        )
    await sesion_pg.rollback()


# --- 1.1 CHECK: ofrecida exige expira_en + hash ------------------------------

@pytest.mark.asyncio
async def test_espera_ofrecida_exige_vencimiento_422(sesion_pg):
    """Task 1.1 RED: CHECK estado='ofrecida' exige oferta_expira_en + token_hash."""
    from sqlalchemy.exc import IntegrityError
    from app.modelos import EsperaEntry, Paciente, Profesional

    sesion_pg.add_all([
        Paciente(nombre="Ana Ficticia", apellido="Demo", telefono="1140001111"),
        Profesional(matricula="DEMO-0001", especialidades="Odontología general"),
    ])
    await sesion_pg.flush()
    paciente = await sesion_pg.scalar(
        __import__("sqlalchemy").select(Paciente).where(Paciente.nombre == "Ana Ficticia")
    )
    profesional = await sesion_pg.scalar(
        __import__("sqlalchemy").select(Profesional).where(Profesional.matricula == "DEMO-0001")
    )
    with pytest.raises(IntegrityError):
        await _insertar_entrada(
            sesion_pg,
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            estado="ofrecida",
            # oferta_expira_en y token_oferta_hash NULL -> CHECK falla
        )
    await sesion_pg.rollback()


# --- 1.1 GREEN: entrada valida se persiste -----------------------------------

@pytest.mark.asyncio
async def test_espera_entrada_valida_persiste(sesion_pg):
    """Task 1.1 GREEN: entrada activa con profesional + expira en ofrece ok."""
    from app.modelos import EsperaEntry, Paciente, Profesional

    sesion_pg.add_all([
        Paciente(nombre="Ana Ficticia", apellido="Demo", telefono="1140001111"),
        Profesional(matricula="DEMO-0001", especialidades="Odontología general"),
    ])
    await sesion_pg.flush()
    paciente = await sesion_pg.scalar(
        __import__("sqlalchemy").select(Paciente).where(Paciente.nombre == "Ana Ficticia")
    )
    profesional = await sesion_pg.scalar(
        __import__("sqlalchemy").select(Profesional).where(Profesional.matricula == "DEMO-0001")
    )
    entrada = await _insertar_entrada(
        sesion_pg,
        paciente_id=paciente.id,
        profesional_id=profesional.id,
        estado="activa",
        especialidad="Odontología general",
        oferta_expira_en=AHORA + timedelta(hours=2),
        token_oferta_hash="hash-demo",
    )
    await sesion_pg.commit()
    assert entrada.id is not None
    assert entrada.estado == "activa"
    await sesion_pg.rollback()
