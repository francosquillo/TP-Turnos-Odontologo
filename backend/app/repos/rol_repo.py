"""Repo Rol: hereda CRUD de la base (D-02)."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import Rol
from app.repos.base import BaseRepository


class RolRepository(BaseRepository[Rol]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Rol)
