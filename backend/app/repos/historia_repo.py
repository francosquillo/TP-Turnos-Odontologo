"""Repo HistoriaClinica: activa vs dada de baja (C-08, D-06).

`activa_por_id` oculta las bajas (la API responde 404); `por_paciente` las
devuelve para distinguir el 409 "dada de baja" de "no existe". La baja nunca
borra la fila ni toca los hallazgos.
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import HistoriaClinica
from app.repos.base import BaseRepository


class HistoriaRepository(BaseRepository[HistoriaClinica]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, HistoriaClinica)

    async def activa_por_id(self, hc_id: int) -> HistoriaClinica | None:
        return await self.sesion.scalar(
            select(HistoriaClinica).where(
                HistoriaClinica.id == hc_id, HistoriaClinica.deleted_at.is_(None)
            )
        )

    async def por_paciente(self, paciente_id: int) -> HistoriaClinica | None:
        """La HC del paciente, incluida la dada de baja (UNIQUE total)."""
        return await self.sesion.scalar(
            select(HistoriaClinica).where(HistoriaClinica.paciente_id == paciente_id)
        )

    async def soft_delete(
        self, hc: HistoriaClinica, motivo: str, ahora: datetime
    ) -> HistoriaClinica:
        hc.deleted_at = ahora
        hc.motivo_baja = motivo
        hc.updated_at = ahora
        await self.sesion.flush()
        return hc
