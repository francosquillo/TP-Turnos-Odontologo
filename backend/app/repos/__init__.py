"""Repos C-02: base generica + finos por entidad (D-02)."""
from app.repos.base import BaseRepository
from app.repos.paciente_repo import PacienteRepository
from app.repos.profesional_repo import ProfesionalRepository
from app.repos.rol_repo import RolRepository
from app.repos.sillon_repo import SillonRepository
from app.repos.turno_repo import TurnoRepository
from app.repos.usuario_repo import UsuarioRepository

__all__ = [
    "BaseRepository",
    "RolRepository",
    "UsuarioRepository",
    "PacienteRepository",
    "ProfesionalRepository",
    "SillonRepository",
    "TurnoRepository",
]
