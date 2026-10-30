"""C-07 task 8.1: Flujo 6 end-to-end, cierre del loop de la lista de espera.

Cancelar un turno con 2 en espera -> oferta a la 1ª (expira en 2 h) -> expira
(freezegun +2h01) -> cascada a la 2ª -> acepta por token -> turno
`confirmado` con `origen=lista_espera` -> una 3ª cancelación sin nadie en
espera deja el hueco libre en `GET /disponibilidad` pública.

El MISMO guion corre dos veces:
  - `test_c07_flujo6_cierre_loop_completo`: Postgres REAL + Redis REAL
    (skipea con mensaje accionable sin Docker).
  - `test_c07_flujo6_cierre_loop_en_memoria`: fakes (siempre corre).
freezegun con tick=True: el reloj avanza, así los timers de asyncpg/redis no
se congelan. Datos 100% ficticios; TZ America/Argentina/Buenos_Aires.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from freezegun import freeze_time

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c03_fakes import FakeRepo, fabricar_usuario  # noqa: E402
from c07_fakes import armar_app  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

T0 = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)          # lunes 09:00 BA: se cancela
HUECO_INI = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)   # lunes siguiente 09:00 BA
HUECO_FIN = HUECO_INI + timedelta(minutes=30)
AGENDA_LUNES = {"duracion_slot_min": 30, "horario": {"lunes": [["08:00", "12:00"]]}}
TOLERANCIA = timedelta(seconds=30)  # tick=True: el reloj avanza mientras corre el guion


def _casi(real: datetime, esperado: datetime) -> bool:
    return abs(real - esperado) <= TOLERANCIA


async def _huecos_publicos(cli, profesional_id: int) -> list[datetime]:
    resp = await cli.get("/disponibilidad", params={
        "profesional_id": profesional_id,
        "desde": "2026-11-16T03:00:00+00:00", "hasta": "2026-11-17T03:00:00+00:00",
    })
    assert resp.status_code == 200, resp.text
    return [datetime.fromisoformat(h["inicio"]) for h in resp.json()]


def _token_de(cliente) -> str:
    """Token del último link enviado por el canal mock (nunca se loguea)."""
    return cliente.envios[-1]["variables"]["link_oferta"].rsplit("/", 1)[1]


async def _guion_flujo6(*, cli, bearer, cliente, ids, leer_turno, leer_entry, listar_ofrecidas, barrido, hay_notif):
    """El guion del Flujo 6; `ids` = dict con turno, prof, e1, e2."""
    def h():
        # JWT de 30 min: se emite DENTRO de cada freeze_time (con freezegun el reloj salta días)
        return bearer(1, "secretaria")

    # 1) Cancelar con 2 en espera -> oferta a la 1ª con expiración 2 h.
    with freeze_time(T0, tick=True):
        assert HUECO_INI not in await _huecos_publicos(cli, ids["prof"])  # el turno aún ocupa el hueco
        cancel = await cli.patch(f"/turnos/{ids['turno']}/estado",
                                 json={"estado": "cancelado", "motivo": "paciente avisó"}, headers=h())
        assert cancel.status_code == 200, cancel.text
        e1, e2 = await leer_entry(ids["e1"]), await leer_entry(ids["e2"])
        assert e1.estado == "ofrecida" and e2.estado == "activa"
        assert _casi(e1.oferta_expira_en, T0 + timedelta(hours=2))
        token1 = _token_de(cliente)
        assert await hay_notif(ids["turno"], "oferta_lista_espera")
        # D-03: la oferta NO bloquea el hueco; sigue público y reservable.
        assert HUECO_INI in await _huecos_publicos(cli, ids["prof"])

    # 2) Pasan 2 h01 sin respuesta -> el worker vence y encadena.
    with freeze_time(T0 + timedelta(hours=2, minutes=1), tick=True):
        stats = await barrido()
        assert stats["vencidas"] == 1 and stats["cascadas"] == 1, stats
        e1, e2 = await leer_entry(ids["e1"]), await leer_entry(ids["e2"])
        assert (e1.estado, e1.motivo_baja) == ("vencida", "expirada")
        assert e2.estado == "ofrecida"
        assert _casi(e2.oferta_expira_en, T0 + timedelta(hours=4, minutes=1))  # ventana nueva
        token2 = _token_de(cliente)
        assert token2 != token1
        # El link de la 1ª ya no sirve: 410 (resuelta), nunca 404 ni turno.
        tarde = await cli.post(f"/lista-espera/aceptar/{token1}")
        assert tarde.status_code == 410

    # 3) La 2ª acepta por token -> confirmado origen lista_espera.
    with freeze_time(T0 + timedelta(hours=2, minutes=30), tick=True):
        ok = await cli.post(f"/lista-espera/aceptar/{token2}")
        assert ok.status_code == 200, ok.text
        nuevo_id = ok.json()["turno_id"]  # el ORM queda expirado tras los commits de la API
        nuevo = await leer_turno(nuevo_id)
        assert (nuevo.estado, nuevo.origen, nuevo.sobre_turno) == ("confirmado", "lista_espera", False)
        assert nuevo.inicio == HUECO_INI
        assert (await leer_entry(ids["e2"])).estado == "convertida"
        assert await hay_notif(nuevo_id, "confirmacion")
        assert HUECO_INI not in await _huecos_publicos(cli, ids["prof"])  # ya ocupado
        reuso = await cli.post(f"/lista-espera/aceptar/{token2}")
        assert reuso.status_code == 410

    # 4) 3ª cancelación (la del turno de lista de espera) sin nadie en espera -> hueco libre.
    with freeze_time(T0 + timedelta(hours=3), tick=True):
        envios_antes = len(cliente.envios)
        c3 = await cli.patch(f"/turnos/{nuevo_id}/estado",
                             json={"estado": "cancelado", "motivo": "imprevisto"}, headers=h())
        assert c3.status_code == 200, c3.text
        assert await listar_ofrecidas() == []                      # sin ofertas residuales
        assert len(cliente.envios) == envios_antes                  # nadie recibió un aviso de más
        assert HUECO_INI in await _huecos_publicos(cli, ids["prof"])  # hueco libre en agenda pública


# --- variante en memoria (siempre corre) -------------------------------------------

@pytest.mark.asyncio
async def test_c07_flujo6_cierre_loop_en_memoria():
    """Task 8.1 (fakes): Flujo 6 completo sin Docker."""
    from c04_fakes import fabricar_turno
    from c05_fakes import fabricar_paciente
    from c07_fakes import fabricar_entry

    from app.worker import espera_jobs

    _, cli, bearer, mundo = armar_app(
        usuarios=[fabricar_usuario(id=1, rol="secretaria")],
        pacientes=[fabricar_paciente(id=i, nombre=n, telefono=f"114000{i}{i}{i}{i}")
                   for i, n in ((1, "Ana"), (2, "Beto"), (3, "Cleo"))],
        turnos=[fabricar_turno(id=10, paciente_id=3, estado="confirmado", inicio=HUECO_INI, fin=HUECO_FIN)],
        entradas=[fabricar_entry(1, paciente_id=1), fabricar_entry(2, paciente_id=2)],
    )

    async def barrido():
        return await espera_jobs.barrido_vencidas(
            mundo.espera, mundo.turnos, mundo.profesionales, mundo.sillones,
            mundo.pacientes, mundo.notifs, mundo.tienda, mundo.cliente,
        )

    async def hay_notif(turno_id, plantilla):
        return await mundo.notifs.activa_de_turno(turno_id, plantilla) is not None

    async def listar_ofrecidas():
        return await mundo.espera.listar_fifo(estado="ofrecida")

    async with cli:
        await _guion_flujo6(
            cli=cli, bearer=bearer, cliente=mundo.cliente,
            ids={"turno": 10, "prof": 1, "e1": 1, "e2": 2},
            leer_turno=mundo.turnos.get, leer_entry=mundo.espera.get,
            listar_ofrecidas=listar_ofrecidas, barrido=barrido, hay_notif=hay_notif,
        )


# --- variante Postgres + Redis reales (skipea sin Docker) --------------------------

@pytest.mark.asyncio
async def test_c07_flujo6_cierre_loop_completo(sesion_pg):
    """Task 8.1 RED/GREEN (PG + Redis reales): Flujo 6 completo con constraints reales."""
    try:
        import redis.asyncio as aioredis
    except ImportError:
        pytest.skip("redis no instalado")
    tienda = aioredis.from_url(os.getenv("REDIS_URL_TEST", "redis://localhost:6379/0"), decode_responses=True)
    try:
        await tienda.ping()
    except Exception as exc:  # noqa: BLE001
        await tienda.aclose()
        pytest.skip(f"Redis no reachable (¿compose down / sin Docker?): {exc}")

    from c06_fakes import CuentaCliente
    from httpx import ASGITransport, AsyncClient

    from app.api.espera_hook import get_cliente_espera
    from app.core.deps import get_db, get_redis, get_usuario_repo
    from app.core.security import crear_access_token
    from app.main import create_app
    from app.modelos import Paciente, Profesional, Sillon
    from app.repos.espera_repo import EsperaRepository
    from app.repos.notificacion_repo import NotificacionRepository
    from app.repos.paciente_repo import PacienteRepository
    from app.repos.profesional_repo import ProfesionalRepository
    from app.repos.sillon_repo import SillonRepository
    from app.repos.turno_repo import TurnoRepository
    from app.worker import espera_jobs

    async def limpiar_redis():
        for patron in ("espera:cascada:*", "notif:*"):
            async for clave in tienda.scan_iter(patron):
                await tienda.delete(clave)

    await limpiar_redis()  # los ids de PG se reinician: no heredar claves de corridas previas
    try:
        pacientes = [Paciente(nombre=n, apellido="Flujo6", telefono=tel, consentimiento_datos=True)
                     for n, tel in (("Ana", "1140001111"), ("Beto", "1140002222"), ("Cleo", "1140003333"))]
        profesional = Profesional(matricula="C07-F6", agenda_config=dict(AGENDA_LUNES))
        sillon = Sillon(nombre="Sillón C07-F6")
        sesion_pg.add_all([*pacientes, profesional, sillon])
        await sesion_pg.flush()
        turnos = TurnoRepository(sesion_pg)
        espera = EsperaRepository(sesion_pg)
        turno = await turnos.crear(
            paciente_id=pacientes[2].id, profesional_id=profesional.id, sillon_id=sillon.id,
            inicio=HUECO_INI, fin=HUECO_FIN, estado="confirmado",
        )
        e1 = await espera.crear(paciente_id=pacientes[0].id, profesional_id=profesional.id, estado="activa")
        await sesion_pg.flush()
        e2 = await espera.crear(paciente_id=pacientes[1].id, profesional_id=profesional.id, estado="activa")
        await sesion_pg.commit()

        app = create_app()
        cliente = CuentaCliente()
        app.dependency_overrides[get_usuario_repo] = lambda: FakeRepo([fabricar_usuario(id=1, rol="secretaria")])
        app.dependency_overrides[get_redis] = lambda: tienda
        app.dependency_overrides[get_cliente_espera] = lambda: cliente

        async def _db():
            yield sesion_pg

        app.dependency_overrides[get_db] = _db

        def bearer(uid, rol):
            return {"Authorization": f"Bearer {crear_access_token(uid, rol)}"}

        async def barrido():
            return await espera_jobs.barrido_vencidas(
                EsperaRepository(sesion_pg), TurnoRepository(sesion_pg),
                ProfesionalRepository(sesion_pg), SillonRepository(sesion_pg),
                PacienteRepository(sesion_pg), NotificacionRepository(sesion_pg),
                tienda, cliente, commit=sesion_pg.commit, rollback=sesion_pg.rollback,
            )

        async def hay_notif(turno_id, plantilla):
            return await NotificacionRepository(sesion_pg).activa_de_turno(turno_id, plantilla) is not None

        async def listar_ofrecidas():
            return await EsperaRepository(sesion_pg).listar_fifo(estado="ofrecida")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as cli:
            await _guion_flujo6(
                cli=cli, bearer=bearer, cliente=cliente,
                ids={"turno": turno.id, "prof": profesional.id, "e1": e1.id, "e2": e2.id},
                leer_turno=TurnoRepository(sesion_pg).get,
                leer_entry=EsperaRepository(sesion_pg).get,
                listar_ofrecidas=listar_ofrecidas, barrido=barrido, hay_notif=hay_notif,
            )
    finally:
        await limpiar_redis()
        await tienda.aclose()
