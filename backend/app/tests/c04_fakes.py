"""Fakes C-04: repos en memoria para servicio y HTTP sin PG (patron c03_fakes).

FakeTurnoRepo replica el predicado D-01 (activos no-sobreturno) y serializa
crear() con lock (como el EXCLUDE en PG): en carrera, el segundo ve el
solapamiento y falla en vez de duplicar.
"""
import asyncio
from datetime import datetime
from types import SimpleNamespace

ESTADOS_ACTIVOS = ("pendiente", "confirmado", "asistido")

AGENDA_LUNES = {
    "duracion_slot_min": 30,
    "horario": {"lunes": [["08:00", "12:00"]]},
}


def _chocan(a_ini: datetime, a_fin: datetime, b_ini: datetime, b_fin: datetime) -> bool:
    return a_ini < b_fin and a_fin > b_ini


def _es_activo(turno) -> bool:
    return turno.sobre_turno is False and turno.estado in ESTADOS_ACTIVOS


class FakeTurnoRepo:
    """TurnoRepository en memoria (misma interfaz usada por el servicio)."""

    def __init__(self, turnos: list | None = None) -> None:
        self._turnos: dict[int, SimpleNamespace] = {}
        self._seq = 0
        self._lock = asyncio.Lock()
        for turno in turnos or []:
            self._seq = max(self._seq, turno.id)
            self._turnos[turno.id] = turno

    async def get(self, id: int):
        return self._turnos.get(id)

    async def crear(self, **datos):
        from app.servicios.agenda_servicio import HuecoOcupadoError

        async with self._lock:
            for turno in self._turnos.values():
                if not _es_activo(turno):
                    continue
                if turno.profesional_id != datos.get("profesional_id") and turno.sillon_id != datos.get("sillon_id"):
                    continue
                if _chocan(turno.inicio, turno.fin, datos["inicio"], datos["fin"]):
                    if datos.get("sobre_turno") is True:
                        continue
                    raise HuecoOcupadoError("hueco ocupado", alternativas=[])
            from datetime import datetime, timezone

            self._seq += 1
            turno = SimpleNamespace(id=self._seq, **datos)
            turno.__dict__.setdefault("estado", "pendiente")
            turno.__dict__.setdefault("origen", "secretaria")
            turno.__dict__.setdefault("sobre_turno", False)
            turno.__dict__.setdefault("token_confirmacion_hash", None)
            turno.__dict__.setdefault(
                "created_at", datetime.now(timezone.utc)
            )
            self._turnos[turno.id] = turno
            return turno

    async def actualizar(self, entidad, **cambios):
        for campo, valor in cambios.items():
            setattr(entidad, campo, valor)
        return entidad

    async def hay_solapamiento(
        self, profesional_id, sillon_id, inicio, fin, excluir_id=None
    ) -> bool:
        for turno in self._turnos.values():
            if excluir_id is not None and turno.id == excluir_id:
                continue
            if not _es_activo(turno):
                continue
            if turno.profesional_id != profesional_id and turno.sillon_id != sillon_id:
                continue
            if _chocan(turno.inicio, turno.fin, inicio, fin):
                return True
        return False

    async def activos_en_rango(
        self, desde, hasta, profesional_id=None, sillon_id=None, excluir_id=None
    ):
        salida = []
        for turno in self._turnos.values():
            if excluir_id is not None and turno.id == excluir_id:
                continue
            if not _es_activo(turno):
                continue
            if profesional_id is not None and turno.profesional_id != profesional_id:
                continue
            if sillon_id is not None and turno.sillon_id != sillon_id:
                continue
            if _chocan(turno.inicio, turno.fin, desde, hasta):
                salida.append(turno)
        return sorted(salida, key=lambda t: t.inicio)

    async def listar_periodo(
        self, desde, hasta, profesional_id=None, sillon_id=None, solo_activos=True
    ):
        salida = []
        for turno in self._turnos.values():
            if solo_activos and not _es_activo(turno):
                continue
            if profesional_id is not None and turno.profesional_id != profesional_id:
                continue
            if sillon_id is not None and turno.sillon_id != sillon_id:
                continue
            if _chocan(turno.inicio, turno.fin, desde, hasta):
                salida.append(turno)
        return sorted(salida, key=lambda t: t.inicio)


class FakeEntidadRepo:
    """Repo generico por id (pacientes / sillones / profesionales base)."""

    def __init__(self, entidades: list | None = None) -> None:
        self._entidades = {e.id: e for e in entidades or []}

    async def get(self, id: int):
        return self._entidades.get(id)


class FakeProfesionalRepo(FakeEntidadRepo):
    """Profesionales con agenda_config demo (lunes 08-12, slots 30)."""

    async def get(self, id: int):
        entidad = self._entidades.get(id)
        if entidad is None:
            return None
        if getattr(entidad, "agenda_config", None) is None:
            entidad.agenda_config = dict(AGENDA_LUNES)
        return entidad

    async def por_usuario_id(self, usuario_id: int):
        for entidad in self._entidades.values():
            if getattr(entidad, "usuario_id", None) == usuario_id:
                return await self.get(entidad.id)
        return None


def fabricar_turno(id: int = 1, **cambios) -> SimpleNamespace:
    from datetime import timedelta, timezone

    base = datetime(2026, 10, 12, 8, 0, tzinfo=timezone.utc)  # lunes
    datos = {
        "id": id,
        "paciente_id": 1,
        "profesional_id": 1,
        "sillon_id": 1,
        "inicio": base,
        "fin": base + timedelta(minutes=30),
        "estado": "confirmado",
        "origen": "secretaria",
        "sobre_turno": False,
        "motivo_sobreturno": None,
        "motivo_cancelacion": None,
        "creado_por": 7,
        "created_at": base,
        "token_confirmacion_hash": None,
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def fabricar_entidad(id: int = 1, **cambios) -> SimpleNamespace:
    datos = {"id": id}
    datos.update(cambios)
    return SimpleNamespace(**datos)
