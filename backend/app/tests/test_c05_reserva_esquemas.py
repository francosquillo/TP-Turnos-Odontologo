"""C-05 task 2.1: esquemas reserva estrictos (RED -> GREEN sin PG)."""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _valida(**cambios) -> dict:
    datos = {
        "profesional_id": 1,
        "sillon_id": 1,
        "inicio": "2026-10-12T12:00:00+00:00",
        "fin": "2026-10-12T12:30:00+00:00",
        "nombre": "Ana Ficticia",
        "telefono": "11 5000-2222",
    }
    datos.update(cambios)
    return datos


def test_reserva_in_rechaza_campo_extra():
    """Task 2.1 RED: campo extra -> ValidationError (422 en el router)."""
    from app.esquemas.reserva import ReservaIn

    with pytest.raises(ValidationError):
        ReservaIn(**_valida(campo_fantasma=1))


def test_reserva_in_nombre_corto_422():
    """Task 2.1 RED: nombre de 1 caracter -> ValidationError."""
    from app.esquemas.reserva import ReservaIn

    with pytest.raises(ValidationError):
        ReservaIn(**_valida(nombre="A"))


def test_reserva_out_solo_token_en_creacion():
    """Triangulacion: ReservaOut lleva token plano una unica vez (201)."""
    from app.esquemas.reserva import ReservaIn, ReservaOut

    entrada = ReservaIn(**_valida())
    assert entrada.telefono == "11 5000-2222"  # sin normalizar en esquema
    salida = ReservaOut(
        turno_id=5, estado="pendiente", token="plano-demo",
        expira_en="2026-10-04T12:00:00+00:00",
    )
    assert salida.estado == "pendiente"
    with pytest.raises(ValidationError):
        ReservaOut(
            turno_id=5, estado="confirmado", token="x",
            expira_en="2026-10-04T12:00:00+00:00",
        )
