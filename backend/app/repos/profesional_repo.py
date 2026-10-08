"""Repo Profesional: hereda CRUD de la base (D-02)."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import Profesional
from app.repos.base import BaseRepository


class ProfesionalRepository(BaseRepository[Profesional]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Profesional)
