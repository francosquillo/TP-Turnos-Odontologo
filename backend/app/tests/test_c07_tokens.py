"""C-07 grupo 3: tokens + aceptar/rechazar + conversión (D-04, D-06).

RED primero con fakes (siempre corre): token desconocido 404, reuso 410,
expirado 410+cascada, conversión crea confirmado origen=lista_espera,
hueco tomado → 409+cascada, rechazo → vencida+cascada.
Luego GREEN con endpoints + servicio. freezegun para ventana 2h.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from types import SimpleNamespace

import pytest
from freezegun import freeze_time

BACKEND_DIR = Path(__file__).resolve().parents[1]  # backend/app/tests -> backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c04_fakes import FakeTurnoRepo, fabricar_turno  # noqa: E402
from c05_fakes import FakePacienteRepo, fabricar_paciente  # noqa: E402
from c06_fakes import FakeNotifRepo, FakeRedis  # noqa: E402

LUNES_9 = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


class FakeEsperaRepoTokens:
    """EsperaRepository en memoria para tests de tokens/conversión."""

    def __init__(self, entradas: list | None = None) -> None:
        self._entradas = {e.id: e for e in entradas or []}
        self._seq = max((e.id for e in self._entradas.values()), default=0)
        self.actualizados = []

    async def get(self, id: int):
        return self._entradas.get(id)

    async def crear(self, **datos):
        self._seq += 1
        entrada = SimpleNamespace(id=self._seq, **datos)
        self._entradas[entrada.id] = entrada
        return entrada

    async def actualizar(self, entidad, **cambios):
        self.actualizados.append((entidad.id, dict(cambios)))
        for campo, valor in cambios.items():
            setattr(entidad, campo, valor)
        return entidad

    async def activas_compatibles(
        self, profesional_id=None, especialidades_profesional="", inicio=None,
        preferencia_horaria=None,
    ) -> list:
        salida = [e for e in self._entradas.values() if e.estado == "activa"]
        return sorted(salida, key=lambda e: e.created_at)

    async def get_by_token_hash(self, token_hash: str):
        for e in self._entradas.values():
            if e.token_oferta_hash == token_hash:
                return e
        return None


# --- helpers -----------------------------------------------------------------

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


class _AsyncProfesionalesRepo:
    async def get(self, id):
        return SimpleNamespace(id=id, especialidades="Odontología general")


class _AsyncSillonesRepo:
    async def get(self, id):
        return SimpleNamespace(id=id)


def _token_valido():
    from app.servicios.reserva_servicio import generar_token
    return generar_token()


# --- 3.1 token desconocido → 404 ---------------------------------------------

@pytest.mark.asyncio
async def test_aceptar_token_desconocido_404():
    """Task 3.1 RED: token jamás emitido -> TokenDesconocidoError (404)."""
    from app.servicios import lista_espera_servicio as svc

    espera_repo = FakeEsperaRepoTokens()
    turnos_repo = FakeTurnoRepo()
    pacientes_repo = FakePacienteRepo()
    profesionales_repo = type("PR", (), {"get": lambda self, id: SimpleNamespace(id=1, especialidades="Odontología general")})()
    sillones_repo = type("SR", (), {"get": lambda self, id: SimpleNamespace(id=1)})()
    notifs = FakeNotifRepo()
    tienda = FakeRedis()
    cliente = type("C", (), {"enviar": lambda self, d, p, v: SimpleNamespace(estado="enviada", message_id="m1", costo=0.0)})()

    with pytest.raises(svc.TokenDesconocidoError):
        await svc.aceptar_por_token(
            espera_repo=espera_repo,
            turnos_repo=turnos_repo,
            profesionales_repo=profesionales_repo,
            sillones_repo=sillones_repo,
            pacientes_repo=pacientes_repo,
            notif_repo=notifs,
            tienda=tienda,
            cliente=cliente,
            token=_token_valido(),
            ahora=LUNES_9,
        )


# --- 3.1 reuso → 410 ---------------------------------------------------------

@pytest.mark.asyncio
async def test_aceptar_token_reusado_410():
    """Task 3.1 RED: token ya consumido (entry convertida) -> 410, sin mutar."""
    from app.servicios import lista_espera_servicio as svc
    from app.servicios.reserva_servicio import hash_token

    token = _token_valido()
    token_hash = hash_token(token)
    entrada = _fabricar_entrada_token(
        1, estado="convertida", token_oferta_hash=token_hash,
    )
    espera_repo = FakeEsperaRepoTokens([entrada])
    turnos_repo = FakeTurnoRepo()
    pacientes_repo = FakePacienteRepo()
    profesionales_repo = _AsyncProfesionalesRepo()
    sillones_repo = _AsyncSillonesRepo()
    notifs = FakeNotifRepo()
    tienda = FakeRedis()
    cliente = type("C", (), {"enviar": lambda self, d, p, v: SimpleNamespace(estado="enviada", message_id="m1", costo=0.0)})()

    with pytest.raises(svc.TokenUsadoError):
        await svc.aceptar_por_token(
            espera_repo=espera_repo, turnos_repo=turnos_repo,
            profesionales_repo=profesionales_repo, sillones_repo=sillones_repo,
            pacientes_repo=pacientes_repo, notif_repo=notifs, tienda=tienda,
            cliente=cliente, token=token, ahora=LUNES_9,
        )
    e1 = await espera_repo.get(1)
    assert e1.estado == "convertida"  # sin mutar


# --- 3.1 expirado → 410 + cascada --------------------------------------------

@pytest.mark.asyncio
async def test_aceptar_token_expirado_410_y_cascada():
    """Task 3.1 RED: +2h01 -> 410, entry vencida, siguiente ofrecida."""
    from app.servicios import lista_espera_servicio as svc
    from app.servicios.reserva_servicio import hash_token

    token = _token_valido()
    token_hash = hash_token(token)
    ahora = LUNES_9
    entrada1 = _fabricar_entrada_token(
        1, estado="ofrecida", token_oferta_hash=token_hash,
        oferta_expira_en=ahora + timedelta(hours=2),
        oferta_hueco={
            "profesional_id": 1, "sillon_id": 1,
            "inicio": ahora.isoformat(),
            "fin": (ahora + timedelta(minutes=30)).isoformat(),
        },
        creado_por=None,
    )
    entrada2 = _fabricar_entrada_token(
        2, profesional_id=1, estado="activa", created_at=ahora + timedelta(minutes=1),
    )
    espera_repo = FakeEsperaRepoTokens([entrada1, entrada2])
    turnos_repo = FakeTurnoRepo()
    pacientes_repo = FakePacienteRepo()
    profesionales_repo = _AsyncProfesionalesRepo()
    sillones_repo = _AsyncSillonesRepo()
    notifs = FakeNotifRepo()
    tienda = FakeRedis()
    cliente = type("C", (), {"enviar": lambda self, d, p, v: SimpleNamespace(estado="enviada", message_id="m1", costo=0.0)})()

    momento_expirado = ahora + timedelta(hours=2, minutes=1)
    with freeze_time(momento_expirado):
        with pytest.raises(svc.TokenExpiradoError):
            await svc.aceptar_por_token(
                espera_repo=espera_repo, turnos_repo=turnos_repo,
                profesionales_repo=profesionales_repo, sillones_repo=sillones_repo,
                pacientes_repo=pacientes_repo, notif_repo=notifs, tienda=tienda,
                cliente=cliente, token=token, ahora=momento_expirado,
            )
    e1 = await espera_repo.get(1)
    assert e1.estado == "vencida"  # expirada
    e2 = await espera_repo.get(2)
    assert e2.estado == "ofrecida"  # cascada al siguiente


# --- 3.2 conversión crea confirmado ------------------------------------------

@pytest.mark.asyncio
async def test_conversion_crea_confirmado_origen_lista_espera():
    """Task 3.2 RED: aceptar válido -> crear_turno(origen=lista_espera) + cambiar_estado→confirmado."""
    from app.servicios import lista_espera_servicio as svc
    from app.servicios.reserva_servicio import hash_token

    token = _token_valido()
    token_hash = hash_token(token)
    ahora = LUNES_9
    entrada = _fabricar_entrada_token(
        1, estado="ofrecida", token_oferta_hash=token_hash,
        oferta_expira_en=ahora + timedelta(hours=2),
        oferta_hueco={
            "profesional_id": 1, "sillon_id": 1,
            "inicio": ahora.isoformat(),
            "fin": (ahora + timedelta(minutes=30)).isoformat(),
        },
    )
    espera_repo = FakeEsperaRepoTokens([entrada])
    turnos_repo = FakeTurnoRepo()
    pacientes_repo = FakePacienteRepo([fabricar_paciente(id=1, nombre="Ana", apellido="Ficticia")])
    profesionales_repo = _AsyncProfesionalesRepo()
    sillones_repo = _AsyncSillonesRepo()
    notifs = FakeNotifRepo()
    tienda = FakeRedis()
    cliente = type("C", (), {"enviar": lambda self, d, p, v: SimpleNamespace(estado="enviada", message_id="m1", costo=0.0)})()

    turno = await svc.aceptar_por_token(
        espera_repo=espera_repo, turnos_repo=turnos_repo,
        profesionales_repo=profesionales_repo, sillones_repo=sillones_repo,
        pacientes_repo=pacientes_repo, notif_repo=notifs, tienda=tienda,
        cliente=cliente, token=token, ahora=ahora - timedelta(hours=1),
    )
    assert turno is not None
    assert turno.estado == "confirmado"
    assert turno.origen == "lista_espera"
    e1 = await espera_repo.get(1)
    assert e1.estado == "convertida"
    assert e1.token_oferta_hash == token_hash  # tombstone: reusar el link es 410, no 404


# --- 3.2 conversión hueco tomado → 409 + cascada -----------------------------

@pytest.mark.asyncio
async def test_conversion_hueco_tomado_409_y_cascada():
    """Task 3.2 RED: hueco ocupado al aceptar -> 409 + entry vencida + siguiente."""
    from app.servicios import lista_espera_servicio as svc
    from app.servicios.reserva_servicio import hash_token
    from app.servicios.agenda_servicio import HuecoOcupadoError

    token = _token_valido()
    token_hash = hash_token(token)
    ahora = LUNES_9
    entrada1 = _fabricar_entrada_token(
        1, estado="ofrecida", token_oferta_hash=token_hash,
        oferta_expira_en=ahora + timedelta(hours=2),
        oferta_hueco={
            "profesional_id": 1, "sillon_id": 1,
            "inicio": ahora.isoformat(),
            "fin": (ahora + timedelta(minutes=30)).isoformat(),
        },
    )
    entrada2 = _fabricar_entrada_token(
        2, profesional_id=1, estado="activa", created_at=ahora + timedelta(minutes=1),
    )
    espera_repo = FakeEsperaRepoTokens([entrada1, entrada2])
    # TurnoRepo que reporta solapamiento al crear (hueco tomado)
    turno_ocupado = fabricar_turno(id=1, profesional_id=1, sillon_id=1, inicio=ahora, fin=ahora + timedelta(minutes=30), estado="confirmado")
    turnos_repo = FakeTurnoRepo([turno_ocupado])
    pacientes_repo = FakePacienteRepo([fabricar_paciente(id=1)])
    profesionales_repo = _AsyncProfesionalesRepo()
    sillones_repo = _AsyncSillonesRepo()
    notifs = FakeNotifRepo()
    tienda = FakeRedis()
    cliente = type("C", (), {"enviar": lambda self, d, p, v: SimpleNamespace(estado="enviada", message_id="m1", costo=0.0)})()

    with pytest.raises(svc.HuecoOcupadoError):
        await svc.aceptar_por_token(
            espera_repo=espera_repo, turnos_repo=turnos_repo,
            profesionales_repo=profesionales_repo, sillones_repo=sillones_repo,
            pacientes_repo=pacientes_repo, notif_repo=notifs, tienda=tienda,
            cliente=cliente, token=token, ahora=ahora - timedelta(hours=1),
        )
    e1 = await espera_repo.get(1)
    assert e1.estado == "vencida"
    assert e1.motivo_baja == "hueco_tomado"
    e2 = await espera_repo.get(2)
    assert e2.estado == "ofrecida"  # cascada


# --- 3.3 rechazo → vencida + cascada -----------------------------------------

@pytest.mark.asyncio
async def test_rechazo_libera_y_ofrece_siguiente():
    """Task 3.3 RED: rechazar entry 1 -> vencida 'rechazo_paciente' + entry 2 ofrecida."""
    from app.servicios import lista_espera_servicio as svc

    ahora = LUNES_9
    entrada1 = _fabricar_entrada_token(
        1, estado="ofrecida", token_oferta_hash="hash-1",
        oferta_expira_en=ahora + timedelta(hours=2),
        oferta_hueco={
            "profesional_id": 1, "sillon_id": 1,
            "inicio": ahora.isoformat(),
            "fin": (ahora + timedelta(minutes=30)).isoformat(),
        },
        creado_por=None,
    )
    entrada2 = _fabricar_entrada_token(
        2, profesional_id=1, estado="activa", created_at=ahora + timedelta(minutes=1),
    )
    espera_repo = FakeEsperaRepoTokens([entrada1, entrada2])
    turnos_repo = FakeTurnoRepo()
    pacientes_repo = FakePacienteRepo()
    profesionales_repo = _AsyncProfesionalesRepo()
    sillones_repo = _AsyncSillonesRepo()
    notifs = FakeNotifRepo()
    tienda = FakeRedis()
    cliente = type("C", (), {"enviar": lambda self, d, p, v: SimpleNamespace(estado="enviada", message_id="m1", costo=0.0)})()

    resultado = await svc.rechazar_por_token(
        espera_repo=espera_repo, turnos_repo=turnos_repo,
        profesionales_repo=profesionales_repo, sillones_repo=sillones_repo,
        pacientes_repo=pacientes_repo, notif_repo=notifs, tienda=tienda,
        cliente=cliente, token_hash="hash-1", ahora=ahora,
    )
    assert resultado is True
    e1 = await espera_repo.get(1)
    assert e1.estado == "vencida"
    assert e1.motivo_baja == "rechazo_paciente"
    e2 = await espera_repo.get(2)
    assert e2.estado == "ofrecida"  # cascada al siguiente


# 5.2 (sin-PHI y sin-numero) vive en test_c07_aviso.py: ahi se ejercita la oferta real.
