"""C-07 grupo 2: servicios/lista_espera_servicio.py (D-02, D-03, D-04, D-05).

RED primero con fakes (siempre corre): intentar_ofrecer, expiración 2h,
cascada, idempotencia + lock Redis. Luego GREEN con el servicio real.
Datos 100% ficticios. freezegun para ventana 2h.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]  # backend/app/tests -> backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c04_fakes import FakeTurnoRepo, fabricar_turno  # noqa: E402
from c05_fakes import FakePacienteRepo, fabricar_paciente  # noqa: E402
from c06_fakes import FakeNotifRepo, FakeRedis  # noqa: E402

LUNES_9 = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)  # lunes


def _fabricar_profesional(id, **cambios):
    datos = {"id": id, "matricula": f"DEMO-{id:04d}", "especialidades": "Odontología general", "agenda_config": {"duracion_slot_min": 30, "horario": {"lunes": [["09:00", "13:00"]]}}}
    datos.update(cambios)
    return SimpleNamespace(**datos)


def _fabricar_sillon(id, **cambios):
    datos = {"id": id, "nombre": f"Sillón Demo {id}", "activo": True}
    datos.update(cambios)
    return SimpleNamespace(**datos)


def _fabricar_entrada_espera(id, **cambios):
    datos = {
        "id": id,
        "paciente_id": 1,
        "profesional_id": 1,
        "especialidad": "Odontología general",
        "preferencia_horaria": None,
        "estado": "activa",
        "oferta_expira_en": None,
        "token_oferta_hash": None,
        "oferta_hueco": None,
        "motivo_baja": None,
        "created_at": LUNES_9 + timedelta(minutes=id),
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def _token_valido():
    from app.servicios.reserva_servicio import generar_token
    return generar_token()


def _fabricar_entrada_token(id, **cambios):
    datos = {
        "id": id,
        "paciente_id": 1,
        "profesional_id": 1,
        "especialidad": "Odontología general",
        "preferencia_horaria": None,
        "estado": "activa",
        "oferta_expira_en": None,
        "token_oferta_hash": None,
        "oferta_hueco": None,
        "motivo_baja": None,
        "created_at": LUNES_9 + timedelta(minutes=id),
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


async def _async_profesional(id):
    return _fabricar_profesional(id)


async def _async_sillon(id):
    return _fabricar_sillon(id)


class FakeEsperaRepo:
    """EsperaRepository en memoria para tests del servicio."""

    async def get_by_token_hash(self, token_hash: str):
        for e in self._entradas.values():
            if e.token_oferta_hash == token_hash:
                return e
        return None

    def __init__(self, entradas: list | None = None) -> None:
        self._entradas = {e.id: e for e in entradas or []}
        self._seq = max((e.id for e in self._entradas.values()), default=0)

    async def get(self, id: int):
        return self._entradas.get(id)

    async def crear(self, **datos):
        self._seq += 1
        entrada = SimpleNamespace(id=self._seq, **datos)
        entrada.__dict__.setdefault("estado", "activa")
        self._entradas[entrada.id] = entrada
        return entrada

    async def actualizar(self, entidad, **cambios):
        for campo, valor in cambios.items():
            setattr(entidad, campo, valor)
        return entidad

    async def activas_compatibles(
        self,
        profesional_id: int | None,
        especialidades_profesional: str,
        inicio: datetime,
        preferencia_horaria: dict | None = None,
    ) -> list:
        """Filtro simple en memoria: activa + profesional coincide o es None."""
        salida = []
        for e in self._entradas.values():
            if e.estado != "activa":
                continue
            if profesional_id is not None and e.profesional_id not in (None, profesional_id):
                continue
            salida.append(e)
        return sorted(salida, key=lambda e: e.created_at)


# --- 2.1 intentar_ofrecer ----------------------------------------------------

@pytest.mark.asyncio
async def test_ofrecer_elige_primera_fifo():
    """Task 2.1 RED: primera activa compatible -> ofrecida + expira 2h + hash + snapshot."""
    from app.servicios import lista_espera_servicio as svc

    hueco = {"profesional_id": 1, "sillon_id": 1, "inicio": LUNES_9, "fin": LUNES_9 + timedelta(minutes=30)}
    entradas = [
        _fabricar_entrada_espera(1, profesional_id=1, created_at=LUNES_9),
        _fabricar_entrada_espera(2, profesional_id=1, created_at=LUNES_9 + timedelta(minutes=1)),
    ]
    espera_repo = FakeEsperaRepo(entradas)
    turnos_repo = FakeTurnoRepo()
    class _ProfesionalesRepo:
        async def get(self, id):
            return _fabricar_profesional(id)

    class _SillonesRepo:
        async def get(self, id):
            return _fabricar_sillon(id)

    profesionales_repo = _ProfesionalesRepo()
    sillones_repo = _SillonesRepo()
    pacientes_repo = FakePacienteRepo([fabricar_paciente(id=1)])
    notifs = FakeNotifRepo()
    tienda = FakeRedis()
    cliente = type("C", (), {"enviar": lambda self, d, p, v: SimpleNamespace(estado="enviada", message_id="m1", costo=0.0)})()

    entrada = await svc.intentar_ofrecer(
        espera_repo=espera_repo,
        turnos_repo=turnos_repo,
        profesionales_repo=profesionales_repo,
        sillones_repo=sillones_repo,
        pacientes_repo=pacientes_repo,
        notif_repo=notifs,
        tienda=tienda,
        cliente=cliente,
        hueco=hueco,
        ahora=LUNES_9,
    )
    assert entrada is not None
    assert entrada.id == 1  # primera FIFO
    assert entrada.estado == "ofrecida"
    assert entrada.oferta_expira_en == LUNES_9 + timedelta(hours=2)
    assert entrada.token_oferta_hash is not None
    assert len(entrada.token_oferta_hash) == 64  # sha256
    assert entrada.oferta_hueco == {
        "profesional_id": 1, "sillon_id": 1,
        "inicio": LUNES_9.isoformat(), "fin": (LUNES_9 + timedelta(minutes=30)).isoformat(),
    }


@pytest.mark.asyncio
async def test_ofrecer_sin_compatible_noop():
    """Task 2.1 RED: sin compatible -> no-op con log, nada muta."""
    from app.servicios import lista_espera_servicio as svc

    hueco = {"profesional_id": 99, "sillon_id": 1, "inicio": LUNES_9, "fin": LUNES_9 + timedelta(minutes=30)}
    entradas = [
        _fabricar_entrada_espera(1, profesional_id=1, created_at=LUNES_9),
    ]
    espera_repo = FakeEsperaRepo(entradas)
    turnos_repo = FakeTurnoRepo()
    class _ProfesionalesRepo:
        async def get(self, id):
            return _fabricar_profesional(id)

    class _SillonesRepo:
        async def get(self, id):
            return _fabricar_sillon(id)

    profesionales_repo = _ProfesionalesRepo()
    sillones_repo = _SillonesRepo()
    pacientes_repo = FakePacienteRepo()
    notifs = FakeNotifRepo()
    tienda = FakeRedis()
    cliente = type("C", (), {"enviar": lambda self, d, p, v: SimpleNamespace(estado="enviada", message_id="m1", costo=0.0)})()

    entrada = await svc.intentar_ofrecer(
        espera_repo=espera_repo,
        turnos_repo=turnos_repo,
        profesionales_repo=profesionales_repo,
        sillones_repo=sillones_repo,
        pacientes_repo=pacientes_repo,
        notif_repo=notifs,
        tienda=tienda,
        cliente=cliente,
        hueco=hueco,
        ahora=LUNES_9,
    )
    assert entrada is None
    assert notifs.cantidad_activas() == 0  # no se encoló notificación


# --- 2.2 cascada -------------------------------------------------------------

@pytest.mark.asyncio
async def test_cascada_rechazo_ofrece_siguiente():
    """Task 2.2 RED: rechazo entry 1 -> entry 2 ofrecida mismo hueco."""
    from app.servicios import lista_espera_servicio as svc

    hueco = {"profesional_id": 1, "sillon_id": 1, "inicio": LUNES_9, "fin": LUNES_9 + timedelta(minutes=30)}
    entradas = [
        _fabricar_entrada_espera(1, profesional_id=1, estado="ofrecida", token_oferta_hash="hash-1", oferta_expira_en=LUNES_9 + timedelta(hours=2), created_at=LUNES_9),
        _fabricar_entrada_espera(2, profesional_id=1, estado="activa", created_at=LUNES_9 + timedelta(minutes=1)),
    ]
    espera_repo = FakeEsperaRepo(entradas)
    turnos_repo = FakeTurnoRepo()
    class _ProfesionalesRepo:
        async def get(self, id):
            return _fabricar_profesional(id)

    class _SillonesRepo:
        async def get(self, id):
            return _fabricar_sillon(id)

    profesionales_repo = _ProfesionalesRepo()
    sillones_repo = _SillonesRepo()
    pacientes_repo = FakePacienteRepo()
    notifs = FakeNotifRepo()
    tienda = FakeRedis()
    cliente = type("C", (), {"enviar": lambda self, d, p, v: SimpleNamespace(estado="enviada", message_id="m1", costo=0.0)})()

    # Rechazar entry 1
    e1 = await espera_repo.get(1)
    e1.estado = "vencida"
    e1.motivo_baja = "rechazo_paciente"
    e1.token_oferta_hash = None

    entrada = await svc.intentar_ofrecer(
        espera_repo=espera_repo,
        turnos_repo=turnos_repo,
        profesionales_repo=profesionales_repo,
        sillones_repo=sillones_repo,
        pacientes_repo=pacientes_repo,
        notif_repo=notifs,
        tienda=tienda,
        cliente=cliente,
        hueco=hueco,
        ahora=LUNES_9 + timedelta(hours=2, minutes=1),
    )
    assert entrada is not None
    assert entrada.id == 2  # entry 2 ofrecida
    assert entrada.estado == "ofrecida"


@pytest.mark.asyncio
async def test_cascada_hueco_tomado_salta():
    """Task 2.2: oferta no bloqueante (D-03); hueco tomado al aceptar -> vencida
    'hueco_tomado' y la cascada ofrece al siguiente en el mismo llamado.

    Corrige el RED original: con el hueco ocupado "para todos" la 2ª entry no
    puede ofrecerse tras quemar a la 1ª sin vaciar la cola; el hueco se
    arbitra recién al aceptar (EXCLUDE de DB), como pide la spec.
    """
    from app.servicios import lista_espera_servicio as svc

    hueco = {"profesional_id": 1, "sillon_id": 1, "inicio": LUNES_9, "fin": LUNES_9 + timedelta(minutes=30)}
    entradas = [
        _fabricar_entrada_espera(1, profesional_id=1, estado="activa", created_at=LUNES_9),
        _fabricar_entrada_espera(2, profesional_id=1, estado="activa", created_at=LUNES_9 + timedelta(minutes=1)),
    ]
    espera_repo = FakeEsperaRepo(entradas)
    turnos_repo = FakeTurnoRepo()
    mundo = dict(
        espera_repo=espera_repo, turnos_repo=turnos_repo,
        profesionales_repo=type("PR", (), {"get": staticmethod(_async_profesional)})(),
        sillones_repo=type("SR", (), {"get": staticmethod(_async_sillon)})(),
        pacientes_repo=FakePacienteRepo([fabricar_paciente(id=1)]),
        notif_repo=FakeNotifRepo(), tienda=FakeRedis(),
        cliente=type("C", (), {"enviar": lambda self, d, p, v: SimpleNamespace(estado="enviada", message_id="m1", costo=0.0)})(),
    )

    oferta_a = LUNES_9 - timedelta(hours=3)  # el hueco es futuro respecto de la oferta
    primera = await svc.intentar_ofrecer(hueco=hueco, ahora=oferta_a, **mundo)
    assert primera.id == 1 and primera.estado == "ofrecida"
    # el hueco se ocupa entre la oferta y la aceptación
    await turnos_repo.crear(
        paciente_id=9, profesional_id=1, sillon_id=1, inicio=LUNES_9,
        fin=LUNES_9 + timedelta(minutes=30), estado="confirmado",
        origen="secretaria", sobre_turno=False,
    )

    with pytest.raises(svc.HuecoOcupadoError):
        await svc.aceptar_por_token(
            token_hash=primera.token_oferta_hash, ahora=oferta_a + timedelta(minutes=30), **mundo,
        )

    e1 = await espera_repo.get(1)
    assert e1.estado == "vencida"
    assert e1.motivo_baja == "hueco_tomado"
    e2 = await espera_repo.get(2)
    assert e2.estado == "ofrecida"  # la cascada siguió al siguiente


# --- 2.3 idempotencia + lock -------------------------------------------------

@pytest.mark.asyncio
async def test_doble_disparo_una_oferta():
    """Task 2.3 RED: dos intentar_ofrecer mismo hueco -> una sola ofrecida."""
    from app.servicios import lista_espera_servicio as svc

    hueco = {"profesional_id": 1, "sillon_id": 1, "inicio": LUNES_9, "fin": LUNES_9 + timedelta(minutes=30)}
    entradas = [
        _fabricar_entrada_espera(1, profesional_id=1, created_at=LUNES_9),
    ]
    espera_repo = FakeEsperaRepo(entradas)
    turnos_repo = FakeTurnoRepo()
    class _ProfesionalesRepo:
        async def get(self, id):
            return _fabricar_profesional(id)

    class _SillonesRepo:
        async def get(self, id):
            return _fabricar_sillon(id)

    profesionales_repo = _ProfesionalesRepo()
    sillones_repo = _SillonesRepo()
    pacientes_repo = FakePacienteRepo()
    notifs = FakeNotifRepo()
    tienda = FakeRedis()
    cliente = type("C", (), {"enviar": lambda self, d, p, v: SimpleNamespace(estado="enviada", message_id="m1", costo=0.0)})()

    e1 = await svc.intentar_ofrecer(
        espera_repo=espera_repo, turnos_repo=turnos_repo,
        profesionales_repo=profesionales_repo, sillones_repo=sillones_repo,
        pacientes_repo=pacientes_repo, notif_repo=notifs, tienda=tienda,
        cliente=cliente, hueco=hueco, ahora=LUNES_9,
    )
    e2 = await svc.intentar_ofrecer(
        espera_repo=espera_repo, turnos_repo=turnos_repo,
        profesionales_repo=profesionales_repo, sillones_repo=sillones_repo,
        pacientes_repo=pacientes_repo, notif_repo=notifs, tienda=tienda,
        cliente=cliente, hueco=hueco, ahora=LUNES_9,
    )
    assert e1 is not None
    assert e2 is None  # segundo es skip (entry ya ofrecida)
    ofrecidas = [e for e in espera_repo._entradas.values() if e.estado == "ofrecida"]
    assert len(ofrecidas) == 1
