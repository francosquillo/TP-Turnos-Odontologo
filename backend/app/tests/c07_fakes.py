"""Fakes C-07: repo de espera en memoria + app FastAPI armada con fakes.

Sin PG/Redis: los tests HTTP y de worker usan estos fakes (siempre corren).
El repo falso reutiliza los predicados REALES de `espera_repo`
(`_especialidad_compatible`, `_cumple_preferencia`) para no divergir del SQL.
Datos 100% ficticios.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

BASE_CREATED = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)


class FakeEsperaRepo:
    """EsperaRepository en memoria (misma interfaz que el real)."""

    def __init__(self, entradas: list | None = None) -> None:
        self._entradas: dict[int, SimpleNamespace] = {}
        self._seq = 0
        for e in entradas or []:
            self._seq = max(self._seq, e.id)
            self._entradas[e.id] = e
        self.falla = False  # simula caída del repo (la cancelación no debe revertirse)

    def _chequear(self) -> None:
        if self.falla:
            raise RuntimeError("repo espera caído (fake)")

    async def get(self, id: int):
        self._chequear()
        return self._entradas.get(id)

    async def crear(self, **datos):
        self._chequear()
        self._seq += 1
        base = {
            "profesional_id": None, "especialidad": None,
            "preferencia_horaria": None, "estado": "activa",
            "oferta_expira_en": None, "token_oferta_hash": None,
            "oferta_hueco": None, "motivo_baja": None,
            "created_at": BASE_CREATED + timedelta(minutes=self._seq),
        }
        base.update(datos)
        entrada = SimpleNamespace(id=self._seq, **base)
        self._entradas[entrada.id] = entrada
        return entrada

    async def actualizar(self, entidad, **cambios):
        self._chequear()
        for campo, valor in cambios.items():
            setattr(entidad, campo, valor)
        return entidad

    async def listar_fifo(self, estado=None, limit=100, offset=0):
        self._chequear()
        filas = [e for e in self._entradas.values() if estado is None or e.estado == estado]
        return sorted(filas, key=lambda e: (e.created_at, e.id))[offset:offset + limit]

    async def activas_compatibles(
        self, profesional_id=None, especialidades_profesional="", inicio=None,
        preferencia_horaria=None,
    ):
        from app.repos.espera_repo import _cumple_preferencia, _especialidad_compatible

        self._chequear()
        salida = [
            e for e in self._entradas.values()
            if e.estado == "activa"
            and (profesional_id is None or e.profesional_id in (None, profesional_id))
            and _especialidad_compatible(e.especialidad, especialidades_profesional)
            and _cumple_preferencia(e.preferencia_horaria, inicio)
        ]
        return sorted(salida, key=lambda e: (e.created_at, e.id))

    async def get_by_token_hash(self, token_hash: str):
        self._chequear()
        return next(
            (e for e in self._entradas.values() if e.token_oferta_hash == token_hash),
            None,
        )

    async def ofrecidas_vencidas(self, ahora: datetime):
        self._chequear()
        filas = [
            e for e in self._entradas.values()
            if e.estado == "ofrecida" and e.oferta_expira_en is not None
            and e.oferta_expira_en <= ahora
        ]
        return sorted(filas, key=lambda e: (e.oferta_expira_en, e.id))


class FakeSesion:
    """AsyncSession mínima: cuenta commits/rollbacks."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeProfesionales:
    """Profesionales con especialidad demo; `get` devuelve None si no existe."""

    def __init__(self, ids=(1,), especialidades="Odontología general") -> None:
        self._ids = set(ids)
        self._esp = especialidades

    async def get(self, id: int):
        if id not in self._ids:
            return None
        return SimpleNamespace(
            id=id, matricula=f"DEMO-{id:04d}", especialidades=self._esp,
            agenda_config={"duracion_slot_min": 30, "horario": {"lunes": [["08:00", "12:00"]]}},
        )


class FakeSillones:
    def __init__(self, ids=(1,)) -> None:
        self._ids = set(ids)

    async def get(self, id: int):
        return SimpleNamespace(id=id, nombre=f"Sillón {id}", activo=True) if id in self._ids else None


def fabricar_entry(id: int, **cambios) -> SimpleNamespace:
    datos = {
        "id": id, "paciente_id": 1, "profesional_id": 1, "especialidad": None,
        "preferencia_horaria": None, "estado": "activa", "oferta_expira_en": None,
        "token_oferta_hash": None, "oferta_hueco": None, "motivo_baja": None,
        "created_at": BASE_CREATED + timedelta(minutes=id),
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def armar_app(*, usuarios, turnos=(), pacientes=(), entradas=(), profesionales=None,
              sillones=None, cliente=None, espera=None):
    """FastAPI con TODAS las dependencias reales reemplazadas por fakes."""
    from c03_fakes import FakeRepo
    from c04_fakes import FakeEntidadRepo, FakeTurnoRepo
    from c06_fakes import CuentaCliente, FakeNotifRepo, FakeRedis
    from httpx import ASGITransport, AsyncClient

    from app.api.espera_hook import get_cliente_espera, get_espera_repo
    from app.api.notificaciones import get_notif_repo
    from app.api.turnos import (
        get_paciente_repo, get_profesional_repo, get_sillon_repo, get_turno_repo,
    )
    from app.core.deps import get_db, get_redis, get_usuario_repo
    from app.core.security import crear_access_token
    from app.main import create_app

    app = create_app()
    mundo = SimpleNamespace(
        turnos=FakeTurnoRepo(list(turnos)),
        pacientes=FakeEntidadRepo(list(pacientes)),
        profesionales=profesionales or FakeProfesionales(),
        sillones=sillones or FakeSillones(),
        espera=espera or FakeEsperaRepo(list(entradas)),
        notifs=FakeNotifRepo(), tienda=FakeRedis(),
        cliente=cliente or CuentaCliente(), sesion=FakeSesion(),
    )
    app.dependency_overrides[get_usuario_repo] = lambda: FakeRepo(list(usuarios))
    app.dependency_overrides[get_turno_repo] = lambda: mundo.turnos
    app.dependency_overrides[get_paciente_repo] = lambda: mundo.pacientes
    app.dependency_overrides[get_profesional_repo] = lambda: mundo.profesionales
    app.dependency_overrides[get_sillon_repo] = lambda: mundo.sillones
    app.dependency_overrides[get_espera_repo] = lambda: mundo.espera
    app.dependency_overrides[get_notif_repo] = lambda: mundo.notifs
    app.dependency_overrides[get_cliente_espera] = lambda: mundo.cliente
    app.dependency_overrides[get_redis] = lambda: mundo.tienda

    async def _db():
        yield mundo.sesion

    app.dependency_overrides[get_db] = _db

    def bearer(usuario_id: int, rol: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {crear_access_token(usuario_id, rol)}"}

    cli = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return app, cli, bearer, mundo

