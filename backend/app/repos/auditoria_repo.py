"""Repo de auditoria de acciones admin (C-12 R3, D-10): solo alta y lectura, nunca edicion."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import EventoAuditoria
from app.repos.base import BaseRepository


class AuditoriaRepository(BaseRepository[EventoAuditoria]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, EventoAuditoria)

    async def registrar(
        self,
        *,
        actor_id: int,
        accion: str,
        objeto_tipo: str,
        objeto_id: int | None = None,
        detalle: dict | None = None,
    ) -> EventoAuditoria:
        """Agrega el evento con flush, dentro de la transaccion del request."""
        return await self.crear(
            actor_id=actor_id, accion=accion, objeto_tipo=objeto_tipo, objeto_id=objeto_id,
            detalle=detalle or {},
        )

    async def listar_recientes(self, limit: int = 50, offset: int = 0) -> list[EventoAuditoria]:
        """Del mas reciente al mas antiguo; el id desempata eventos de una misma transaccion."""
        filas = await self.sesion.execute(
            select(EventoAuditoria)
            .order_by(EventoAuditoria.created_at.desc(), EventoAuditoria.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(filas.scalars().all())
