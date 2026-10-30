"""Repo EsperaEntry: CRUD + matching FIFO compatible (C-07, D-01).

`activas_compatibles` filtra en SQL lo indexado (estado, profesional_id)
y en Python la lógica de especialidad + preferencia_horaria (JSONB).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import EsperaEntry
from app.repos.base import BaseRepository


TZ_BA = ZoneInfo("America/Argentina/Buenos_Aires")


def _local(inicio: datetime) -> datetime:
    """El hueco viene en UTC desde DB; la preferencia del paciente es hora BA."""
    return inicio.astimezone(TZ_BA) if inicio.tzinfo is not None else inicio


def _dia_semana_es(inicio: datetime) -> str:
    """Nombre del día en español (lunes..domingo) para comparar con preferencia."""
    inicio = _local(inicio)
    return (
        "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"
    )[inicio.weekday()]


def _cumple_preferencia(preferencia: dict | None, inicio: datetime) -> bool:
    """True si `inicio` cae en los días/franja de preferencia (o sin preferencia)."""
    if not preferencia:
        return True
    dias = preferencia.get("dias") or []
    if dias and _dia_semana_es(inicio) not in dias:
        return False
    desde = preferencia.get("desde")
    hasta = preferencia.get("hasta")
    if desde or hasta:
        hhmm = _local(inicio).strftime("%H:%M")
        if desde and hhmm < desde:
            return False
        if hasta and hhmm >= hasta:  # fin exclusivo: 09:00 no está en [08:00, 09:00)
            return False
    return True


def _especialidad_compatible(
    especialidad_entry: str | None, especialidades_profesional: str
) -> bool:
    """True si la especialidad de la entry está en las del profesional."""
    if especialidad_entry is None:
        return True
    if not especialidades_profesional:
        return False
    return especialidad_entry.lower() in especialidades_profesional.lower()


class EsperaRepository(BaseRepository[EsperaEntry]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, EsperaEntry)

    async def activas_compatibles(
        self,
        profesional_id: int | None,
        especialidades_profesional: str,
        inicio: datetime,
        preferencia_horaria: dict | None = None,
    ) -> list[EsperaEntry]:
        """Entradas activas compatibles con el hueco, orden FIFO (created_at ASC).

        Filtros SQL (indexados): estado='activa', profesional_id NULL o igual.
        Filtros Python (JSONB/lógica): especialidad contenida en las del
        profesional, preferencia_horaria cubre el inicio del hueco.
        """
        condiciones = [EsperaEntry.estado == "activa"]
        if profesional_id is not None:
            condiciones.append(
                (EsperaEntry.profesional_id == profesional_id)
                | (EsperaEntry.profesional_id.is_(None))
            )
        filas = await self.sesion.execute(
            select(EsperaEntry)
            .where(and_(*condiciones))
            .order_by(EsperaEntry.created_at.asc(), EsperaEntry.id.asc())
        )
        candidatos = list(filas.scalars().all())
        return [
            e
            for e in candidatos
            if e.estado == "activa"
            and (profesional_id is None or e.profesional_id is None or e.profesional_id == profesional_id)
            and _especialidad_compatible(e.especialidad, especialidades_profesional)
            and _cumple_preferencia(e.preferencia_horaria, inicio)
        ]

    async def get_by_token_hash(self, token_hash: str) -> EsperaEntry | None:
        """Busca entry por token_oferta_hash (aceptar/rechazar, D-04)."""
        return await self.sesion.scalar(
            select(EsperaEntry).where(
                EsperaEntry.token_oferta_hash == token_hash
            ).limit(1)
        )

    async def listar_fifo(
        self, estado: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[EsperaEntry]:
        """Cola ordenada FIFO (created_at ASC), filtrable por estado."""
        consulta = select(EsperaEntry).order_by(
            EsperaEntry.created_at.asc(), EsperaEntry.id.asc()
        )
        if estado is not None:
            consulta = consulta.where(EsperaEntry.estado == estado)
        filas = await self.sesion.execute(consulta.limit(limit).offset(offset))
        return list(filas.scalars().all())

    async def ofrecidas_vencidas(self, ahora: datetime) -> list[EsperaEntry]:
        """Ofertas sin respuesta con `oferta_expira_en <= ahora` (barrido, D-05)."""
        filas = await self.sesion.execute(
            select(EsperaEntry)
            .where(
                EsperaEntry.estado == "ofrecida",
                EsperaEntry.oferta_expira_en <= ahora,
            )
            .order_by(EsperaEntry.oferta_expira_en.asc(), EsperaEntry.id.asc())
        )
        return list(filas.scalars().all())
