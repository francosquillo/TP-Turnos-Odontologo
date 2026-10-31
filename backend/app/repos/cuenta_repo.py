"""Repo CuentaCorriente + Movimiento (C-09, D-11, D-13, D-14, D-16).

El saldo NO se guarda: es `COALESCE(SUM(monto), 0)` en cada lectura. `asegurar`
usa `INSERT ... ON CONFLICT DO NOTHING` + `SELECT` para el primer cargo
concurrente. Los movimientos son inmutables (trigger): este repo solo inserta y
lee. `movimiento_para_actualizar` toma `FOR UPDATE` para serializar anulaciones.
"""
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modelos import CuentaCorriente, Movimiento
from app.repos.base import BaseRepository


@dataclass(frozen=True)
class MovimientoListado:
    movimiento: Movimiento
    anulado: bool


class CuentaRepository(BaseRepository[CuentaCorriente]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, CuentaCorriente)

    async def por_paciente(self, paciente_id: int) -> CuentaCorriente | None:
        """La cuenta del paciente o None: consultar nunca crea filas."""
        return await self.sesion.scalar(
            select(CuentaCorriente).where(CuentaCorriente.paciente_id == paciente_id)
        )

    async def asegurar(self, paciente_id: int) -> CuentaCorriente:
        """Crea la cuenta si falta; seguro ante dos primeros cargos simultáneos."""
        await self.sesion.execute(
            pg_insert(CuentaCorriente)
            .values(paciente_id=paciente_id)
            .on_conflict_do_nothing(index_elements=["paciente_id"])
        )
        cuenta = await self.por_paciente(paciente_id)
        assert cuenta is not None
        return cuenta

    async def saldo(self, cc_id: int) -> Decimal:
        return await self.sesion.scalar(
            select(func.coalesce(func.sum(Movimiento.monto), 0)).where(
                Movimiento.cc_id == cc_id
            )
        )

    async def crear_movimiento(self, cc_id: int, **datos) -> Movimiento:
        movimiento = Movimiento(cc_id=cc_id, **datos)
        self.sesion.add(movimiento)
        await self.sesion.flush()
        return movimiento

    async def movimientos(self, cc_id: int) -> list[MovimientoListado]:
        """Del más reciente al más antiguo, con `anulado` derivado."""
        anulacion = aliased(Movimiento)
        anulado = exists().where(anulacion.anula_a_id == Movimiento.id)
        filas = await self.sesion.execute(
            select(Movimiento, anulado)
            .where(Movimiento.cc_id == cc_id)
            .order_by(Movimiento.created_at.desc(), Movimiento.id.desc())
        )
        return [MovimientoListado(mov, bool(flag)) for mov, flag in filas.all()]

    async def movimiento_para_actualizar(
        self, cc_id: int, movimiento_id: int
    ) -> Movimiento | None:
        """Movimiento de esa cuenta, bloqueado; otro `cc_id` da None (404 en la API)."""
        return await self.sesion.scalar(
            select(Movimiento)
            .where(Movimiento.id == movimiento_id, Movimiento.cc_id == cc_id)
            .with_for_update()
        )

    async def presupuestos_con_cargo_anulado(self, ids: list[int]) -> set[int]:
        """Ids de presupuestos cuyo cargo tiene un contramovimiento (D-14)."""
        if not ids:
            return set()
        anulacion = aliased(Movimiento)
        filas = await self.sesion.execute(
            select(Movimiento.presupuesto_id).where(
                Movimiento.presupuesto_id.in_(ids),
                Movimiento.tipo == "cargo",
                exists().where(anulacion.anula_a_id == Movimiento.id),
            )
        )
        return set(filas.scalars().all())

    async def tiene_anulacion(self, movimiento_id: int) -> bool:
        """True si ya existe un contramovimiento de ese movimiento."""
        return (
            await self.sesion.scalar(
                select(Movimiento.id).where(Movimiento.anula_a_id == movimiento_id).limit(1)
            )
        ) is not None
