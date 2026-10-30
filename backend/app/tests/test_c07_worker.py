"""C-07 grupo 6: worker de vencimientos de lista de espera (D-05).

Con fakes (siempre corre): barrido a las 2 h, cascada con nueva ventana,
degradación sin Redis idempotente, lock anti-doble-cascada y main con
`bucle_espera`. La variante con Redis real skipea sin Docker.
freezegun para la ventana de 2 h. Datos 100% ficticios.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from freezegun import freeze_time

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c04_fakes import FakeTurnoRepo  # noqa: E402
from c05_fakes import FakePacienteRepo, fabricar_paciente  # noqa: E402
from c06_fakes import CuentaCliente, FakeNotifRepo, FakeRedis  # noqa: E402
from c07_fakes import (  # noqa: E402
    FakeEsperaRepo, FakeProfesionales, FakeSillones, fabricar_entry,
)

T0 = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)  # lunes, oferta inicial
HUECO_INI = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
HUECO_FIN = HUECO_INI + timedelta(minutes=30)


def _mundo(n_entradas=2):
    pacientes = [fabricar_paciente(id=i, nombre=f"Paciente{i}", telefono=f"11400011{i:02d}")
                 for i in range(1, n_entradas + 1)]
    entradas = [fabricar_entry(i, paciente_id=i) for i in range(1, n_entradas + 1)]
    return dict(
        espera_repo=FakeEsperaRepo(entradas), turnos_repo=FakeTurnoRepo(),
        profesionales_repo=FakeProfesionales(), sillones_repo=FakeSillones(),
        pacientes_repo=FakePacienteRepo(pacientes), notif_repo=FakeNotifRepo(),
        tienda=FakeRedis(), cliente=CuentaCliente(),
    )


async def _ofrecer_inicial(mundo):
    from app.servicios import lista_espera_servicio as svc

    hueco = {"profesional_id": 1, "sillon_id": 1, "inicio": HUECO_INI, "fin": HUECO_FIN, "turno_id": 5}
    return await svc.intentar_ofrecer(hueco=hueco, ahora=T0, **mundo)


@pytest.mark.asyncio
async def test_barrido_2h_vence_y_ofrece_siguiente():
    """Task 6.1 RED: +2h01 -> la 1ª `vencida 'expirada'` y la 2ª `ofrecida` con ventana nueva."""
    from app.worker import espera_jobs

    mundo = _mundo()
    primera = await _ofrecer_inicial(mundo)
    assert primera.id == 1 and primera.oferta_expira_en == T0 + timedelta(hours=2)

    ahora = T0 + timedelta(hours=2, minutes=1)
    with freeze_time(ahora):
        stats = await espera_jobs.barrido_vencidas(**mundo)

    e1, e2 = await mundo["espera_repo"].get(1), await mundo["espera_repo"].get(2)
    assert (e1.estado, e1.motivo_baja) == ("vencida", "expirada")
    assert e2.estado == "ofrecida"
    assert e2.oferta_expira_en == ahora + timedelta(hours=2)  # nueva ventana de 2 h
    assert e2.oferta_hueco["inicio"] == HUECO_INI.isoformat()  # mismo hueco
    assert stats["vencidas"] == 1 and stats["cascadas"] == 1
    assert [e["destinatario"] for e in mundo["cliente"].envios] == ["1140001101", "1140001102"]


@pytest.mark.asyncio
async def test_barrido_antes_de_las_2h_no_toca_nada():
    """Task 6.1 (triangulación): a las 1h59 la oferta sigue vigente."""
    from app.worker import espera_jobs

    mundo = _mundo()
    await _ofrecer_inicial(mundo)

    with freeze_time(T0 + timedelta(hours=1, minutes=59)):
        stats = await espera_jobs.barrido_vencidas(**mundo)

    assert stats["vencidas"] == 0
    assert (await mundo["espera_repo"].get(1)).estado == "ofrecida"
    assert (await mundo["espera_repo"].get(2)).estado == "activa"


@pytest.mark.asyncio
async def test_barrido_cola_vacia_deja_hueco_libre():
    """Si nadie más espera, la entry vence y el hueco queda libre (sin turnos ni ofertas residuales)."""
    from app.worker import espera_jobs

    mundo = _mundo(n_entradas=1)
    await _ofrecer_inicial(mundo)

    with freeze_time(T0 + timedelta(hours=3)):
        stats = await espera_jobs.barrido_vencidas(**mundo)

    assert (await mundo["espera_repo"].get(1)).estado == "vencida"
    assert stats["vencidas"] == 1 and stats["cascadas"] == 0
    assert await mundo["turnos_repo"].activos_en_rango(HUECO_INI, HUECO_FIN) == []  # hueco libre
    assert all(e.estado != "ofrecida" for e in mundo["espera_repo"]._entradas.values())


@pytest.mark.asyncio
async def test_barrido_sin_redis_no_duplica():
    """Task 6.1 RED: con Redis caído degrada a barrido DB idempotente: dos ticks, una sola oferta nueva."""
    from app.worker import espera_jobs

    mundo = _mundo(n_entradas=3)
    await _ofrecer_inicial(mundo)
    mundo["tienda"].roto = True  # Redis caído a partir de acá

    ahora = T0 + timedelta(hours=2, minutes=1)
    with freeze_time(ahora):
        uno = await espera_jobs.barrido_vencidas(**mundo)
        dos = await espera_jobs.barrido_vencidas(**mundo)

    estados = {e.id: e.estado for e in mundo["espera_repo"]._entradas.values()}
    assert estados == {1: "vencida", 2: "ofrecida", 3: "activa"}  # la 3ª NO se ofrece de más
    assert uno["degradadas"] == 1 and uno["vencidas"] == 1
    assert dos["vencidas"] == 0 and dos["cascadas"] == 0
    assert len(mundo["cliente"].envios) == 2  # inicial + una cascada


@pytest.mark.asyncio
async def test_barrido_lock_tomado_por_otro_proceso_se_saltea():
    """Anti-doble-cascada: con el lock `espera:cascada:*` tomado, este tick no toca la entry."""
    from app.worker import espera_jobs

    mundo = _mundo()
    await _ofrecer_inicial(mundo)
    clave = f"espera:cascada:1:1:{HUECO_INI.isoformat()}"

    with freeze_time(T0 + timedelta(hours=2, minutes=1)):
        # el lock se toma DENTRO del freeze: FakeRedis usa time.monotonic (también congelado)
        await mundo["tienda"].set(clave, "otro-proceso", ex=900, nx=True)
        stats = await espera_jobs.barrido_vencidas(**mundo)

    assert stats["skips"] == 1 and stats["vencidas"] == 0
    assert (await mundo["espera_repo"].get(1)).estado == "ofrecida"
    assert await mundo["tienda"].get(clave) == "otro-proceso"  # no pisa ni borra el lock ajeno


@pytest.mark.asyncio
async def test_barrido_libera_su_lock_al_terminar():
    """redis-patterns: el lock propio se libera en finally (verificando token)."""
    from app.worker import espera_jobs

    mundo = _mundo()
    await _ofrecer_inicial(mundo)

    with freeze_time(T0 + timedelta(hours=2, minutes=1)):
        await espera_jobs.barrido_vencidas(**mundo)

    assert mundo["tienda"]._datos == {}  # ninguna clave espera:cascada:* colgada


@pytest.mark.asyncio
async def test_barrido_un_fallo_no_frena_las_demas_y_hace_rollback():
    """Un error en una cascada no tira el barrido: se cuenta, se hace rollback y sigue."""
    from app.worker import espera_jobs

    mundo = _mundo(n_entradas=2)
    await _ofrecer_inicial(mundo)
    # segunda oferta vencida en OTRO hueco, procesada después
    await mundo["espera_repo"].crear(
        paciente_id=2, profesional_id=1, estado="ofrecida", token_oferta_hash="h-otra",
        oferta_expira_en=T0 + timedelta(hours=1),
        oferta_hueco={"profesional_id": 1, "sillon_id": 1,
                      "inicio": (HUECO_INI + timedelta(days=1)).isoformat(),
                      "fin": (HUECO_FIN + timedelta(days=1)).isoformat()},
    )
    llamadas = {"rollback": 0, "commit": 0}

    async def rollback():
        llamadas["rollback"] += 1

    async def commit():
        llamadas["commit"] += 1

    original = mundo["profesionales_repo"].get
    primera_vez = {"v": True}

    async def get_roto(id):
        if primera_vez["v"]:
            primera_vez["v"] = False
            raise RuntimeError("falla transitoria (fake)")
        return await original(id)

    mundo["profesionales_repo"].get = get_roto
    with freeze_time(T0 + timedelta(hours=3)):
        stats = await espera_jobs.barrido_vencidas(commit=commit, rollback=rollback, **mundo)

    assert stats["errores"] == 1
    assert llamadas["rollback"] == 1
    assert llamadas["commit"] >= 1  # la otra entry sí se procesó y persistió
    assert (await mundo["espera_repo"].get(1)).estado == "vencida"  # la sana sí se procesó
    assert (await mundo["espera_repo"].get(2)).estado == "ofrecida"  # y encadenó


def test_worker_main_suma_bucle_espera_y_commitea():
    """Task 6.1 RED: main conserva heartbeat+bucle_notif y suma bucle_espera(600 s) que hace commit."""
    import asyncio
    import inspect

    import app.worker.main as main

    assert asyncio.iscoroutinefunction(main.bucle_espera)
    assert inspect.signature(main.bucle_espera).parameters["intervalo_s"].default == 600.0
    src_main = inspect.getsource(main.main)
    assert "heartbeat" in src_main and "bucle_notif" in src_main and "bucle_espera" in src_main
    assert "commit" in inspect.getsource(main.bucle_espera)  # sin commit el barrido se pierde


@pytest.mark.asyncio
async def test_barrido_lock_redis_real_con_ttl_y_liberado():
    """Task 6.1 (Redis real): el lock se toma con TTL <= 900 s y se libera (skipea sin Docker)."""
    import os

    try:
        import redis.asyncio as aioredis
    except ImportError:
        pytest.skip("redis no instalado")
    tienda = aioredis.from_url(os.getenv("REDIS_URL_TEST", "redis://localhost:6379/0"), decode_responses=True)
    try:
        await tienda.ping()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Redis no reachable (¿compose down / sin Docker?): {exc}")
    from app.worker import espera_jobs

    try:
        mundo = _mundo()
        mundo["tienda"] = tienda
        await _ofrecer_inicial(mundo)
        clave = f"espera:cascada:1:1:{HUECO_INI.isoformat()}"
        assert await tienda.set(clave, "ajeno", ex=900, nx=True)
        with freeze_time(T0 + timedelta(hours=2, minutes=1)):
            skip = await espera_jobs.barrido_vencidas(**mundo)
        assert skip["skips"] == 1 and 0 < await tienda.ttl(clave) <= 900
        await tienda.delete(clave)
        with freeze_time(T0 + timedelta(hours=2, minutes=1)):
            ok = await espera_jobs.barrido_vencidas(**mundo)
        assert ok["vencidas"] == 1 and await tienda.exists(clave) == 0
    finally:
        async for k in tienda.scan_iter("espera:cascada:*"):
            await tienda.delete(k)
        await tienda.aclose()
