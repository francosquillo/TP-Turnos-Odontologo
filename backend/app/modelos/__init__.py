"""C-02: Base declarativa + entidades (D-05: tipos Postgres estrictos).

PK BIGINT GENERATED ALWAYS AS IDENTITY (serial prohibido), TIMESTAMPTZ,
TEXT+CHECK, BOOLEAN NOT NULL, snake_case sin comillas.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa unica: target_metadata de Alembic (D-01)."""


from app.modelos.paciente import Paciente  # noqa: E402
from app.modelos.profesional import Profesional  # noqa: E402
from app.modelos.rol import Rol  # noqa: E402
from app.modelos.sillon import Sillon  # noqa: E402
from app.modelos.turno import Turno  # noqa: E402
from app.modelos.usuario import Usuario  # noqa: E402

__all__ = ["Base", "Paciente", "Profesional", "Rol", "Sillon", "Turno", "Usuario"]
