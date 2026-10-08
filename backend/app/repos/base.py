"""Base repository generico async (D-02): get/list/crear/actualizar/eliminar.

Los servicios importan repos, nunca AsyncSession directo.
"""
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import Base

M = TypeVar("M", bound=Base)


class BaseRepository(Generic[M]):
    """CRUD async tipado por entidad; los repos finos heredan sin duplicar."""

    def __init__(self, sesion: AsyncSession, modelo: type[M]) -> None:
        self.sesion = sesion
        self.modelo = modelo

    async def get(self, id: int) -> M | None:
        return await self.sesion.get(self.modelo, id)

    async def list(self, limit: int = 100, offset: int = 0) -> list[M]:
        filas = await self.sesion.execute(
            select(self.modelo).limit(limit).offset(offset)
        )
        return list(filas.scalars().all())

    async def crear(self, **datos) -> M:
        entidad = self.modelo(**datos)
        self.sesion.add(entidad)
        await self.sesion.flush()
        return entidad

    async def actualizar(self, entidad: M, **cambios) -> M:
        for campo, valor in cambios.items():
            setattr(entidad, campo, valor)
        await self.sesion.flush()
        return entidad

    async def eliminar(self, entidad: M) -> None:
        await self.sesion.delete(entidad)
        await self.sesion.flush()
