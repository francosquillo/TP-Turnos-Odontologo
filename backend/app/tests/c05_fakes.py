"""Fakes C-05: paciente por telefono + turno por hash (extiende c04_fakes).

Sin PG: los tests de servicio usan estos fakes. Los tests contra PG real
viven en test_c05_reserva_pg.py y skipean sin Docker (compose down).
"""
import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c04_fakes import FakeTurnoRepo  # noqa: E402


class FakePacienteRepo:
    """PacienteRepository en memoria con match por telefono normalizado."""

    def __init__(self, pacientes: list | None = None) -> None:
        self._pacientes: dict[int, SimpleNamespace] = {}
        self._seq = 0
        for paciente in pacientes or []:
            self._seq = max(self._seq, paciente.id)
            self._pacientes[paciente.id] = paciente

    async def get(self, id: int):
        return self._pacientes.get(id)

    async def por_telefono(self, telefono_norm: str):
        for paciente in self._pacientes.values():
            if getattr(paciente, "deleted_at", None) is not None:
                continue
            if getattr(paciente, "telefono", None) == telefono_norm:
                return paciente
        return None

    async def crear(self, **datos):
        self._seq += 1
        paciente = SimpleNamespace(id=self._seq, **datos)
        paciente.__dict__.setdefault("deleted_at", None)
        self._pacientes[paciente.id] = paciente
        return paciente

    def cantidad(self) -> int:
        return len(self._pacientes)


class FakeTurnoRepoC05(FakeTurnoRepo):
    """FakeTurnoRepo + busqueda por hash de token (confirmar, D-01)."""

    async def por_token_hash(self, token_hash: str):
        for turno in self._turnos.values():
            if getattr(turno, "token_confirmacion_hash", None) == token_hash:
                return turno
        return None


def fabricar_paciente(id: int = 1, **cambios) -> SimpleNamespace:
    datos = {
        "id": id,
        "nombre": "Paciente",
        "apellido": "Demo",
        "dni": None,
        "telefono": "1140001111",
        "email": None,
        "deleted_at": None,
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)
