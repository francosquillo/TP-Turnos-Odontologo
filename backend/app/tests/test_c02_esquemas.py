"""C-02 tasks 2.2 + 4.2 (+ AgendaConfig 4.1): esquemas Pydantic estrictos.

Puros unitarios: corren siempre (sin DB).
"""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_esquema_usuario_rechaza_campo_extra():
    """Task 2.2 GREEN: campo extra -> ValidationError (extra='forbid')."""
    from app.esquemas.usuario import UsuarioCreate

    with pytest.raises(ValidationError):
        UsuarioCreate(
            nombre="Admin",
            email="admin@demo.test",
            password="secreto123",
            rol_id=1,
            campo_extra="no permitido",
        )


def test_esquema_usuario_response_sin_password_hash():
    """Task 2.2 GREEN: el response nunca expone password_hash."""
    from app.esquemas.usuario import UsuarioResponse

    assert "password_hash" not in UsuarioResponse.model_fields
    with pytest.raises(ValidationError):
        UsuarioResponse(
            id=1,
            nombre="Admin",
            email="admin@demo.test",
            rol_id=1,
            activo=True,
            password_hash="no debe aceptarse",
        )


def test_esquemas_paciente_profesional_sillon_rechazan_extra():
    """Task 4.2 GREEN: rechazo de campo extra por esquema."""
    from app.esquemas.paciente import PacienteCreate
    from app.esquemas.profesional import ProfesionalCreate
    from app.esquemas.sillon import SillonCreate

    with pytest.raises(ValidationError):
        PacienteCreate(
            nombre="Juan",
            apellido="Demo",
            consentimiento_datos=True,
            campo_extra=1,
        )
    with pytest.raises(ValidationError):
        ProfesionalCreate(
            matricula="DEMO-1",
            especialidades="General",
            campo_extra=1,
        )
    with pytest.raises(ValidationError):
        SillonCreate(nombre="Sillon 1", campo_extra=1)


def test_agenda_config_valida_ok():
    """Task 4.1 GREEN: agenda semanal valida pasa el esquema."""
    from app.esquemas.profesional import AgendaConfig

    agenda = AgendaConfig(
        duracion_slot_min=30,
        horario={"lunes": [["09:00", "13:00"], ["14:00", "18:00"]]},
    )
    assert agenda.duracion_slot_min == 30


def test_agenda_config_invalida_rechazada():
    """Spec: agenda sin duracion o con franja fin<=inicio falla antes de persistir."""
    from app.esquemas.profesional import AgendaConfig

    with pytest.raises(ValidationError):
        AgendaConfig(duracion_slot_min=0, horario={"lunes": [["09:00", "13:00"]]})
    with pytest.raises(ValidationError):
        AgendaConfig(duracion_slot_min=30, horario={"lunes": [["13:00", "09:00"]]})
    with pytest.raises(ValidationError):
        AgendaConfig(duracion_slot_min=30, horario={})
