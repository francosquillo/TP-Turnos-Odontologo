"""Repo Sillon: hereda CRUD de la base (D-02)."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import Sillon
from app.repos.base import BaseRepository


class SillonRepository(BaseRepository[Sillon]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Sillon)
