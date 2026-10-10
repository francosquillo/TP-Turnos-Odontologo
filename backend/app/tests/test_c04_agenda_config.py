"""C-04 task 6.1: formato demo de agenda_config fijado (reutilizable por C-05).

Canonico C-02: {duracion_slot_min, horario: {dia_es: [[ini, fin]]}},
TZ America/Argentina/Buenos_Aires. El servicio lo parsea sin reinterpretar.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_agenda_config_demo_parsea():
    """Task 6.1: seed demo valida y da 16 huecos el lunes (fijado para C-05)."""
    from app.db.seed import AGENDA_DEMO
    from app.esquemas.profesional import AgendaConfig
    from app.servicios.agenda_servicio import calcular_huecos

    agenda = AgendaConfig.model_validate(AGENDA_DEMO)
    assert agenda.duracion_slot_min == 30
    assert any(franjas for franjas in agenda.horario.values())
    assert set(agenda.horario) <= {
        "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo",
    }
    lunes = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)
    huecos = calcular_huecos(
        dict(AGENDA_DEMO), lunes, lunes + timedelta(days=1), [], None
    )
    # Lunes demo 09-13 + 14-18 en BA = 8 h = 16 slots de 30 min.
    assert len(huecos) == 16
    assert huecos[0][0].strftime("%H:%M") == "09:00"
    assert str(huecos[0][0].tzinfo) == "America/Argentina/Buenos_Aires"
