"""Repo Usuario: hereda CRUD + consultas para el guard >=1 admin (RN-AU-03)."""
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modelos import Profesional, Rol, Turno, Usuario
from app.repos.base import BaseRepository


class UsuarioRepository(BaseRepository[Usuario]):
    def __init__(self, sesion: AsyncSession) -> None:
        super().__init__(sesion, Usuario)

    async def get(self, id: int) -> Usuario | None:
        """Por id con el rol cargado: el servicio lee `usuario.rol` (sin lazy-load async)."""
        return await self.obtener_con_rol(id)

    async def listar_admins_activos(self) -> list[Usuario]:
        """Admins activos, bloqueados con `FOR UPDATE` hasta el fin de la transaccion.

        El lock serializa las operaciones admin concurrentes (RN-AU-03, C-12 D-03): la segunda
        espera, relee el estado ya confirmado (`populate_existing`) y ve un solo admin.
        """
        filas = await self.sesion.execute(
            select(Usuario)
            .join(Rol, Usuario.rol_id == Rol.id)
            .where(Rol.nombre == "admin", Usuario.activo.is_(True))
            .order_by(Usuario.id)
            .options(selectinload(Usuario.rol))  # populate_existing deja `rol` sin cargar
            .with_for_update(of=Usuario)
            .execution_options(populate_existing=True)
        )
        return list(filas.scalars().all())

    async def obtener_rol(self, nombre: str) -> Rol | None:
        """Rol por nombre (catalogo fijo admin/odontologo/secretaria)."""
        return await self.sesion.scalar(select(Rol).where(Rol.nombre == nombre))

    async def cambiar_rol(self, usuario: Usuario, rol: Rol) -> Usuario:
        """Asigna el rol (FK simple) y deja `usuario.rol` coherente."""
        usuario.rol = rol
        await self.sesion.flush()
        return usuario

    async def tiene_historial(self, usuario_id: int) -> bool:
        """True si el usuario figura como autor de un turno o esta vinculado a un profesional.

        Esas FK son `SET NULL`: borrar al usuario no falla, pero borraria la autoria. Las FK
        `RESTRICT` (caja, recibo, arancel, liquidacion, ...) fallan solas al borrar.
        """
        consulta = select(
            exists().where(Turno.creado_por == usuario_id)
            | exists().where(Profesional.usuario_id == usuario_id)
        )
        return bool(await self.sesion.scalar(consulta))

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
