"""Repo de liquidaciones e ítems (C-11, D-02, D-09, D-10).

`candidatas` elige las prestaciones liquidables: ítems de presupuestos `aceptado` o `cobrado`
con plan de esa obra social, aceptados dentro del mes (en la zona del servidor), con el cargo
sin anular y sin fila previa en `item_liquidacion`. Las filas leen los valores congelados al
aceptar (plan, arancel, `cubierto`): nunca recalculan. El borrado físico solo existe para
descartar un `borrador` (D-10).
"""
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modelos import (
    ItemLiquidacion, ItemPresupuesto, Liquidacion, Movimiento, ObraSocial, Paciente, Plan,
    Presupuesto, Tratamiento,
)
from app.repos.base import BaseRepository


@dataclass(frozen=True)
class Candidata:
    item_presupuesto_id: int
    plan_id: int
    arancel_id: int | None
    cubierto: object  # Decimal | None
    decidido_at: datetime


@dataclass(frozen=True)
class FilaDetalle:
    item_id: int
    item_presupuesto_id: int
    plan_id: int
    plan_nombre: str
    arancel_id: int | None
    fecha_prestacion: date
    monto: object  # Decimal
    paciente_nombre: str
    codigo: str
    descripcion: str
    cantidad: int
    profesional_id: int


class LiquidacionRepository(BaseRepository[Liquidacion]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Liquidacion)

    async def candidatas(self, os_id: int, inicio: datetime, fin: datetime) -> list[Candidata]:
        anulacion = aliased(Movimiento)
        cargo_anulado = exists().where(
            Movimiento.presupuesto_id == Presupuesto.id,
            Movimiento.tipo == "cargo",
            exists().where(anulacion.anula_a_id == Movimiento.id),
        )
        ya_liquidada = exists().where(ItemLiquidacion.item_presupuesto_id == ItemPresupuesto.id)
        filas = await self.sesion.execute(
            select(
                ItemPresupuesto.id, Presupuesto.plan_id, ItemPresupuesto.arancel_id,
                ItemPresupuesto.cubierto, Presupuesto.decidido_at,
            )
            .join(Presupuesto, Presupuesto.id == ItemPresupuesto.presupuesto_id)
            .join(Plan, Plan.id == Presupuesto.plan_id)
            .where(
                Plan.obra_social_id == os_id,
                Presupuesto.estado.in_(("aceptado", "cobrado")),
                Presupuesto.deleted_at.is_(None),
                Presupuesto.decidido_at >= inicio,
                Presupuesto.decidido_at < fin,
                ~cargo_anulado,
                ~ya_liquidada,
            )
            .order_by(Presupuesto.plan_id, Presupuesto.decidido_at, ItemPresupuesto.id)
        )
        return [Candidata(*fila) for fila in filas.all()]

    async def agregar_items(self, filas: list[dict]) -> list[ItemLiquidacion]:
        items = [ItemLiquidacion(**datos) for datos in filas]
        self.sesion.add_all(items)
        await self.sesion.flush()
        return items

    async def get_para_actualizar(self, liquidacion_id: int) -> Liquidacion | None:
        return await self.sesion.scalar(
            select(Liquidacion)
            .where(Liquidacion.id == liquidacion_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def obra_social_de(self, os_id: int) -> ObraSocial | None:
        return await self.sesion.get(ObraSocial, os_id)

    async def listar(self) -> list[tuple[Liquidacion, str]]:
        filas = await self.sesion.execute(
            select(Liquidacion, ObraSocial.nombre)
            .join(ObraSocial, ObraSocial.id == Liquidacion.os_id)
            .order_by(Liquidacion.periodo.desc(), Liquidacion.id.desc())
            .execution_options(populate_existing=True)
        )
        return [(liq, nombre) for liq, nombre in filas.all()]

    async def con_obra(self, liquidacion_id: int) -> tuple[Liquidacion, str] | None:
        fila = (await self.sesion.execute(
            select(Liquidacion, ObraSocial.nombre)
            .join(ObraSocial, ObraSocial.id == Liquidacion.os_id)
            .where(Liquidacion.id == liquidacion_id)
            .execution_options(populate_existing=True)
        )).first()
        return None if fila is None else (fila[0], fila[1])

    async def filas(
        self, liquidacion_id: int, profesional_id: int | None = None
    ) -> list[FilaDetalle]:
        """Filas con paciente, código y descripción: solo datos administrativos (RN-CL-04)."""
        consulta = (
            select(
                ItemLiquidacion.id, ItemLiquidacion.item_presupuesto_id, ItemLiquidacion.plan_id,
                Plan.nombre, ItemLiquidacion.arancel_id, ItemLiquidacion.fecha_prestacion,
                ItemLiquidacion.monto,
                (Paciente.apellido + ", " + Paciente.nombre),
                func.coalesce(Tratamiento.codigo_nomenclador, Tratamiento.codigo),
                Tratamiento.nombre, ItemPresupuesto.cantidad, Presupuesto.profesional_id,
            )
            .join(Plan, Plan.id == ItemLiquidacion.plan_id)
            .join(ItemPresupuesto, ItemPresupuesto.id == ItemLiquidacion.item_presupuesto_id)
            .join(Presupuesto, Presupuesto.id == ItemPresupuesto.presupuesto_id)
            .join(Paciente, Paciente.id == Presupuesto.paciente_id)
            .join(Tratamiento, Tratamiento.id == ItemPresupuesto.tratamiento_id)
            .where(ItemLiquidacion.liquidacion_id == liquidacion_id)
            .order_by(Plan.nombre, ItemLiquidacion.fecha_prestacion, ItemLiquidacion.id)
        )
        if profesional_id is not None:
            consulta = consulta.where(Presupuesto.profesional_id == profesional_id)
        return [FilaDetalle(*fila) for fila in (await self.sesion.execute(consulta)).all()]

    async def eliminar_con_items(self, liquidacion: Liquidacion) -> None:
        """Descarta un `borrador`: borra sus filas y la cabecera (D-10)."""
        await self.sesion.execute(
            delete(ItemLiquidacion).where(ItemLiquidacion.liquidacion_id == liquidacion.id)
        )
        await self.sesion.delete(liquidacion)
        await self.sesion.flush()


__all__ = ["Candidata", "FilaDetalle", "LiquidacionRepository"]
