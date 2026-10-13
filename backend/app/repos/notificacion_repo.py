"""Repo Notificacion + Plantilla (C-06, D-01/D-02).

El servicio importa repos, nunca AsyncSession directo.
"""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import Notificacion, Plantilla
from app.repos.base import BaseRepository


class NotificacionRepository(BaseRepository[Notificacion]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Notificacion)

    async def activa_de_turno(
        self, turno_id: int, plantilla: str
    ) -> Notificacion | None:
        """Fila no-fallida del turno+plantilla (None si solo hay fallidas)."""
        return await self.sesion.scalar(
            select(Notificacion)
            .where(
                Notificacion.turno_id == turno_id,
                Notificacion.plantilla == plantilla,
                Notificacion.estado != "fallida",
            )
            .limit(1)
        )

    async def por_message_id(self, message_id: str) -> Notificacion | None:
        """Fila cuyo payload lleva ese message_id (webhook estado_mensaje)."""
        return await self.sesion.scalar(
            select(Notificacion)
            .where(Notificacion.payload["message_id"].astext == message_id)
            .limit(1)
        )

    async def fallida_de_turno(
        self, turno_id: int, plantilla: str
    ) -> Notificacion | None:
        """Fallida existente (evita duplicar avisos a secretaria, D-06)."""
        return await self.sesion.scalar(
            select(Notificacion)
            .where(
                Notificacion.turno_id == turno_id,
                Notificacion.plantilla == plantilla,
                Notificacion.estado == "fallida",
            )
            .order_by(Notificacion.id.desc())
            .limit(1)
        )

    async def encoladas(self, limit: int = 100) -> list[Notificacion]:
        """Encoladas nunca enviadas (degradadas por Redis caido, D-04)."""
        filas = await self.sesion.execute(
            select(Notificacion)
            .where(Notificacion.estado == "encolada")
            .order_by(Notificacion.id)
            .limit(limit)
        )
        return list(filas.scalars().all())

    async def fallidas(
        self, limit: int = 50, offset: int = 0
    ) -> list[Notificacion]:
        """Fallidas para el aviso a secretaria (D-06), paginado."""
        filas = await self.sesion.execute(
            select(Notificacion)
            .where(Notificacion.estado == "fallida")
            .order_by(Notificacion.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(filas.scalars().all())


class PlantillaRepository(BaseRepository[Plantilla]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Plantilla)

    async def upsert(
        self, nombre: str, version: str, cuerpo: str, variables: list[str]
    ) -> Plantilla:
        """Upsert idempotente por (nombre, version) para el seed (D-02)."""
        fila = await self.sesion.scalar(
            pg_insert(Plantilla)
            .values(
                nombre=nombre, version=version, cuerpo=cuerpo,
                variables=list(variables),
            )
            .on_conflict_do_update(
                index_elements=["nombre", "version"],
                set_={"cuerpo": cuerpo, "variables": list(variables)},
            )
            .returning(Plantilla)
        )
        assert fila is not None
        return fila

    async def obtener(self, nombre: str, version: str = "v1") -> Plantilla | None:
        return await self.sesion.get(Plantilla, (nombre, version))

    async def contar_version(self, version: str = "v1") -> int:
        from sqlalchemy import func

        return (
            await self.sesion.scalar(
                select(func.count())
                .select_from(Plantilla)
                .where(Plantilla.version == version)
            )
        ) or 0
