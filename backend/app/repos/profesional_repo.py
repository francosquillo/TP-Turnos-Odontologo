"""Repo Profesional: hereda CRUD de la base (D-02)."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import Profesional
from app.repos.base import BaseRepository


class ProfesionalRepository(BaseRepository[Profesional]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Profesional)

    async def por_usuario_id(self, usuario_id: int) -> Profesional | None:
        """Profesional vinculado a la cuenta (RBAC odontologo, D-07)."""
        filas = await self.sesion.execute(
            select(Profesional).where(Profesional.usuario_id == usuario_id)
        )
        return filas.scalars().first()
