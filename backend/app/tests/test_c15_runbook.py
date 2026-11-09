"""C-15 task 5.1: runbook de despliegue en Easypanel (docs/deploy-vps.md)."""
from pathlib import Path

import pytest

RUNBOOK = Path(__file__).resolve().parents[3] / "docs" / "deploy-vps.md"


def _texto() -> str:
    assert RUNBOOK.exists(), f"falta {RUNBOOK}"
    return RUNBOOK.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "termino",
    [
        "compose.prod.yml", "Create .env file", "api.", "8000", "8080", "pg_dump", "pg_restore",
        "ficticios", ".env.prod.example", "migrate", "openssl rand -hex 32", "DNS",
    ],
)
def test_runbook_menciona(termino):
    assert termino in _texto()


def test_runbook_aclara_convivencia_y_sin_puertos():
    texto = _texto().lower()
    assert "container_name" in texto
    assert "puertos" in texto
    assert "calculadora" in texto


def test_runbook_incluye_supuestos_a_confirmar():
    texto = _texto()
    for s in ("S-1", "S-2", "S-3", "S-4", "S-5"):
        assert s in texto


def test_runbook_sin_secretos_reales():
    import re

    assert not re.search(r"\b[0-9a-f]{64}\b", _texto())
