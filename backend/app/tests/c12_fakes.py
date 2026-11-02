"""Fakes C-12: repo de usuarios con alta/rol/historial y sesion con commit/rollback contados.

Permiten probar el router y el servicio de usuarios sin Postgres. Lo que depende del motor
(lock `FOR UPDATE`, FK reales, indice unico) se prueba aparte contra Postgres real.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from c03_fakes import FakeRepo, fabricar_usuario


class FakeAuditoria:
    """Repo de auditoria en memoria: guarda los eventos en orden de registro."""

    def __init__(self) -> None:
        self.eventos: list[SimpleNamespace] = []

    async def registrar(self, *, actor_id, accion, objeto_tipo, objeto_id=None, detalle=None):
        evento = SimpleNamespace(
            id=len(self.eventos) + 1, actor_id=actor_id, accion=accion, objeto_tipo=objeto_tipo,
            objeto_id=objeto_id, detalle=dict(detalle or {}),
            created_at=datetime(2026, 11, 2, 15, 0, len(self.eventos), tzinfo=timezone.utc),
        )
        self.eventos.append(evento)
        return evento

    async def listar_recientes(self, limit: int = 50, offset: int = 0):
        return list(reversed(self.eventos))[offset:offset + limit]


def override_auditoria(app) -> FakeAuditoria:
    """Reemplaza el repo de auditoria del app por uno en memoria y lo devuelve."""
    from app.core.deps import get_auditoria_repo

    fake = FakeAuditoria()
    app.dependency_overrides[get_auditoria_repo] = lambda: fake
    return fake


class FakeDb:
    """Sesion minima: cuenta commits y rollbacks del request."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeRepoAdmin(FakeRepo):
    """FakeRepo + alta, cambio de rol e historial. `con_fk` simula una FK RESTRICT al borrar."""

    def __init__(self, usuarios=None, con_historial=(), con_fk=()) -> None:
        super().__init__(usuarios)
        self.con_historial = set(con_historial)
        self.con_fk = set(con_fk)
        self._siguiente = max(self._usuarios, default=0) + 1

    async def obtener_rol(self, nombre: str):
        return SimpleNamespace(id=hash(nombre) % 1000, nombre=nombre)

    async def crear(self, **datos):
        if await self.obtener_por_email(datos["email"]) is not None:
            raise IntegrityError("INSERT usuario", {}, Exception("uq_usuario_email_lower"))
        usuario = SimpleNamespace(id=self._siguiente, activo=True, **datos)
        self._siguiente += 1
        self._usuarios[usuario.id] = usuario
        return usuario

    async def cambiar_rol(self, usuario, rol):
        usuario.rol = SimpleNamespace(nombre=rol.nombre)
        return usuario

    async def tiene_historial(self, usuario_id: int) -> bool:
        return usuario_id in self.con_historial

    async def eliminar(self, entidad) -> None:
        if entidad.id in self.con_fk:
            raise IntegrityError("DELETE usuario", {}, Exception("fk RESTRICT"))
        await super().eliminar(entidad)


def app_admin_con(repo: FakeRepoAdmin):
    """App con repo y sesion falsos. Devuelve (app, cliente, bearer, db)."""
    from httpx import ASGITransport, AsyncClient

    from app.core.deps import get_db, get_usuario_repo
    from app.core.security import crear_access_token
    from app.main import create_app

    app = create_app()
    db = FakeDb()

    async def _db():
        yield db

    app.dependency_overrides[get_usuario_repo] = lambda: repo
    app.dependency_overrides[get_db] = _db
    db.auditoria = override_auditoria(app)
    cliente = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    def bearer(usuario_id: int, rol: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {crear_access_token(usuario_id, rol)}"}

    return app, cliente, bearer, db


__all__ = ["FakeAuditoria", "override_auditoria", "FakeDb", "FakeRepoAdmin", "app_admin_con", "fabricar_usuario"]
