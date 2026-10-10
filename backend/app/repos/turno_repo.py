"""Repo Turno: consultas por profesional/sillon/rango para agenda (C-04, D-04).

Solo turnos activos no-sobreturno bloquean huecos (mismo predicado que el
EXCLUDE, D-01); el repo nunca decide: expone lecturas y el servicio valida.
"""
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import Turno
from app.repos.base import BaseRepository

ESTADOS_ACTIVOS = ("pendiente", "confirmado", "asistido")


class TurnoRepository(BaseRepository[Turno]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Turno)

    def _condicion_activos(self):
        return and_(
            Turno.sobre_turno.is_(False),
            Turno.estado.in_(ESTADOS_ACTIVOS),
        )

    async def activos_en_rango(
        self,
        desde: datetime,
        hasta: datetime,
        profesional_id: int | None = None,
        sillon_id: int | None = None,
        excluir_id: int | None = None,
    ) -> list[Turno]:
        """Turnos activos que pisan [desde, hasta), ordenados por inicio."""
        condiciones = [
            self._condicion_activos(),
            Turno.inicio < hasta,
            Turno.fin > desde,
        ]
        if profesional_id is not None:
            condiciones.append(Turno.profesional_id == profesional_id)
        if sillon_id is not None:
            condiciones.append(Turno.sillon_id == sillon_id)
        if excluir_id is not None:
            condiciones.append(Turno.id != excluir_id)
        filas = await self.sesion.execute(
            select(Turno).where(*condiciones).order_by(Turno.inicio)
        )
        return list(filas.scalars().all())

    async def hay_solapamiento(
        self,
        profesional_id: int,
        sillon_id: int,
        inicio: datetime,
        fin: datetime,
        excluir_id: int | None = None,
    ) -> bool:
        """True si algun activo no-sobreturno choca por profesional o sillon."""
        condiciones = [
            self._condicion_activos(),
            Turno.inicio < fin,
            Turno.fin > inicio,
            or_(
                Turno.profesional_id == profesional_id,
                Turno.sillon_id == sillon_id,
            ),
        ]
        if excluir_id is not None:
            condiciones.append(Turno.id != excluir_id)
        return (
            await self.sesion.scalar(select(Turno.id).where(*condiciones).limit(1))
        ) is not None

    async def por_token_hash(self, token_hash: str):
        """Turno con ese hash de confirmacion (C-05, D-01; None si no hay)."""
        return await self.sesion.scalar(
            select(Turno).where(Turno.token_confirmacion_hash == token_hash).limit(1)
        )

    async def listar_periodo(
        self,
        desde: datetime,
        hasta: datetime,
        profesional_id: int | None = None,
        sillon_id: int | None = None,
        solo_activos: bool = True,
    ) -> list[Turno]:
        """Turnos del periodo para vistas de agenda (incluye cancelados si se pide)."""
        condiciones = [Turno.inicio < hasta, Turno.fin > desde]
        if solo_activos:
            condiciones.append(self._condicion_activos())
        if profesional_id is not None:
            condiciones.append(Turno.profesional_id == profesional_id)
        if sillon_id is not None:
            condiciones.append(Turno.sillon_id == sillon_id)
        filas = await self.sesion.execute(
            select(Turno).where(*condiciones).order_by(Turno.inicio)
        )
        return list(filas.scalars().all())
