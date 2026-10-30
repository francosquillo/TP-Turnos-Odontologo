"""C-07 grupo 1: migración 004_espera encadenada a 003_notificacion (D-08).

RED primero: si 004_espera.py no existe o down_revision no apunta a 003,
el test falla. Luego GREEN con alembic/versions/004_espera.py.
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]  # backend/app/tests -> backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"  # backend/alembic


def test_c07_migracion_head_encadena_003():
    """Task 1.2 RED: 004_espera está en la cadena sobre 003_notificacion y la cabeza es única.

    Solo lee los scripts de alembic (no toca la DB): corre siempre, sin Docker.
    C-08 agrega 005_clinica encima: la cabeza deja de ser 004_espera (C-08, D-01).
    """
    from alembic.script import ScriptDirectory

    script = ScriptDirectory(str(ALEMBIC_DIR))
    cabezas = script.get_heads()
    assert len(cabezas) == 1, f"esperada 1 cabeza, encontradas: {cabezas}"
    cadena = [r.revision for r in script.walk_revisions()]  # de la cabeza hacia la base
    assert "004_espera" in cadena and "003_notificacion" in cadena
    assert cadena.index("004_espera") < cadena.index("003_notificacion")
    assert script.get_revision("004_espera").down_revision == "003_notificacion"


def test_c07_migracion_declara_los_mismos_checks_e_indices_que_el_modelo():
    """La migración y el modelo no pueden divergir (los tests PG usan el modelo, prod la migración)."""
    from app.modelos import EsperaEntry

    texto = (ALEMBIC_DIR / "versions" / "004_espera.py").read_text(encoding="utf-8")
    nombres_modelo = {c.name for c in EsperaEntry.__table__.constraints if c.name}
    indices_modelo = {i.name for i in EsperaEntry.__table__.indexes}
    assert nombres_modelo >= {"ck_espera_destino_presente", "ck_espera_ofrecida_exige_vencimiento", "ck_espera_estado_catalogo"}
    for nombre in nombres_modelo | indices_modelo:
        assert nombre in texto, f"{nombre} está en el modelo pero no en 004_espera.py"
    assert "downgrade" in texto and "DROP TABLE IF EXISTS espera_entry" in texto
