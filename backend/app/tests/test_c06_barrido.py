"""C-06 tasks 3.1/3.2/3.3 + 6.1 RED: barrido 48/24 h idempotente con costo (D-03).

Unit con fakes (siempre corre, freezegun + TZ BA): ventana ±30 min encola
pendiente+confirmado e ignora fuera de ventana; sin numero -> fallida sin
envio; doble barrido -> 1 fila + 1 envio; 3 intentos luego fallida; costo
mock 0 / real 0.026; online entra al barrido; Redis caido degrada a encolada;
reprogramacion reenvia (resolucion humana 2026-10-13).
PG/Redis-gated: idempotencia real doble barrido (skipea sin Docker).
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from freezegun import freeze_time

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c04_fakes import fabricar_entidad  # noqa: E402
from c05_fakes import FakePacienteRepo, fabricar_paciente  # noqa: E402
from c06_fakes import (  # noqa: E402
    CuentaCliente,
    FakeNotifRepo,
    FakeRedis,
    FakeTurnoRepoC06,
    FallaCliente,
    fabricar_turno_c06,
)
from db_utils import sesion_pg  # noqa: E402, F401

AHORA = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
A_48H = AHORA + timedelta(hours=48)
A_12H = AHORA + timedelta(hours=12)


def _mundo(turnos, pacientes=None, tienda=None, cliente=None):
    return {
        "turnos": FakeTurnoRepoC06(turnos),
        "notifs": FakeNotifRepo(),
        "pacientes": FakePacienteRepo(pacientes if pacientes is not None else [
            fabricar_paciente(id=1, telefono="1140001111",
                              email="ana@ficticio.test"),
        ]),
        "tienda": tienda or FakeRedis(),
        "cliente": cliente or CuentaCliente(),
    }


@pytest.mark.asyncio
async def test_barrido_48h_encola_pendiente_y_confirmado():
    """Task 3.1 RED: pendiente+confirmado a 48 h generan; a 12 h nada."""
    from app.servicios import notificacion_servicio as svc

    with freeze_time(AHORA):
        mundo = _mundo([
            fabricar_turno_c06(id=1, estado="pendiente", inicio=A_48H,
                               fin=A_48H + timedelta(minutes=30)),
            fabricar_turno_c06(id=2, estado="confirmado", inicio=A_48H,
                               fin=A_48H + timedelta(minutes=30)),
            fabricar_turno_c06(id=3, estado="pendiente", inicio=A_12H,
                               fin=A_12H + timedelta(minutes=30)),
            fabricar_turno_c06(id=4, estado="cancelado", inicio=A_48H,
                               fin=A_48H + timedelta(minutes=30)),
        ])
        stats = await svc.barrido_recordatorios(
            mundo["turnos"], mundo["notifs"], mundo["pacientes"],
            mundo["tienda"], mundo["cliente"], ahora=AHORA,
        )
    assert stats["encoladas"] == 2
    assert mundo["notifs"].cantidad_activas() == 2
    assert len(mundo["cliente"].envios) == 2
    plantillas = {f.plantilla for f in mundo["notifs"]._filas.values()}
    assert plantillas == {"recordatorio_48h"}


@pytest.mark.asyncio
async def test_barrido_sin_numero_marca_fallida_sin_encolar():
    """Task 3.1 RED: sin telefono ni email -> fallida sin envio ni costo."""
    from app.servicios import notificacion_servicio as svc

    with freeze_time(AHORA):
        mundo = _mundo(
            [fabricar_turno_c06(id=1, paciente_id=9, inicio=A_48H,
                                fin=A_48H + timedelta(minutes=30))],
            pacientes=[fabricar_paciente(id=9, telefono=None, email=None)],
        )
        stats = await svc.barrido_recordatorios(
            mundo["turnos"], mundo["notifs"], mundo["pacientes"],
            mundo["tienda"], mundo["cliente"], ahora=AHORA,
        )
    assert stats["fallidas"] == 1
    fila = next(iter(mundo["notifs"]._filas.values()))
    assert fila.estado == "fallida"
    assert fila.ultimo_error == "sin_numero_valido"
    assert len(mundo["cliente"].envios) == 0


@pytest.mark.asyncio
async def test_doble_barrido_un_solo_envio():
    """Task 3.2 RED: dos barridos -> 1 fila activa + 1 envio (Redis + UNIQUE)."""
    from app.servicios import notificacion_servicio as svc

    with freeze_time(AHORA):
        mundo = _mundo([fabricar_turno_c06(id=1, inicio=A_48H,
                                           fin=A_48H + timedelta(minutes=30))])
        uno = await svc.barrido_recordatorios(
            mundo["turnos"], mundo["notifs"], mundo["pacientes"],
            mundo["tienda"], mundo["cliente"], ahora=AHORA,
        )
        dos = await svc.barrido_recordatorios(
            mundo["turnos"], mundo["notifs"], mundo["pacientes"],
            mundo["tienda"], mundo["cliente"], ahora=AHORA,
        )
    assert uno["encoladas"] == 1 and dos["encoladas"] == 0
    assert dos["skips"] >= 1
    assert mundo["notifs"].cantidad_activas() == 1
    assert len(mundo["cliente"].envios) == 1


@pytest.mark.asyncio
async def test_reintento_backoff_3_intentos_luego_fallida(monkeypatch):
    """Task 3.3 RED: 3 fallos + fallback roto -> fallida intentos=3 sin PHI."""
    from app.servicios import notificacion_servicio as svc
    from app.servicios import whatsapp_cliente as wc

    async def _sms_roto(self, destinatario, plantilla, variables):
        raise wc.EnvioFallidoError("sms stub caido (demo)")

    monkeypatch.setattr(wc.SmsStubCliente, "enviar", _sms_roto)
    with freeze_time(AHORA):
        mundo = _mundo(
            [fabricar_turno_c06(id=1, paciente_id=9, inicio=A_48H,
                                fin=A_48H + timedelta(minutes=30))],
            pacientes=[fabricar_paciente(id=9, telefono="1140009999", email=None)],
            cliente=FallaCliente(),
        )
        stats = await svc.barrido_recordatorios(
            mundo["turnos"], mundo["notifs"], mundo["pacientes"],
            mundo["tienda"], mundo["cliente"], ahora=AHORA,
        )
    assert stats["fallidas"] == 1
    fila = next(iter(mundo["notifs"]._filas.values()))
    assert fila.estado == "fallida" and fila.intentos == 3
    assert "1140009999" not in (fila.ultimo_error or "")  # sin PHI en traza
    assert float(fila.costo or 0) == 0


@pytest.mark.asyncio
async def test_barrido_falla_whatsapp_ok_sms_fallback():
    """Triangulacion RN-NO-03: whatsapp caido + tel valido -> sms enviada."""
    from app.servicios import notificacion_servicio as svc

    with freeze_time(AHORA):
        mundo = _mundo(
            [fabricar_turno_c06(id=1, paciente_id=9, inicio=A_48H,
                                fin=A_48H + timedelta(minutes=30))],
            pacientes=[fabricar_paciente(id=9, telefono="1140009999", email=None)],
            cliente=FallaCliente(),
        )
        stats = await svc.barrido_recordatorios(
            mundo["turnos"], mundo["notifs"], mundo["pacientes"],
            mundo["tienda"], mundo["cliente"], ahora=AHORA,
        )
    fila = next(iter(mundo["notifs"]._filas.values()))
    assert stats["encoladas"] == 1 and fila.estado == "enviada"
    assert fila.canal == "sms" and fila.intentos == 3


@pytest.mark.asyncio
async def test_costo_mock_cero_y_real_0026():
    """Task 3.3 RED: mock -> 0; cliente costo real -> 0.026 por enviada."""
    from app.servicios import notificacion_servicio as svc
    from app.servicios.whatsapp_cliente import COSTO_META_USD_REF

    with freeze_time(AHORA):
        mundo = _mundo([fabricar_turno_c06(id=1, inicio=A_48H,
                                           fin=A_48H + timedelta(minutes=30))])
        await svc.barrido_recordatorios(
            mundo["turnos"], mundo["notifs"], mundo["pacientes"],
            mundo["tienda"], mundo["cliente"], ahora=AHORA,
        )
        fila_mock = next(iter(mundo["notifs"]._filas.values()))
        assert float(fila_mock.costo) == 0

        mundo2 = _mundo(
            [fabricar_turno_c06(id=1, inicio=A_48H,
                                fin=A_48H + timedelta(minutes=30))],
            cliente=CuentaCliente(costo=COSTO_META_USD_REF),
        )
        await svc.barrido_recordatorios(
            mundo2["turnos"], mundo2["notifs"], mundo2["pacientes"],
            mundo2["tienda"], mundo2["cliente"], ahora=AHORA,
        )
        fila_real = next(iter(mundo2["notifs"]._filas.values()))
        assert float(fila_real.costo) == 0.026


@pytest.mark.asyncio
async def test_reserva_online_entra_al_barrido():
    """Task 6.1 RED: turno origen=online pendiente a 48 h entra sin codigo extra."""
    from app.servicios import notificacion_servicio as svc

    with freeze_time(AHORA):
        mundo = _mundo([fabricar_turno_c06(
            id=1, origen="online", estado="pendiente", inicio=A_48H,
            fin=A_48H + timedelta(minutes=30))])
        stats = await svc.barrido_recordatorios(
            mundo["turnos"], mundo["notifs"], mundo["pacientes"],
            mundo["tienda"], mundo["cliente"], ahora=AHORA,
        )
    assert stats["encoladas"] == 1


@pytest.mark.asyncio
async def test_barrido_redis_caido_degrada_encolada():
    """Triangulacion D-04: Redis roto -> fila encolada sin envio, reintento luego."""
    from app.servicios import notificacion_servicio as svc

    with freeze_time(AHORA):
        tienda_rota = FakeRedis()
        tienda_rota.roto = True
        mundo = _mundo(
            [fabricar_turno_c06(id=1, inicio=A_48H,
                                fin=A_48H + timedelta(minutes=30))],
            tienda=tienda_rota,
        )
        stats = await svc.barrido_recordatorios(
            mundo["turnos"], mundo["notifs"], mundo["pacientes"],
            mundo["tienda"], mundo["cliente"], ahora=AHORA,
        )
    assert stats["degradadas"] == 1
    fila = next(iter(mundo["notifs"]._filas.values()))
    assert fila.estado == "encolada"
    assert len(mundo["cliente"].envios) == 0
    # Proximo tick con Redis sano: reintento la envia sin duplicar.
    tienda_sana = FakeRedis()
    re = await svc.reintentar_fallidas(
        mundo["notifs"], mundo["turnos"], mundo["pacientes"],
        tienda_sana, mundo["cliente"], ahora=AHORA,
    )
    assert re["enviadas"] == 1
    assert fila.estado == "enviada"


@pytest.mark.asyncio
async def test_reprogramacion_reenvia_nueva_hora():
    """Resolucion humana P1: turno reprogramado habilita nuevo recordatorio."""
    from app.servicios import notificacion_servicio as svc

    with freeze_time(AHORA):
        mundo = _mundo([fabricar_turno_c06(id=1, inicio=A_48H,
                                           fin=A_48H + timedelta(minutes=30))])
        await svc.barrido_recordatorios(
            mundo["turnos"], mundo["notifs"], mundo["pacientes"],
            mundo["tienda"], mundo["cliente"], ahora=AHORA,
        )
        # Reprograma +20 min (sigue en ventana 48 h, otra hora) y rebarre.
        turno = await mundo["turnos"].get(1)
        turno.inicio = A_48H + timedelta(minutes=20)
        turno.fin = turno.inicio + timedelta(minutes=30)
        stats = await svc.barrido_recordatorios(
            mundo["turnos"], mundo["notifs"], mundo["pacientes"],
            mundo["tienda"], mundo["cliente"], ahora=AHORA,
        )
    assert stats["encoladas"] == 1
    assert len(mundo["cliente"].envios) == 2


@pytest.mark.asyncio
async def test_barrido_pg_redis_idempotente(sesion_pg):
    """Tasks 3.1/3.2 GREEN (PG+Redis reales): doble barrido -> 1 fila, 1 envio."""
    import uuid
    from datetime import timezone as _tz

    from app.repos.notificacion_repo import NotificacionRepository
    from app.repos.paciente_repo import PacienteRepository
    from app.repos.turno_repo import TurnoRepository
    from app.servicios import notificacion_servicio as svc

    try:
        import redis.asyncio as aioredis
    except ImportError:
        pytest.skip("redis no instalado")
    import os

    tienda = aioredis.from_url(
        os.getenv("REDIS_URL_TEST", "redis://localhost:6379/0"),
        decode_responses=True,
    )
    try:
        await tienda.ping()
    except Exception as exc:
        pytest.skip(f"Redis no reachable: {exc}")
    try:
        from app.modelos import Paciente, Profesional, Sillon, Turno

        suf = uuid.uuid4().hex[:6]
        paciente = Paciente(
            nombre="Ficticia", apellido="Barrido", telefono="1140001111",
            consentimiento_datos=True,
        )
        profesional = Profesional(matricula=f"C06-B{suf}")
        sillon = Sillon(nombre=f"Sillón C06-B{suf}")
        sesion_pg.add_all([paciente, profesional, sillon])
        await sesion_pg.flush()
        ahora = datetime.now(_tz.utc)
        inicio = ahora + timedelta(hours=48)
        sesion_pg.add(Turno(
            paciente_id=paciente.id, profesional_id=profesional.id,
            sillon_id=sillon.id, inicio=inicio,
            fin=inicio + timedelta(minutes=30),
        ))
        await sesion_pg.flush()
        from c06_fakes import CuentaCliente

        cliente = CuentaCliente()
        notifs = NotificacionRepository(sesion_pg)
        await svc.barrido_recordatorios(
            TurnoRepository(sesion_pg), notifs, PacienteRepository(sesion_pg),
            tienda, cliente, ahora=ahora,
        )
        await svc.barrido_recordatorios(
            TurnoRepository(sesion_pg), notifs, PacienteRepository(sesion_pg),
            tienda, cliente, ahora=ahora,
        )
        await sesion_pg.commit()
        from sqlalchemy import func, select

        from app.modelos import Notificacion

        activas = await sesion_pg.scalar(
            select(func.count()).select_from(Notificacion).where(
                Notificacion.estado != "fallida")
        )
        assert activas == 1
        assert len(cliente.envios) == 1
    finally:
        try:
            async for clave in tienda.scan_iter("notif:*"):
                await tienda.delete(clave)
        except Exception:
            pass
        await tienda.aclose()
