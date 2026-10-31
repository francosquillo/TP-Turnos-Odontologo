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
from app.modelos.notificacion import Notificacion, Plantilla  # noqa: E402
from app.modelos.espera_entry import EsperaEntry  # noqa: E402
from app.modelos.historia_clinica import HistoriaClinica  # noqa: E402
from app.modelos.hallazgo_odontograma import (  # noqa: E402
    EstadoHallazgoCatalogo,
    HallazgoOdontograma,
)
from app.modelos.tratamiento import Tratamiento  # noqa: E402
from app.modelos.presupuesto import ItemPresupuesto, Presupuesto  # noqa: E402
from app.modelos.cuenta_corriente import CuentaCorriente, Movimiento  # noqa: E402
from app.modelos.caja import Caja, MovimientoCaja, Recibo, ReciboContador  # noqa: E402

__all__ = ["Caja", "MovimientoCaja", "Recibo", "ReciboContador", "ItemPresupuesto", "Presupuesto", "CuentaCorriente", "Movimiento","Base", "Paciente", "Profesional", "Rol", "Sillon", "Turno", "Usuario", "Notificacion", "Plantilla", "EsperaEntry", "HistoriaClinica", "EstadoHallazgoCatalogo", "HallazgoOdontograma", "Tratamiento"]
