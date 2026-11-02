"""Repo Paciente: hereda CRUD + baja logica (RN-GL-01, D-06)."""
from datetime import datetime, timezone

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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

    async def dnis_activos(self, dnis: Collection[str]) -> set[str]:
        """DNI de la lista que ya pertenecen a pacientes no eliminados (C-12, importacion)."""
        if not dnis:
            return set()
        filas = await self.sesion.execute(
            select(Paciente.dni).where(Paciente.dni.in_(dnis), Paciente.deleted_at.is_(None))
        )
        return set(filas.scalars().all())

    async def insertar_si_no_existe(self, **datos) -> int | None:
        """`INSERT ... ON CONFLICT DO NOTHING`: devuelve el id, o `None` si choco con `uq_paciente_dni`.

        No aborta la transaccion ante un DNI repetido (incluye pacientes dados de baja: el
        indice unico cubre tambien las filas con `deleted_at`).
        """
        consulta = pg_insert(Paciente).values(**datos).on_conflict_do_nothing().returning(Paciente.id)
        return await self.sesion.scalar(consulta)

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
