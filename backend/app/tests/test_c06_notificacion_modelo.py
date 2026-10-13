"""C-06 tasks 1.1/1.2 RED: modelo Notificacion + migracion 003 (D-01, D-08).

Unit (siempre corre): metadata trae notificacion con CHECKs, indices y UNIQUE
parcial; archivo 003 existe y encadena 002_turno (D-08: C-08 aun no creo 003_*).
PG-gated (skipea sin Docker): CHECK rechaza canal invalido; UNIQUE parcial
permite reintento tras fallida y rechaza duplicada activa; heads unico.
Datos 100% ficticios. NUNCA PHI (ni siquiera telefonos reales en tests).
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

REPO_ROOT = Path(__file__).resolve().parents[3]
VERSIONS_DIR = REPO_ROOT / "backend" / "alembic" / "versions"

from db_utils import sesion_pg  # noqa: E402, F401


def test_notificacion_registrada_con_checks_e_indices():
    """Task 1.1 RED: tabla notificacion con CHECKs canal/plantilla/estado."""
    from app.modelos import Base, Notificacion

    assert "notificacion" in Base.metadata.tables
    assert issubclass(Notificacion, Base)
    assert Notificacion.__tablename__ == "notificacion"
    tabla = Base.metadata.tables["notificacion"]
    for columna in (
        "turno_id", "canal", "plantilla", "estado", "costo",
        "payload", "intentos", "ultimo_error",
    ):
        assert columna in tabla.c, f"notificacion sin columna {columna}"
    checks = " ".join(
        str(c.sqltext) for c in tabla.constraints
        if c.__class__.__name__ == "CheckConstraint"
    )
    assert "whatsapp" in checks and "paloma" not in checks
    assert "recordatorio_48h" in checks
    assert "encolada" in checks and "fallida" in checks
    assert tabla.c.costo.nullable is True
    assert tabla.c.payload.nullable is False


def test_notificacion_unique_parcial_solo_activas():
    """Task 1.1 RED: UNIQUE (turno_id, plantilla) WHERE estado != fallida."""
    from app.modelos import Base

    tabla = Base.metadata.tables["notificacion"]
    parciales = [
        i for i in tabla.indexes
        if i.unique and set(i.columns.keys()) == {"turno_id", "plantilla"}
    ]
    assert len(parciales) == 1, "falta UNIQUE parcial (turno_id, plantilla)"
    condicion = str(parciales[0].dialect_options["postgresql"]["where"])
    assert "fallida" in condicion
    nombres = {i.name for i in tabla.indexes}
    assert "ix_notificacion_turno" in nombres
    assert "ix_notificacion_estado" in nombres


def test_notificacion_cuerpo_no_persiste():
    """Task 1.4 RED (D-01): sin columna cuerpo; payload guarda variables."""
    from app.modelos import Base

    tabla = Base.metadata.tables["notificacion"]
    assert "cuerpo" not in tabla.c, "el cuerpo renderizado NUNCA se persiste"


def test_migracion_003_existe_y_encadena_002():
    """Task 1.2 RED: 003_notificacion existe con down_revision 002_turno (D-08)."""
    candidatos = list(VERSIONS_DIR.glob("*003*.py"))
    assert len(candidatos) == 1, f"se esperaba un unico 003_*, hay {candidatos}"
    src = candidatos[0].read_text(encoding="utf-8")
    assert "def upgrade" in src and "def downgrade" in src
    assert "002_turno" in src
    assert "notificacion" in src
    assert "EXCLUDE" not in src  # este change no toca anti-solapamiento


def test_c06_migracion_head_encadena_002():
    """Task 1.2 RED (unit): cadena unica 001 -> 002 -> 003 sin cabezas dobles."""
    import re

    revisiones: dict[str, str | None] = {}
    for archivo in VERSIONS_DIR.glob("*.py"):
        if archivo.name.startswith("__"):
            continue
        texto = archivo.read_text(encoding="utf-8")
        rev = re.search(r"^revision:\s*str\s*=\s*[\"']([^\"']+)", texto, re.M)
        down = re.search(r"^down_revision[^=]*=\s*[\"']([^\"']+)", texto, re.M)
        assert rev, f"{archivo.name} sin revision"
        revisiones[rev.group(1)] = down.group(1) if down else None
    apuntadas = {d for d in revisiones.values() if d}
    cabezas = [r for r in revisiones if r not in apuntadas]
    assert len(cabezas) == 1, f"se esperaba una sola cabeza, hay {cabezas}"
    assert "002_turno" in revisiones, "la cadena debe incluir 002_turno"


@pytest.mark.asyncio
async def test_notificacion_canal_invalido_422(sesion_pg):
    """Task 1.1 GREEN (PG real): CHECK rechaza canal paloma_mensajera."""
    from sqlalchemy.exc import IntegrityError

    from app.modelos import Paciente, Profesional, Sillon
    from app.repos.notificacion_repo import NotificacionRepository

    paciente = Paciente(nombre="Ficticia", apellido="Canal", consentimiento_datos=True)
    profesional = Profesional(matricula="C06-M1")
    sillon = Sillon(nombre="Sillón C06-M1")
    sesion_pg.add_all([paciente, profesional, sillon])
    await sesion_pg.flush()
    from datetime import datetime, timedelta, timezone

    from app.modelos import Turno

    ahora = datetime.now(timezone.utc)
    sesion_pg.add(
        Turno(
            paciente_id=paciente.id, profesional_id=profesional.id,
            sillon_id=sillon.id, inicio=ahora + timedelta(days=2),
            fin=ahora + timedelta(days=2, minutes=30),
        )
    )
    await sesion_pg.flush()
    turno_id = (await sesion_pg.execute(
        __import__("sqlalchemy").select(Turno.id)
    )).scalars().first()
    repo = NotificacionRepository(sesion_pg)
    with pytest.raises(IntegrityError):
        await repo.crear(
            turno_id=turno_id, canal="paloma_mensajera",
            plantilla="recordatorio_48h", payload={"nombre_pila": "Ficticia"},
        )
    await sesion_pg.rollback()


@pytest.mark.asyncio
async def test_notificacion_unique_parcial_permite_reintento_tras_fallida(sesion_pg):
    """Task 1.1 GREEN (PG real): 2da fila ok si la 1ra es fallida; IntegrityError si encolada."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from app.modelos import Paciente, Profesional, Sillon, Turno
    from app.repos.notificacion_repo import NotificacionRepository

    paciente = Paciente(nombre="Ficticia", apellido="Unica", consentimiento_datos=True)
    profesional = Profesional(matricula="C06-M2")
    sillon = Sillon(nombre="Sillón C06-M2")
    sesion_pg.add_all([paciente, profesional, sillon])
    await sesion_pg.flush()
    ahora = datetime.now(timezone.utc)
    sesion_pg.add(
        Turno(
            paciente_id=paciente.id, profesional_id=profesional.id,
            sillon_id=sillon.id, inicio=ahora + timedelta(days=2),
            fin=ahora + timedelta(days=2, minutes=30),
        )
    )
    await sesion_pg.flush()
    turno_id = (await sesion_pg.execute(select(Turno.id))).scalars().first()
    repo = NotificacionRepository(sesion_pg)
    # Primera fallida + segunda encolada: permitido (reintento).
    await repo.crear(
        turno_id=turno_id, canal="whatsapp", plantilla="recordatorio_48h",
        estado="fallida", payload={"nombre_pila": "Ficticia"},
        ultimo_error="sin_numero_valido",
    )
    segunda = await repo.crear(
        turno_id=turno_id, canal="whatsapp", plantilla="recordatorio_48h",
        payload={"nombre_pila": "Ficticia"},
    )
    assert segunda.estado == "encolada"
    # Tercera con una activa: rechazada por el UNIQUE parcial.
    with pytest.raises(IntegrityError):
        await repo.crear(
            turno_id=turno_id, canal="whatsapp", plantilla="recordatorio_48h",
            payload={"nombre_pila": "Ficticia"},
        )
    await sesion_pg.rollback()
