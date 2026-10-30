"""Repo HallazgoOdontograma + lectura del catálogo de estados (C-08, D-04/D-05).

Orden del historial: `fecha DESC, id DESC`. Toda consulta por hallazgo lleva
`hc_id` para que un id de otra historia nunca se filtre (404 en la API).
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import EstadoHallazgoCatalogo, HallazgoOdontograma
from app.repos.base import BaseRepository


class HallazgoRepository(BaseRepository[HallazgoOdontograma]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, HallazgoOdontograma)

    async def listar(
        self, hc_id: int, pieza: int | None = None, incluir_anulados: bool = False
    ) -> list[HallazgoOdontograma]:
        consulta = select(HallazgoOdontograma).where(HallazgoOdontograma.hc_id == hc_id)
        if pieza is not None:
            consulta = consulta.where(HallazgoOdontograma.pieza_fdi == pieza)
        if not incluir_anulados:
            consulta = consulta.where(HallazgoOdontograma.deleted_at.is_(None))
        filas = await self.sesion.execute(
            consulta.order_by(HallazgoOdontograma.fecha.desc(), HallazgoOdontograma.id.desc())
        )
        return list(filas.scalars().all())

    async def get_en_hc(self, hc_id: int, hallazgo_id: int) -> HallazgoOdontograma | None:
        return await self.sesion.scalar(
            select(HallazgoOdontograma).where(
                HallazgoOdontograma.id == hallazgo_id,
                HallazgoOdontograma.hc_id == hc_id,
            )
        )

    async def estados_vigentes(self) -> tuple[int | None, list[EstadoHallazgoCatalogo]]:
        """(versión, estados) de la última versión vigente; (None, []) sin catálogo."""
        version = await self.sesion.scalar(
            select(func.max(EstadoHallazgoCatalogo.version)).where(
                EstadoHallazgoCatalogo.vigente.is_(True)
            )
        )
        if version is None:
            return None, []
        filas = await self.sesion.execute(
            select(EstadoHallazgoCatalogo)
            .where(
                EstadoHallazgoCatalogo.version == version,
                EstadoHallazgoCatalogo.vigente.is_(True),
            )
            .order_by(EstadoHallazgoCatalogo.id)
        )
        return version, list(filas.scalars().all())
