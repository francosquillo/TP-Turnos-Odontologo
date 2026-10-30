"""C-07 grupo 5: aviso de oferta por canal C-06 + plantilla seed (D-07, RN-NO-04).

Con fakes (siempre corre): la oferta cuelga una Notificacion
`oferta_lista_espera` del turno cancelado que liberó el hueco; payload sin
PHI y con fecha/hora DEL HUECO (no del vencimiento); sin número válido la
fila queda `fallida` pero la entry sigue `ofrecida`; en cascada el mismo
turno ofrece a varios pacientes sin chocar con el UNIQUE parcial.
Datos 100% ficticios.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]  # backend/app/tests -> backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c05_fakes import FakePacienteRepo, fabricar_paciente  # noqa: E402
from c04_fakes import FakeTurnoRepo  # noqa: E402
from c06_fakes import CuentaCliente, FakeNotifRepo, FakeRedis  # noqa: E402

# 12:00 UTC = 09:00 en Buenos Aires (UTC-3): distingue hora del hueco vs. vencimiento.
HUECO_INI = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
HUECO_FIN = HUECO_INI + timedelta(minutes=30)
AHORA = HUECO_INI - timedelta(hours=5)  # 07:00 UTC = 04:00 BA: el hueco es futuro
TURNO_CANCELADO = 77


def _entry(id, paciente_id, **cambios):
    datos = {
        "id": id, "paciente_id": paciente_id, "profesional_id": 1,
        "especialidad": None, "preferencia_horaria": None, "estado": "activa",
        "oferta_expira_en": None, "token_oferta_hash": None,
        "oferta_hueco": None, "motivo_baja": None,
        "created_at": AHORA + timedelta(minutes=id),
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


class _EsperaRepo:
    def __init__(self, entradas):
        self._e = {e.id: e for e in entradas}

    async def get(self, id):
        return self._e.get(id)

    async def actualizar(self, entidad, **cambios):
        for k, v in cambios.items():
            setattr(entidad, k, v)
        return entidad

    async def activas_compatibles(self, profesional_id=None, especialidades_profesional="", inicio=None, preferencia_horaria=None):
        return sorted((e for e in self._e.values() if e.estado == "activa"), key=lambda e: e.created_at)

    async def get_by_token_hash(self, token_hash):
        return next((e for e in self._e.values() if e.token_oferta_hash == token_hash), None)


class _Pros:
    async def get(self, id):
        return SimpleNamespace(id=id, especialidades="Odontología general")


def _mundo(entradas, pacientes):
    return dict(
        espera_repo=_EsperaRepo(entradas), turnos_repo=FakeTurnoRepo(),
        profesionales_repo=_Pros(), sillones_repo=_Pros(),
        pacientes_repo=FakePacienteRepo(pacientes), notif_repo=FakeNotifRepo(),
        tienda=FakeRedis(), cliente=CuentaCliente(),
    )


def _hueco(**cambios):
    datos = {"profesional_id": 1, "sillon_id": 1, "inicio": HUECO_INI,
             "fin": HUECO_FIN, "turno_id": TURNO_CANCELADO}
    datos.update(cambios)
    return datos


# --- 5.1 seed ---------------------------------------------------------------

def test_seed_oferta_idempotente():
    """Task 5.1 RED: doble seed -> 6 plantillas v1, con oferta_lista_espera declarada."""
    from app.core.seed_plantillas import (
        PLANTILLAS_V1, contar_plantillas, sembrar_plantillas, variables_declaradas,
    )

    almacen: dict = {}
    assert sembrar_plantillas(almacen) == 6
    assert sembrar_plantillas(almacen) == 6  # idempotente: no duplica
    assert contar_plantillas(almacen) == 6
    assert "oferta_lista_espera" in PLANTILLAS_V1
    assert set(variables_declaradas("oferta_lista_espera")) == {
        "nombre_pila", "fecha", "hora", "expira_en", "link_oferta",
    }


# --- 5.1 ofrecer encola la notificación -------------------------------------

@pytest.mark.asyncio
async def test_oferta_encola_notificacion():
    """Task 5.1 RED: ofrecer -> fila oferta_lista_espera enviada, colgada del turno cancelado."""
    from app.servicios import lista_espera_servicio as svc

    mundo = _mundo(
        [_entry(1, 1)],
        [fabricar_paciente(id=1, nombre="Ana", telefono="1140001111")],
    )
    ofrecida = await svc.intentar_ofrecer(hueco=_hueco(), ahora=AHORA, **mundo)

    assert ofrecida.estado == "ofrecida"
    filas = list(mundo["notif_repo"]._filas.values())
    assert len(filas) == 1
    fila = filas[0]
    assert fila.plantilla == "oferta_lista_espera"
    assert fila.turno_id == TURNO_CANCELADO  # FK al turno que liberó el hueco
    assert fila.estado == "enviada"
    assert fila.destinatario_ref == "1140001111"
    assert len(mundo["cliente"].envios) == 1
    # fecha/hora del HUECO en TZ BA (09:00), no del vencimiento ni UTC.
    assert fila.payload["fecha"] == "12/10"
    assert fila.payload["hora"] == "09:00"
    assert fila.payload["nombre_pila"] == "Ana"
    assert fila.payload["expira_en"] == "12/10 06:00"  # AHORA(04:00 BA) + 2 h, en TZ BA


# --- 5.2 sin PHI ------------------------------------------------------------

@pytest.mark.asyncio
async def test_oferta_sin_phi():
    """Task 5.2 RED: plantilla + payload real no matchean la lista bloqueada."""
    from app.core.seed_plantillas import PLANTILLAS_V1, TERMINOS_BLOQUEADOS, sin_phi
    from app.servicios import lista_espera_servicio as svc

    mundo = _mundo(
        [_entry(1, 1)],
        [fabricar_paciente(id=1, nombre="Ana", apellido="Ficticia", telefono="1140001111")],
    )
    await svc.intentar_ofrecer(hueco=_hueco(), ahora=AHORA, **mundo)

    cuerpo = PLANTILLAS_V1["oferta_lista_espera"]["cuerpo"].lower()
    assert not any(t in cuerpo for t in TERMINOS_BLOQUEADOS)
    payload = next(iter(mundo["notif_repo"]._filas.values())).payload
    assert set(payload) <= {"nombre_pila", "fecha", "hora", "expira_en", "link_oferta", "message_id"}
    assert sin_phi(" ".join(str(v) for v in payload.values()))
    assert "Ficticia" not in str(payload)  # nunca el apellido
    assert "1140001111" not in str(payload)  # nunca el teléfono


@pytest.mark.asyncio
async def test_oferta_sin_numero_sigue_en_ui():
    """Task 5.2 RED: teléfono inválido -> notif fallida, pero la entry sigue ofrecida."""
    from app.servicios import lista_espera_servicio as svc

    mundo = _mundo(
        [_entry(1, 1)],
        [fabricar_paciente(id=1, nombre="Ana", telefono=None, email=None)],
    )
    ofrecida = await svc.intentar_ofrecer(hueco=_hueco(), ahora=AHORA, **mundo)

    assert ofrecida.estado == "ofrecida"
    assert ofrecida.oferta_expira_en == AHORA + timedelta(hours=2)  # countdown
    fila = next(iter(mundo["notif_repo"]._filas.values()))
    assert fila.estado == "fallida"
    assert fila.ultimo_error == "sin_numero_valido"
    assert mundo["cliente"].envios == []  # nada salió por WhatsApp


# --- cascada: mismo turno cancelado, varios pacientes -----------------------

@pytest.mark.asyncio
async def test_cascada_avisa_al_siguiente_sin_chocar_con_unique():
    """El UNIQUE (turno, plantilla) no debe impedir avisar a la 2ª tras rechazar la 1ª."""
    from app.servicios import lista_espera_servicio as svc

    mundo = _mundo(
        [_entry(1, 1), _entry(2, 2)],
        [fabricar_paciente(id=1, nombre="Ana", telefono="1140001111"),
         fabricar_paciente(id=2, nombre="Beto", telefono="1140002222")],
    )
    primera = await svc.intentar_ofrecer(hueco=_hueco(), ahora=AHORA, **mundo)
    rechazo = await svc.rechazar_por_token(
        token_hash=primera.token_oferta_hash, ahora=AHORA + timedelta(minutes=10),
        **{k: v for k, v in mundo.items()},
    )

    assert rechazo is True
    segunda = await mundo["espera_repo"].get(2)
    assert segunda.estado == "ofrecida"
    assert [e["destinatario"] for e in mundo["cliente"].envios] == ["1140001111", "1140002222"]
    activas = [f for f in mundo["notif_repo"]._filas.values() if f.estado != "fallida"]
    assert len(activas) == 1 and activas[0].destinatario_ref == "1140002222"


@pytest.mark.asyncio
async def test_oferta_manual_sin_turno_origen_no_avisa_pero_ofrece():
    """Oferta manual sin turno de origen: sin FK donde colgar el aviso, la entry igual queda ofrecida."""
    from app.servicios import lista_espera_servicio as svc

    mundo = _mundo([_entry(1, 1)], [fabricar_paciente(id=1, nombre="Ana", telefono="1140001111")])
    mundo.pop("turnos_repo"); mundo.pop("profesionales_repo"); mundo.pop("sillones_repo"); mundo.pop("tienda")
    ofrecida = await svc.ofrecer_a_entry(
        entry_id=1, hueco=_hueco(turno_id=None), ahora=AHORA, **mundo,
    )

    assert ofrecida.estado == "ofrecida"
    assert mundo["notif_repo"]._filas == {}


@pytest.mark.asyncio
async def test_ofrecer_a_entry_no_activa_conflicto():
    """Ofrecer a una entry ya ofrecida/vencida es OfertaYaActivaError (409), sin mutar."""
    from app.servicios import lista_espera_servicio as svc

    entry = _entry(1, 1, estado="vencida", motivo_baja="rechazo_paciente")
    mundo = _mundo([entry], [fabricar_paciente(id=1)])
    for k in ("turnos_repo", "profesionales_repo", "sillones_repo", "tienda"):
        mundo.pop(k)

    with pytest.raises(svc.OfertaYaActivaError):
        await svc.ofrecer_a_entry(entry_id=1, hueco=_hueco(), ahora=AHORA, **mundo)
    with pytest.raises(svc.EntradaNoEncontradaError):
        await svc.ofrecer_a_entry(entry_id=99, hueco=_hueco(), ahora=AHORA, **mundo)
    assert entry.estado == "vencida"


@pytest.mark.asyncio
async def test_oferta_token_aleatorio_no_dispara_escaner_phi(monkeypatch):
    """El token opaco del link puede contener 'fdi' o 8+ digitos por azar: el aviso igual sale."""
    from app.servicios import lista_espera_servicio as svc

    monkeypatch.setattr(svc, "generar_token", lambda: "AbcFDIxyz-12345678901234")
    mundo = _mundo([_entry(1, 1)], [fabricar_paciente(id=1, nombre="Ana", telefono="1140001111")])

    await svc.intentar_ofrecer(hueco=_hueco(), ahora=AHORA, **mundo)

    assert len(mundo["cliente"].envios) == 1
    assert mundo["cliente"].envios[0]["variables"]["link_oferta"].endswith("AbcFDIxyz-12345678901234")
