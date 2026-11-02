"""Repo Presupuesto + ítems (C-09, D-13, D-18).

`get_para_actualizar` toma `SELECT ... FOR UPDATE` y refresca la fila: toda
transición y edición valida el estado recién después de ese lock. Los ítems de
un borrador se reemplazan físicamente (D-18). El orden del historial es
`created_at DESC, id DESC`. Las bajas lógicas nunca se listan.
"""
from dataclasses import dataclass

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import (
    HallazgoOdontograma, ItemLiquidacion, ItemPresupuesto, Presupuesto, Tratamiento,
)
from app.repos.base import BaseRepository


@dataclass(frozen=True)
class ItemDetalle:
    """Ítem con los datos de lectura del hallazgo y del tratamiento."""

    item: ItemPresupuesto
    tratamiento_nombre: str
    pieza_fdi: int
    cara: str
    hallazgo_vigente: bool


class PresupuestoRepository(BaseRepository[Presupuesto]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Presupuesto)

    async def get_activo(self, presupuesto_id: int) -> Presupuesto | None:
        return await self.sesion.scalar(
            select(Presupuesto).where(
                Presupuesto.id == presupuesto_id, Presupuesto.deleted_at.is_(None)
            )
        )

    async def estado_de(self, presupuesto_id: int) -> str:
        """Estado actual leído de la DB (sin depender del identity map)."""
        return await self.sesion.scalar(
            select(Presupuesto.estado).where(Presupuesto.id == presupuesto_id)
        )

    async def get_para_actualizar(self, presupuesto_id: int) -> Presupuesto | None:
        """Fila activa bloqueada (`FOR UPDATE`) y refrescada desde la DB."""
        return await self.sesion.scalar(
            select(Presupuesto)
            .where(Presupuesto.id == presupuesto_id, Presupuesto.deleted_at.is_(None))
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def listar(
        self, paciente_id: int, estado: str | None = None
    ) -> list[Presupuesto]:
        consulta = select(Presupuesto).where(
            Presupuesto.paciente_id == paciente_id, Presupuesto.deleted_at.is_(None)
        )
        if estado is not None:
            consulta = consulta.where(Presupuesto.estado == estado)
        filas = await self.sesion.execute(
            consulta.order_by(Presupuesto.created_at.desc(), Presupuesto.id.desc())
        )
        return list(filas.scalars().all())

    async def reemplazar_items(
        self, presupuesto_id: int, items: list[dict]
    ) -> list[ItemPresupuesto]:
        """Borra los ítems del borrador y crea los nuevos (D-18: sin efecto contable)."""
        await self.sesion.execute(
            delete(ItemPresupuesto).where(ItemPresupuesto.presupuesto_id == presupuesto_id)
        )
        nuevos = [ItemPresupuesto(presupuesto_id=presupuesto_id, **datos) for datos in items]
        self.sesion.add_all(nuevos)
        await self.sesion.flush()
        return nuevos

    async def items_detalle(self, presupuesto_id: int) -> list[ItemDetalle]:
        """Ítems en orden de alta, con pieza, cara, nombre y vigencia del hallazgo."""
        filas = await self.sesion.execute(
            select(
                ItemPresupuesto, Tratamiento.nombre, HallazgoOdontograma.pieza_fdi,
                HallazgoOdontograma.cara, HallazgoOdontograma.deleted_at.is_(None),
            )
            .join(Tratamiento, Tratamiento.id == ItemPresupuesto.tratamiento_id)
            .join(HallazgoOdontograma, HallazgoOdontograma.id == ItemPresupuesto.hallazgo_id)
            .where(ItemPresupuesto.presupuesto_id == presupuesto_id)
            .order_by(ItemPresupuesto.id)
            .execution_options(populate_existing=True)
        )
        return [ItemDetalle(*fila) for fila in filas.all()]


    async def items_con_nomenclador(
        self, presupuesto_id: int
    ) -> list[tuple[ItemPresupuesto, str | None]]:
        """Ítems en orden de alta con el código de nomenclador de su tratamiento (C-11, D-03)."""
        filas = await self.sesion.execute(
            select(ItemPresupuesto, Tratamiento.codigo_nomenclador)
            .join(Tratamiento, Tratamiento.id == ItemPresupuesto.tratamiento_id)
            .where(ItemPresupuesto.presupuesto_id == presupuesto_id)
            .order_by(ItemPresupuesto.id)
            .execution_options(populate_existing=True)
        )
        return [(item, codigo) for item, codigo in filas.all()]

    async def tiene_item_liquidado(self, presupuesto_id: int) -> bool:
        """True si algún ítem del presupuesto está en cualquier liquidación (C-11, D-06)."""
        return bool(await self.sesion.scalar(
            select(
                exists().where(
                    ItemLiquidacion.item_presupuesto_id == ItemPresupuesto.id,
                    ItemPresupuesto.presupuesto_id == presupuesto_id,
                )
            )
        ))
