"""Repo Tratamiento: solo lectura para la API (C-08, D-10)."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import Tratamiento
from app.repos.base import BaseRepository


class TratamientoRepository(BaseRepository[Tratamiento]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Tratamiento)

    async def listar(self) -> list[Tratamiento]:
        filas = await self.sesion.execute(select(Tratamiento).order_by(Tratamiento.codigo))
        return list(filas.scalars().all())
