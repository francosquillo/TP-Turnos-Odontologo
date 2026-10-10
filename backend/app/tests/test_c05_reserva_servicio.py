"""C-05 grupo 1: servicio reserva (token, expiracion, paciente minimo).

TDD estricto: RED primero (modulo inexistente), GREEN minimo, TRIANGULATE con
happy + edge. Sin PG: fakes C-05 (FakePacienteRepo, FakeTurnoRepoC05). Los
tests contra PG real viven en test_c05_reserva_pg.py (skipean sin Docker).
Datos 100% ficticios. TZ America/Argentina/Buenos_Aires.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c03_fakes import FakeStore  # noqa: E402
from c04_fakes import FakeEntidadRepo, FakeProfesionalRepo, fabricar_entidad  # noqa: E402
from c05_fakes import FakePacienteRepo, FakeTurnoRepoC05, fabricar_paciente  # noqa: E402

LUNES_9_BA = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)  # 09:00 BA
AHORA_BASE = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _repos(pacientes=None, turnos=None):
    return (
        FakeTurnoRepoC05(turnos),
        FakePacienteRepo(pacientes),
        FakeProfesionalRepo([fabricar_entidad(1)]),
        FakeEntidadRepo([fabricar_entidad(1)]),
    )


# --- 1.1 token puro ---------------------------------------------------------

def test_token_hash_no_expone_plano():
    """Task 1.1 RED: hash determinista que nunca contiene el token plano."""
    from app.servicios import reserva_servicio as svc

    token = svc.generar_token()
    assert len(token) >= 43  # 256 bits en urlsafe
    otro = svc.generar_token()
    assert token != otro
    token_hash = svc.hash_token(token)
    assert token not in token_hash
    assert token_hash == svc.hash_token(token)  # determinista
    assert len(token_hash) == 64  # sha256 hex


@pytest.mark.parametrize(
    "creado,inicio,ahora,esperado",
    [
        # dentro de la ventana: ok
        (AHORA_BASE, AHORA_BASE + timedelta(days=9), AHORA_BASE + timedelta(hours=1), False),
        # +73 h con inicio lejano: expirado por 72 h
        (AHORA_BASE, AHORA_BASE + timedelta(days=9), AHORA_BASE + timedelta(hours=73), True),
        # inicio pasado aunque no pasen 72 h: expirado por inicio
        (AHORA_BASE, AHORA_BASE + timedelta(hours=5), AHORA_BASE + timedelta(hours=6), True),
        # exactamente en el inicio: expirado (>=)
        (AHORA_BASE, AHORA_BASE + timedelta(hours=5), AHORA_BASE + timedelta(hours=5), True),
        # un segundo antes del inicio (< 72 h): vigente
        (AHORA_BASE, AHORA_BASE + timedelta(hours=5), AHORA_BASE + timedelta(hours=5) - timedelta(seconds=1), False),
    ],
)
def test_token_expira_72h_o_inicio(creado, inicio, ahora, esperado):
    """Task 1.1 RED: expiracion derivada min(creado+72h, inicio), D-02."""
    from app.servicios import reserva_servicio as svc

    assert svc.token_expirado(creado, inicio, ahora) is esperado


# --- 1.2 paciente minimo ----------------------------------------------------

@pytest.mark.asyncio
async def test_reserva_reutiliza_paciente_por_telefono():
    """Task 1.2 RED: telefono conocido (con formato) reutiliza sin duplicar."""
    from app.servicios import reserva_servicio as svc

    pacientes = FakePacienteRepo([fabricar_paciente(id=7, telefono="1140001111")])
    paciente = await svc.obtener_o_crear_paciente_minimo(
        pacientes, "Otro Nombre", "11 4000-1111"
    )
    assert paciente.id == 7
    assert pacientes.cantidad() == 1


@pytest.mark.asyncio
async def test_reserva_crea_paciente_minimo_si_no_existe():
    """Task 1.2 RED: telefono nuevo crea minimo (nombre+telefono, resto NULL)."""
    from app.servicios import reserva_servicio as svc

    pacientes = FakePacienteRepo()
    paciente = await svc.obtener_o_crear_paciente_minimo(
        pacientes, "Ana Ficticia", "11 5000-2222"
    )
    assert paciente.nombre == "Ana Ficticia"
    assert paciente.telefono == "1150002222"
    assert paciente.dni is None and paciente.email is None
    assert pacientes.cantidad() == 1


@pytest.mark.asyncio
async def test_reserva_telefono_invalido_422():
    """Task 1.2 RED: telefono corto o nombre de 1 char -> ValueError (422)."""
    from app.servicios import reserva_servicio as svc

    pacientes = FakePacienteRepo()
    with pytest.raises(ValueError):
        await svc.obtener_o_crear_paciente_minimo(pacientes, "Ana Ficticia", "123")
    with pytest.raises(ValueError):
        await svc.obtener_o_crear_paciente_minimo(pacientes, "A", "1150002222")
    assert pacientes.cantidad() == 0


@pytest.mark.asyncio
async def test_reserva_ignora_paciente_soft_deleted():
    """Triangulacion: telefono de paciente borrado logico no se reutiliza."""
    from app.servicios import reserva_servicio as svc

    borrado = fabricar_paciente(
        id=3, telefono="1150003333", deleted_at=datetime.now(timezone.utc)
    )
    pacientes = FakePacienteRepo([borrado])
    paciente = await svc.obtener_o_crear_paciente_minimo(
        pacientes, "Nueva Ficticia", "1150003333"
    )
    assert paciente.id != 3
    assert pacientes.cantidad() == 2


# --- 1.3 crear_reserva ------------------------------------------------------

@pytest.mark.asyncio
async def test_reserva_crea_pendiente_con_hash():
    """Task 1.3 RED: hueco libre -> pendiente online, hash != plano, expira."""
    from app.servicios import reserva_servicio as svc

    turnos, pacientes, profesionales, sillones = _repos()
    resultado = await svc.crear_reserva(
        turnos, pacientes, profesionales, sillones,
        profesional_id=1, sillon_id=1,
        inicio=LUNES_9_BA, fin=LUNES_9_BA + timedelta(minutes=30),
        nombre="Ana Ficticia", telefono="1150002222", ahora=AHORA_BASE,
    )
    turno = resultado.turno
    assert turno.estado == "pendiente"
    assert turno.origen == "online"
    assert turno.sobre_turno is False
    assert turno.creado_por is None
    assert turno.token_confirmacion_hash is not None
    assert resultado.token not in turno.token_confirmacion_hash
    assert turno.token_confirmacion_hash == svc.hash_token(resultado.token)
    assert resultado.expira_en == min(
        turno.created_at + timedelta(hours=72), LUNES_9_BA
    )


@pytest.mark.asyncio
async def test_reserva_hueco_ocupado_409_con_alternativas():
    """Task 1.3 RED: hueco tomado -> HuecoOcupadoError con re-oferta."""
    from c04_fakes import fabricar_turno

    from app.servicios import agenda_servicio
    from app.servicios import reserva_servicio as svc

    ocupado = fabricar_turno(
        id=1, inicio=LUNES_9_BA, fin=LUNES_9_BA + timedelta(minutes=30),
        estado="confirmado",
    )
    turnos, pacientes, profesionales, sillones = _repos(turnos=[ocupado])
    with pytest.raises(agenda_servicio.HuecoOcupadoError) as exc:
        await svc.crear_reserva(
            turnos, pacientes, profesionales, sillones,
            profesional_id=1, sillon_id=1,
            inicio=LUNES_9_BA, fin=LUNES_9_BA + timedelta(minutes=30),
            nombre="Ana Ficticia", telefono="1150002222", ahora=AHORA_BASE,
        )
    assert len(exc.value.alternativas) > 0
    assert len(turnos._turnos) == 1  # nada nuevo persiste


@pytest.mark.asyncio
async def test_reserva_fuera_horario_no_crea():
    """Triangulacion: martes sin horario -> HuecoOcupadoError, sin turno."""
    from app.servicios import agenda_servicio
    from app.servicios import reserva_servicio as svc

    turnos, pacientes, profesionales, sillones = _repos()
    martes_9 = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(agenda_servicio.HuecoOcupadoError):
        await svc.crear_reserva(
            turnos, pacientes, profesionales, sillones,
            profesional_id=1, sillon_id=1,
            inicio=martes_9, fin=martes_9 + timedelta(minutes=30),
            nombre="Ana Ficticia", telefono="1150002222", ahora=AHORA_BASE,
        )
    assert len(turnos._turnos) == 0


# --- 1.4 confirmar_por_token ------------------------------------------------

@pytest.mark.asyncio
async def test_confirmar_token_valido_confirma():
    """Task 1.4 RED: token valido -> confirmado + hash NULL."""
    from app.servicios import reserva_servicio as svc

    turnos, pacientes, profesionales, sillones = _repos()
    tienda = FakeStore()
    resultado = await svc.crear_reserva(
        turnos, pacientes, profesionales, sillones,
        profesional_id=1, sillon_id=1,
        inicio=LUNES_9_BA, fin=LUNES_9_BA + timedelta(minutes=30),
        nombre="Ana Ficticia", telefono="1150002222", ahora=AHORA_BASE,
    )
    turno = await svc.confirmar_por_token(
        turnos, resultado.token, ahora=AHORA_BASE + timedelta(hours=1),
        tienda_usados=tienda,
    )
    assert turno.estado == "confirmado"
    assert turno.token_confirmacion_hash is None


@pytest.mark.asyncio
async def test_confirmar_reuso_token_410():
    """Task 1.4 RED: segundo uso -> TokenUsadoError (410), sin cambios."""
    from app.servicios import reserva_servicio as svc

    turnos, pacientes, profesionales, sillones = _repos()
    tienda = FakeStore()
    resultado = await svc.crear_reserva(
        turnos, pacientes, profesionales, sillones,
        profesional_id=1, sillon_id=1,
        inicio=LUNES_9_BA, fin=LUNES_9_BA + timedelta(minutes=30),
        nombre="Ana Ficticia", telefono="1150002222", ahora=AHORA_BASE,
    )
    await svc.confirmar_por_token(
        turnos, resultado.token, ahora=AHORA_BASE + timedelta(hours=1),
        tienda_usados=tienda,
    )
    with pytest.raises(svc.TokenUsadoError):
        await svc.confirmar_por_token(
            turnos, resultado.token, ahora=AHORA_BASE + timedelta(hours=2),
            tienda_usados=tienda,
        )
    turno = await turnos.get(resultado.turno.id)
    assert turno.estado == "confirmado"


@pytest.mark.asyncio
async def test_confirmar_expirado_410_con_contacto():
    """Task 1.4 RED: +73 h -> TokenExpiradoError con contacto, sigue pendiente."""
    from freezegun import freeze_time

    from app.servicios import reserva_servicio as svc

    turnos, pacientes, profesionales, sillones = _repos()
    with freeze_time("2026-10-01 12:00:00"):
        resultado = await svc.crear_reserva(
            turnos, pacientes, profesionales, sillones,
            profesional_id=1, sillon_id=1,
            inicio=LUNES_9_BA, fin=LUNES_9_BA + timedelta(minutes=30),
            nombre="Ana Ficticia", telefono="1150002222",
        )
    with pytest.raises(svc.TokenExpiradoError) as exc:
        await svc.confirmar_por_token(
            turnos, resultado.token, ahora=AHORA_BASE + timedelta(hours=73),
        )
    assert exc.value.contacto  # alternativa de contacto (telefono ficticio)
    turno = await turnos.get(resultado.turno.id)
    assert turno.estado == "pendiente"
    assert turno.token_confirmacion_hash is not None  # no se invalida


@pytest.mark.asyncio
async def test_confirmar_desconocido_404():
    """Task 1.4 RED: token que nunca existio -> TokenDesconocidoError (404)."""
    from app.servicios import reserva_servicio as svc

    turnos, _, _, _ = _repos()
    with pytest.raises(svc.TokenDesconocidoError):
        await svc.confirmar_por_token(turnos, svc.generar_token(), ahora=AHORA_BASE)


@pytest.mark.asyncio
async def test_confirmar_cancelado_410_honesto():
    """Triangulacion: turno cancelado por secretaria no se confirma (410)."""
    from app.servicios import agenda_servicio
    from app.servicios import reserva_servicio as svc

    turnos, pacientes, profesionales, sillones = _repos()
    resultado = await svc.crear_reserva(
        turnos, pacientes, profesionales, sillones,
        profesional_id=1, sillon_id=1,
        inicio=LUNES_9_BA, fin=LUNES_9_BA + timedelta(minutes=30),
        nombre="Ana Ficticia", telefono="1150002222", ahora=AHORA_BASE,
    )
    await agenda_servicio.cambiar_estado(
        turnos, resultado.turno.id, "cancelado", motivo="paciente ausente demo"
    )
    with pytest.raises(svc.TurnoNoConfirmableError):
        await svc.confirmar_por_token(
            turnos, resultado.token, ahora=AHORA_BASE + timedelta(hours=1)
        )


# --- 1.5 carrera ------------------------------------------------------------

@pytest.mark.asyncio
async def test_reserva_concurrente_mismo_hueco_un_ganador():
    """Task 1.5 RED: 2 reservas mismo hueco -> 1 turno, 1 HuecoOcupadoError."""
    import asyncio

    from app.servicios import agenda_servicio
    from app.servicios import reserva_servicio as svc

    turnos, pacientes, profesionales, sillones = _repos()

    async def _intento(nombre: str, telefono: str):
        return await svc.crear_reserva(
            turnos, pacientes, profesionales, sillones,
            profesional_id=1, sillon_id=1,
            inicio=LUNES_9_BA, fin=LUNES_9_BA + timedelta(minutes=30),
            nombre=nombre, telefono=telefono, ahora=AHORA_BASE,
        )

    resultados = await asyncio.gather(
        _intento("Ana Ficticia", "1150002222"),
        _intento("Bruno Ficticio", "1150003333"),
        return_exceptions=True,
    )
    exitos = [r for r in resultados if not isinstance(r, Exception)]
    fallos = [r for r in resultados if isinstance(r, Exception)]
    assert len(exitos) == 1
    assert len(fallos) == 1
    assert isinstance(fallos[0], agenda_servicio.HuecoOcupadoError)
    assert len(turnos._turnos) == 1
