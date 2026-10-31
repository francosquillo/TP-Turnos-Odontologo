"""Repo Recibo (C-10, D-10, D-22, D-25).

`siguiente_numero` usa una fila contador: el lock de fila dura hasta el commit y el
rollback devuelve el número (las secuencias de Postgres dejan huecos). El recibo es
inmutable salvo su anulación (trigger); este repo solo inserta, lee y bloquea.
"""
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import Caja, MovimientoCaja, Paciente, Recibo
from app.repos.base import BaseRepository

_SIGUIENTE = text(
    "INSERT INTO recibo_contador (id, ultimo) VALUES (1, 1) "
    "ON CONFLICT (id) DO UPDATE SET ultimo = recibo_contador.ultimo + 1 "
    "RETURNING ultimo"
)


@dataclass(frozen=True)
class ReciboListado:
    recibo: Recibo
    paciente_nombre: str
    fecha: date


class ReciboRepository(BaseRepository[Recibo]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Recibo)

    async def siguiente_numero(self) -> int:
        """Número consecutivo sin huecos; pedirlo siempre dentro de la transacción del cobro."""
        return int(await self.sesion.scalar(_SIGUIENTE))

    async def por_clave(self, clave: str) -> Recibo | None:
        """Lectura sin lock (D-25)."""
        return await self.sesion.scalar(
            select(Recibo)
            .where(Recibo.clave_idempotencia == clave)
            .execution_options(populate_existing=True)
        )

    async def get_para_actualizar(self, recibo_id: int) -> Recibo | None:
        return await self.sesion.scalar(
            select(Recibo)
            .where(Recibo.id == recibo_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def fecha_de(self, recibo_id: int) -> date:
        """Fecha de la caja en la que se emitió (su ingreso)."""
        return await self.sesion.scalar(
            select(Caja.fecha)
            .join(MovimientoCaja, MovimientoCaja.caja_id == Caja.id)
            .where(MovimientoCaja.recibo_id == recibo_id, MovimientoCaja.monto > 0)
        )

    async def listar_por_fecha(self, fecha: date) -> list[ReciboListado]:
        """Recibos emitidos en la caja de esa fecha, del número mayor al menor."""
        filas = await self.sesion.execute(
            select(Recibo, Paciente.nombre, Paciente.apellido, Caja.fecha)
            .join(MovimientoCaja, MovimientoCaja.recibo_id == Recibo.id)
            .join(Caja, Caja.id == MovimientoCaja.caja_id)
            .join(Paciente, Paciente.id == Recibo.paciente_id)
            .where(Caja.fecha == fecha, MovimientoCaja.monto > 0)
            .order_by(Recibo.numero.desc())
            .execution_options(populate_existing=True)
        )
        return [
            ReciboListado(recibo, f"{nombre} {apellido}", dia)
            for recibo, nombre, apellido, dia in filas.all()
        ]
