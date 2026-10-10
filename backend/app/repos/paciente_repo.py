"""Repo Paciente: hereda CRUD + baja logica (RN-GL-01, D-06)."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import Paciente
from app.repos.base import BaseRepository


class PacienteRepository(BaseRepository[Paciente]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Paciente)

    async def listar_activos(self, limit: int = 100, offset: int = 0) -> list[Paciente]:
        """Solo no eliminados (filtro por defecto)."""
        filas = await self.sesion.execute(
            select(Paciente)
            .where(Paciente.deleted_at.is_(None))
            .limit(limit)
            .offset(offset)
        )
        return list(filas.scalars().all())

    async def por_telefono(self, telefono: str):
        """Paciente no eliminado con ese telefono normalizado (C-05, D-05)."""
        filas = await self.sesion.execute(
            select(Paciente)
            .where(
                Paciente.telefono == telefono,
                Paciente.deleted_at.is_(None),
            )
            .limit(1)
        )
        return filas.scalars().first()

    async def soft_delete(self, paciente: Paciente) -> Paciente:
        """Baja logica: nunca DELETE fisico."""
        paciente.deleted_at = datetime.now(timezone.utc)
        await self.sesion.flush()
        return paciente
