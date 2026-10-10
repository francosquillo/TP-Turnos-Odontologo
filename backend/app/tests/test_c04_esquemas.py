"""C-04 task 3.1: esquemas Turno estrictos (extra='forbid', fin>inicio)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

BASE = datetime(2026, 10, 12, 8, 0, tzinfo=timezone.utc)


def _valido(**cambios) -> dict:
    datos = {
        "paciente_id": 1,
        "profesional_id": 1,
        "sillon_id": 1,
        "inicio": BASE,
        "fin": BASE + timedelta(minutes=30),
    }
    datos.update(cambios)
    return datos


def test_turno_in_rechaza_campo_extra():
    """Task 3.1 RED: campo extra -> 422 (extra='forbid')."""
    from app.esquemas.turno import TurnoIn

    with pytest.raises(ValidationError):
        TurnoIn.model_validate(_valido(token_confirmacion_hash="plano-prohibido"))


def test_turno_in_exige_fin_mayor_inicio():
    """Triangulacion: fin<=inicio -> 422 en esquema y reprogramacion."""
    from app.esquemas.turno import ReprogramarIn, TurnoIn

    with pytest.raises(ValidationError):
        TurnoIn.model_validate(_valido(fin=BASE))
    with pytest.raises(ValidationError):
        ReprogramarIn.model_validate({"inicio": BASE, "fin": BASE})


def test_turno_out_oculta_token_y_estado_patch_lleva_motivo():
    """Triangulacion: TurnoOut sin token; EstadoPatch acepta motivo."""
    from app.esquemas.turno import EstadoPatch, TurnoOut

    out = TurnoOut.model_validate(
        {
            "id": 1,
            "paciente_id": 1,
            "profesional_id": 1,
            "sillon_id": 1,
            "inicio": BASE,
            "fin": BASE + timedelta(minutes=30),
            "estado": "confirmado",
            "origen": "secretaria",
            "sobre_turno": False,
            "motivo_sobreturno": None,
            "motivo_cancelacion": None,
            "creado_por": 7,
            "created_at": BASE,
        }
    )
    assert "token" not in out.model_dump()
    patch = EstadoPatch.model_validate({"estado": "cancelado", "motivo": "aviso"})
    assert patch.motivo == "aviso"
    with pytest.raises(ValidationError):
        EstadoPatch.model_validate({"estado": "reprogramado"})
