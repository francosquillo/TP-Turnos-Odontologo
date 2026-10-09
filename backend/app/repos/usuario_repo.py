"""Repo Usuario: hereda CRUD + consultas para el guard >=1 admin (RN-AU-03)."""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modelos import Rol, Usuario
from app.repos.base import BaseRepository


class UsuarioRepository(BaseRepository[Usuario]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Usuario)

    async def listar_admins_activos(self) -> list[Usuario]:
        """Admins activos (para el guard >=1 admin)."""
        filas = await self.sesion.execute(
            select(Usuario)
            .join(Rol, Usuario.rol_id == Rol.id)
            .where(Rol.nombre == "admin", Usuario.activo.is_(True))
        )
        return list(filas.scalars().all())

    async def obtener_por_email(self, email: str) -> Usuario | None:
        """Lookup case-insensitive (usa uq_usuario_email_lower), con rol."""
        fila = await self.sesion.execute(
            select(Usuario)
            .options(selectinload(Usuario.rol))
            .where(func.lower(Usuario.email) == email.lower())
        )
        return fila.scalars().first()

    async def obtener_con_rol(self, usuario_id: int) -> Usuario | None:
        """Usuario por id con rol cargado (auth necesita `usuario.rol.nombre`)."""
        fila = await self.sesion.execute(
            select(Usuario)
            .options(selectinload(Usuario.rol))
            .where(Usuario.id == usuario_id)
        )
        return fila.scalars().first()

    async def listar_todos_con_rol(self) -> list[Usuario]:
        """Listado admin con rol cargado, orden estable por id."""
        filas = await self.sesion.execute(
            select(Usuario).options(selectinload(Usuario.rol)).order_by(Usuario.id)
        )
        return list(filas.scalars().all())
