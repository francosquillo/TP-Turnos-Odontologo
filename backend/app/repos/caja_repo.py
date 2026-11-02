"""Repo Caja + MovimientoCaja (C-10, D-05, D-11, D-12, D-17).

`asegurar` usa `INSERT ... ON CONFLICT DO NOTHING` SIN indicar índice, para cubrir la
UNIQUE de `fecha` y `uq_caja_una_abierta`. Los locks son `FOR UPDATE` y refrescan la fila.
El total NO se guarda en una caja abierta: se suma en cada lectura.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import Caja, Liquidacion, MovimientoCaja, ObraSocial
from app.repos.base import BaseRepository


class CajaRepository(BaseRepository[Caja]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Caja)

    async def asegurar(self, fecha: date, usuario_id: int) -> None:
        """Abre la caja de esa fecha si falta; no hace nada si existe o hay otra abierta."""
        await self.sesion.execute(
            pg_insert(Caja).values(fecha=fecha, abierta_por=usuario_id).on_conflict_do_nothing()
        )

    async def por_fecha(self, fecha: date) -> Caja | None:
        return await self.sesion.scalar(
            select(Caja).where(Caja.fecha == fecha).execution_options(populate_existing=True)
        )

    async def por_fecha_para_actualizar(self, fecha: date) -> Caja | None:
        return await self.sesion.scalar(
            select(Caja)
            .where(Caja.fecha == fecha)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def get_para_actualizar(self, caja_id: int) -> Caja | None:
        return await self.sesion.scalar(
            select(Caja)
            .where(Caja.id == caja_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def pendiente_anterior(self, hoy: date) -> Caja | None:
        """Caja abierta de una fecha anterior (como máximo una por `uq_caja_una_abierta`)."""
        return await self.sesion.scalar(
            select(Caja)
            .where(Caja.estado == "abierta", Caja.fecha < hoy)
            .execution_options(populate_existing=True)
        )

    async def total(self, caja_id: int) -> Decimal:
        return await self.sesion.scalar(
            select(func.coalesce(func.sum(MovimientoCaja.monto), 0)).where(
                MovimientoCaja.caja_id == caja_id
            )
        )

    async def desglose(self, caja_id: int) -> dict[str, Decimal]:
        filas = await self.sesion.execute(
            select(MovimientoCaja.medio, func.sum(MovimientoCaja.monto))
            .where(MovimientoCaja.caja_id == caja_id)
            .group_by(MovimientoCaja.medio)
            .order_by(MovimientoCaja.medio)
        )
        return {medio: subtotal for medio, subtotal in filas.all()}

    async def crear_movimiento(self, **datos) -> MovimientoCaja:
        movimiento = MovimientoCaja(**datos)
        self.sesion.add(movimiento)
        await self.sesion.flush()
        return movimiento

    async def ingreso_de_liquidacion(self, liquidacion_id: int) -> MovimientoCaja | None:
        """El único ingreso (monto positivo) de la liquidación (`uq_movcaja_liq_ingreso`)."""
        return await self.sesion.scalar(
            select(MovimientoCaja).where(
                MovimientoCaja.liquidacion_id == liquidacion_id, MovimientoCaja.monto > 0
            )
        )

    async def movimientos_de_liquidacion(self, caja_id: int) -> list[tuple]:
        """Ingresos y reversiones de liquidaciones de la caja, sin datos de pacientes (D-15)."""
        filas = await self.sesion.execute(
            select(
                MovimientoCaja.liquidacion_id, ObraSocial.nombre, Liquidacion.periodo,
                MovimientoCaja.medio, MovimientoCaja.monto, MovimientoCaja.created_at,
            )
            .join(Liquidacion, Liquidacion.id == MovimientoCaja.liquidacion_id)
            .join(ObraSocial, ObraSocial.id == Liquidacion.os_id)
            .where(MovimientoCaja.caja_id == caja_id)
            .order_by(MovimientoCaja.created_at, MovimientoCaja.id)
        )
        return list(filas.all())
