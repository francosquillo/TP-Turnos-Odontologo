"""Repo Usuario: hereda CRUD + consultas para el guard >=1 admin (RN-AU-03)."""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
        """Lookup case-insensitive (usa uq_usuario_email_lower)."""
        fila = await self.sesion.execute(
            select(Usuario).where(func.lower(Usuario.email) == email.lower())
        )
        return fila.scalars().first()
