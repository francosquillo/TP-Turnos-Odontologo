"""Repos de obra social, plan y arancel (C-11, D-07, D-08).

`arancel_vigente` usa bordes inclusivos (`vigencia_desde <= fecha <= vigencia_hasta`) y un
`vigencia_hasta` nulo como abierto: el EXCLUDE de la tabla garantiza que haya a lo sumo uno.
Nada se borra: la baja es lógica (`activa`/`activo`).
"""
from dataclasses import dataclass
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import Arancel, ObraSocial, Plan
from app.repos.base import BaseRepository


@dataclass(frozen=True)
class PlanConObra:
    plan: Plan
    obra_social: ObraSocial


class ObraSocialRepository(BaseRepository[ObraSocial]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, ObraSocial)

    async def listar(self, solo_activas: bool = False) -> list[ObraSocial]:
        consulta = select(ObraSocial).order_by(ObraSocial.nombre, ObraSocial.id)
        if solo_activas:
            consulta = consulta.where(ObraSocial.activa.is_(True))
        return list((await self.sesion.execute(consulta)).scalars().all())


class PlanRepository(BaseRepository[Plan]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Plan)

    async def con_obra(self, plan_id: int) -> PlanConObra | None:
        fila = (await self.sesion.execute(
            select(Plan, ObraSocial)
            .join(ObraSocial, ObraSocial.id == Plan.obra_social_id)
            .where(Plan.id == plan_id)
            .execution_options(populate_existing=True)
        )).first()
        return None if fila is None else PlanConObra(fila[0], fila[1])

    async def listar(self, obra_social_id: int | None = None) -> list[PlanConObra]:
        consulta = (
            select(Plan, ObraSocial)
            .join(ObraSocial, ObraSocial.id == Plan.obra_social_id)
            .order_by(ObraSocial.nombre, Plan.nombre, Plan.id)
        )
        if obra_social_id is not None:
            consulta = consulta.where(Plan.obra_social_id == obra_social_id)
        filas = (await self.sesion.execute(consulta)).all()
        return [PlanConObra(plan, obra) for plan, obra in filas]


class ArancelRepository(BaseRepository[Arancel]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Arancel)

    async def arancel_vigente(self, plan_id: int, codigo: str, fecha: date) -> Arancel | None:
        """El arancel del plan y código vigente en `fecha` (bordes inclusivos), o None."""
        return await self.sesion.scalar(
            select(Arancel).where(
                Arancel.plan_id == plan_id,
                Arancel.codigo_nomenclador == codigo,
                Arancel.vigencia_desde <= fecha,
                or_(Arancel.vigencia_hasta.is_(None), Arancel.vigencia_hasta >= fecha),
            )
        )

    async def listar(
        self, plan_id: int | None = None, codigo: str | None = None
    ) -> list[Arancel]:
        consulta = select(Arancel).order_by(
            Arancel.plan_id, Arancel.codigo_nomenclador, Arancel.vigencia_desde
        )
        if plan_id is not None:
            consulta = consulta.where(Arancel.plan_id == plan_id)
        if codigo is not None:
            consulta = consulta.where(Arancel.codigo_nomenclador == codigo)
        return list((await self.sesion.execute(consulta)).scalars().all())

    async def get_para_actualizar(self, arancel_id: int) -> Arancel | None:
        return await self.sesion.scalar(
            select(Arancel)
            .where(Arancel.id == arancel_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )


__all__ = ["ArancelRepository", "ObraSocialRepository", "PlanConObra", "PlanRepository"]
