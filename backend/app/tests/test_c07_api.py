"""C-07 grupo 4.1: endpoints lista de espera (staff + públicos) con fakes HTTP.

Siempre corre (sin PG/Redis). Cubre RBAC, CRUD con baja lógica, ofrecer
manual, convertir staff y los públicos aceptar/rechazar/oferta con la
persistencia correcta (commit cuando el servicio ya mutó: expirado, hueco
tomado). Datos 100% ficticios.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c03_fakes import fabricar_usuario  # noqa: E402
from c04_fakes import fabricar_turno  # noqa: E402
from c05_fakes import fabricar_paciente  # noqa: E402
from c07_fakes import armar_app, fabricar_entry  # noqa: E402

# Lunes 16/11/2026 09:00 BA (12:00 UTC): futuro respecto de "hoy" real del suite.
HUECO_INI = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
HUECO_FIN = HUECO_INI + timedelta(minutes=30)
STAFF = [fabricar_usuario(id=1, rol="secretaria"), fabricar_usuario(id=2, rol="odontologo", email="odo@demo.test"),
         fabricar_usuario(id=3, rol="admin", email="adm@demo.test")]
PACIENTES = [fabricar_paciente(id=1, nombre="Ana", telefono="1140001111"),
             fabricar_paciente(id=2, nombre="Beto", telefono="1140002222")]


def _hueco_json(**cambios):
    datos = {"profesional_id": 1, "sillon_id": 1, "inicio": HUECO_INI.isoformat(),
             "fin": HUECO_FIN.isoformat(), "turno_id": 5}
    datos.update(cambios)
    return datos


def _oferta(id, token_hash, **cambios):
    """Entry ya `ofrecida` con ventana vigente respecto del reloj real."""
    ahora = datetime.now(timezone.utc)
    datos = {
        "estado": "ofrecida", "token_oferta_hash": token_hash,
        "oferta_expira_en": ahora + timedelta(hours=1),
        "oferta_hueco": {"profesional_id": 1, "sillon_id": 1, "inicio": HUECO_INI.isoformat(),
                         "fin": HUECO_FIN.isoformat(), "turno_id": 5},
    }
    datos.update(cambios)
    return fabricar_entry(id, **datos)


# --- 4.1 CRUD staff ------------------------------------------------------------

@pytest.mark.asyncio
async def test_crud_staff_ok():
    """Task 4.1 RED: secretaria da de alta, lista FIFO, edita, consulta y da de baja con motivo."""
    _, cli, bearer, mundo = armar_app(usuarios=STAFF, pacientes=PACIENTES)
    h = bearer(1, "secretaria")
    async with cli:
        a = await cli.post("/lista-espera", json={"paciente_id": 1, "profesional_id": 1}, headers=h)
        b = await cli.post("/lista-espera", json={
            "paciente_id": 2, "especialidad": "Odontología general",
            "preferencia_horaria": {"dias": ["lunes"], "desde": "09:00", "hasta": "13:00"},
        }, headers=h)
        assert a.status_code == 201 and b.status_code == 201, (a.text, b.text)
        assert a.json()["estado"] == "activa" and a.json()["paciente_id"] == 1
        assert b.json()["preferencia_horaria"] == {"dias": ["lunes"], "desde": "09:00", "hasta": "13:00"}

        lista = await cli.get("/lista-espera", headers=h)
        assert [e["id"] for e in lista.json()] == [a.json()["id"], b.json()["id"]]  # FIFO

        editado = await cli.patch(f"/lista-espera/{b.json()['id']}", json={"especialidad": "Ortodoncia"}, headers=h)
        assert editado.status_code == 200 and editado.json()["especialidad"] == "Ortodoncia"

        detalle = await cli.get(f"/lista-espera/{a.json()['id']}", headers=h)
        assert detalle.status_code == 200 and detalle.json()["id"] == a.json()["id"]

        baja = await cli.post(f"/lista-espera/{a.json()['id']}/baja", json={"motivo_baja": "ya se atendió"}, headers=h)
        assert baja.status_code == 200
        assert baja.json()["estado"] == "vencida" and baja.json()["motivo_baja"] == "ya se atendió"

        solo_activas = await cli.get("/lista-espera?estado=activa", headers=h)
        assert [e["id"] for e in solo_activas.json()] == [b.json()["id"]]
    assert mundo.sesion.commits >= 4


@pytest.mark.asyncio
async def test_crud_sin_bearer_401():
    """Task 4.1 RED: sin Bearer los endpoints staff responden 401."""
    _, cli, _, mundo = armar_app(usuarios=STAFF, pacientes=PACIENTES, entradas=[fabricar_entry(1)])
    async with cli:
        for metodo, ruta in (("get", "/lista-espera"), ("get", "/lista-espera/1")):
            resp = await getattr(cli, metodo)(ruta)
            assert resp.status_code == 401, ruta
        alta = await cli.post("/lista-espera", json={"paciente_id": 1, "profesional_id": 1})
        assert alta.status_code == 401
        ofrecer = await cli.post("/lista-espera/1/ofrecer", json=_hueco_json())
        assert ofrecer.status_code == 401
    assert (await mundo.espera.get(1)).estado == "activa"


@pytest.mark.asyncio
async def test_crud_rol_no_staff_403():
    """Task 4.1: un odontólogo no administra la cola (solo secretaria|admin)."""
    _, cli, bearer, _ = armar_app(usuarios=STAFF, pacientes=PACIENTES, entradas=[fabricar_entry(1)])
    async with cli:
        resp = await cli.get("/lista-espera", headers=bearer(2, "odontologo"))
        assert resp.status_code == 403
        admin = await cli.get("/lista-espera", headers=bearer(3, "admin"))
        assert admin.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("cuerpo", [
    {"paciente_id": 1},                                            # sin destino
    {"paciente_id": 1, "profesional_id": 1, "extra": "x"},         # extra='forbid'
    {"paciente_id": 99, "profesional_id": 1},                      # paciente inexistente
    {"paciente_id": 1, "profesional_id": 99},                      # profesional inexistente
    {"paciente_id": 1, "profesional_id": 1, "preferencia_horaria": {"desde": "9am"}},  # franja inválida
])
async def test_alta_invalida_422(cuerpo):
    """Task 4.1: alta inválida -> 422 y nada se crea."""
    _, cli, bearer, mundo = armar_app(usuarios=STAFF, pacientes=PACIENTES)
    async with cli:
        resp = await cli.post("/lista-espera", json=cuerpo, headers=bearer(1, "secretaria"))
    assert resp.status_code == 422, resp.text
    assert await mundo.espera.listar_fifo() == []


@pytest.mark.asyncio
async def test_no_existe_delete_fisico():
    """RN-GL-01: la baja es lógica; no hay DELETE de la entry."""
    _, cli, bearer, mundo = armar_app(usuarios=STAFF, pacientes=PACIENTES, entradas=[fabricar_entry(1)])
    async with cli:
        resp = await cli.delete("/lista-espera/1", headers=bearer(1, "secretaria"))
    assert resp.status_code == 405
    assert await mundo.espera.get(1) is not None


# --- 4.1 ofrecer manual ----------------------------------------------------------

@pytest.mark.asyncio
async def test_ofrecer_manual_staff_ok():
    """Task 4.1 RED: staff ofrece un hueco a una entry puntual -> ofrecida + countdown + aviso."""
    _, cli, bearer, mundo = armar_app(
        usuarios=STAFF, pacientes=PACIENTES, entradas=[fabricar_entry(1), fabricar_entry(2, paciente_id=2)],
        turnos=[fabricar_turno(id=5, estado="cancelado", inicio=HUECO_INI, fin=HUECO_FIN)],
    )
    antes = datetime.now(timezone.utc)
    async with cli:
        resp = await cli.post("/lista-espera/2/ofrecer", json=_hueco_json(), headers=bearer(1, "secretaria"))
    despues = datetime.now(timezone.utc)

    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert cuerpo["estado"] == "ofrecida" and cuerpo["id"] == 2
    expira = datetime.fromisoformat(cuerpo["oferta_expira_en"])
    assert antes + timedelta(hours=2) <= expira <= despues + timedelta(hours=2)
    assert (await mundo.espera.get(1)).estado == "activa"  # saltea la cola: la 1ª no se toca
    assert mundo.sesion.commits == 1
    assert [e["destinatario"] for e in mundo.cliente.envios] == ["1140002222"]


@pytest.mark.asyncio
async def test_ofrecer_manual_errores():
    """Task 4.1: 404 inexistente, 409 no activa, 422 hueco inválido; nada se muta."""
    _, cli, bearer, mundo = armar_app(
        usuarios=STAFF, pacientes=PACIENTES,
        entradas=[fabricar_entry(1, estado="vencida", motivo_baja="rechazo_paciente")],
    )
    h = bearer(1, "secretaria")
    async with cli:
        assert (await cli.post("/lista-espera/99/ofrecer", json=_hueco_json(), headers=h)).status_code == 404
        assert (await cli.post("/lista-espera/1/ofrecer", json=_hueco_json(), headers=h)).status_code == 409
        invertido = _hueco_json(inicio=HUECO_FIN.isoformat(), fin=HUECO_INI.isoformat())
        assert (await cli.post("/lista-espera/1/ofrecer", json=invertido, headers=h)).status_code == 422
    assert (await mundo.espera.get(1)).estado == "vencida"
    assert mundo.cliente.envios == []


# --- 4.1 convertir (staff) -------------------------------------------------------

@pytest.mark.asyncio
async def test_convertir_staff_crea_confirmado_origen_lista_espera():
    """Task 3.2/4.1: staff convierte (aceptó por teléfono) -> turno confirmado, sin sobreturno."""
    _, cli, bearer, mundo = armar_app(
        usuarios=STAFF, pacientes=PACIENTES, entradas=[_oferta(1, "hash-staff")],
    )
    async with cli:
        resp = await cli.post("/lista-espera/1/convertir", headers=bearer(1, "secretaria"))

    assert resp.status_code == 200, resp.text
    turno = await mundo.turnos.get(resp.json()["turno_id"])
    assert (turno.estado, turno.origen, turno.sobre_turno) == ("confirmado", "lista_espera", False)
    entrada = await mundo.espera.get(1)
    assert entrada.estado == "convertida"
    assert entrada.token_oferta_hash == "hash-staff"  # tombstone: el reuso del link responde 410, no 404
    assert mundo.sesion.commits == 1


@pytest.mark.asyncio
async def test_convertir_staff_sin_oferta_vigente_409():
    """Task 4.1: convertir una entry activa (sin oferta) -> 409, nada se crea."""
    _, cli, bearer, mundo = armar_app(usuarios=STAFF, pacientes=PACIENTES, entradas=[fabricar_entry(1)])
    async with cli:
        resp = await cli.post("/lista-espera/1/convertir", headers=bearer(1, "secretaria"))
    assert resp.status_code == 409
    assert (await mundo.espera.get(1)).estado == "activa"


# --- 3.x públicos aceptar / rechazar / oferta ------------------------------------

@pytest.mark.asyncio
async def test_aceptar_publico_sin_bearer_confirma_y_reuso_410():
    """Task 3.1/3.2: aceptar con token (sin Bearer) confirma; el reuso es 410 sin cambios."""
    from app.servicios.reserva_servicio import generar_token, hash_token

    token = generar_token()
    _, cli, _, mundo = armar_app(
        usuarios=STAFF, pacientes=PACIENTES, entradas=[_oferta(1, hash_token(token))],
    )
    async with cli:
        ok = await cli.post(f"/lista-espera/aceptar/{token}")
        reuso = await cli.post(f"/lista-espera/aceptar/{token}")
        desconocido = await cli.post(f"/lista-espera/aceptar/{generar_token()}")

    assert ok.status_code == 200 and ok.json()["detail"] == "aceptado"
    turno = await mundo.turnos.get(ok.json()["turno_id"])
    assert (turno.estado, turno.origen) == ("confirmado", "lista_espera")
    assert reuso.status_code == 410
    assert desconocido.status_code == 404


@pytest.mark.asyncio
async def test_aceptar_expirado_410_persiste_vencida_y_cascada():
    """Task 3.1: ventana vencida -> 410, la entry queda vencida 'expirada' y se ofrece al siguiente (commit)."""
    from app.servicios.reserva_servicio import generar_token, hash_token

    token = generar_token()
    vencida = _oferta(1, hash_token(token), oferta_expira_en=datetime.now(timezone.utc) - timedelta(minutes=1))
    _, cli, _, mundo = armar_app(
        usuarios=STAFF, pacientes=PACIENTES, entradas=[vencida, fabricar_entry(2, paciente_id=2)],
    )
    async with cli:
        resp = await cli.post(f"/lista-espera/aceptar/{token}")

    assert resp.status_code == 410
    e1, e2 = await mundo.espera.get(1), await mundo.espera.get(2)
    assert (e1.estado, e1.motivo_baja) == ("vencida", "expirada")
    assert e2.estado == "ofrecida"
    assert mundo.sesion.commits == 1 and mundo.sesion.rollbacks == 0  # lo mutado NO se descarta


@pytest.mark.asyncio
async def test_aceptar_hueco_tomado_409_persiste_cascada():
    """Task 3.2: hueco ocupado entre oferta y aceptación -> 409 con alternativas + vencida + siguiente ofrecida."""
    from app.servicios.reserva_servicio import generar_token, hash_token

    token = generar_token()
    ocupado = fabricar_turno(id=9, estado="confirmado", inicio=HUECO_INI, fin=HUECO_FIN)
    _, cli, _, mundo = armar_app(
        usuarios=STAFF, pacientes=PACIENTES, turnos=[ocupado],
        entradas=[_oferta(1, hash_token(token)), fabricar_entry(2, paciente_id=2)],
    )
    async with cli:
        resp = await cli.post(f"/lista-espera/aceptar/{token}")

    assert resp.status_code == 409
    assert "alternativas" in resp.json()
    e1, e2 = await mundo.espera.get(1), await mundo.espera.get(2)
    assert (e1.estado, e1.motivo_baja) == ("vencida", "hueco_tomado")
    assert e2.estado == "ofrecida"
    assert mundo.sesion.commits == 1 and mundo.sesion.rollbacks == 0


@pytest.mark.asyncio
async def test_rechazar_publico_libera_y_ofrece_siguiente():
    """Task 3.3: rechazar (sin Bearer) -> vencida 'rechazo_paciente' + siguiente ofrecida; reuso 410, desconocido 404."""
    from app.servicios.reserva_servicio import generar_token, hash_token

    token = generar_token()
    _, cli, _, mundo = armar_app(
        usuarios=STAFF, pacientes=PACIENTES,
        entradas=[_oferta(1, hash_token(token)), fabricar_entry(2, paciente_id=2)],
    )
    async with cli:
        ok = await cli.post(f"/lista-espera/rechazar/{token}")
        otra_vez = await cli.post(f"/lista-espera/rechazar/{token}")
        inexistente = await cli.post(f"/lista-espera/rechazar/{generar_token()}")

    assert ok.status_code == 200
    e1, e2 = await mundo.espera.get(1), await mundo.espera.get(2)
    assert (e1.estado, e1.motivo_baja) == ("vencida", "rechazo_paciente")
    assert e2.estado == "ofrecida"
    assert otra_vez.status_code == 410  # token ya consumido (no es "desconocido")
    assert inexistente.status_code == 404


@pytest.mark.asyncio
async def test_oferta_publica_detalle_minimo_sin_phi():
    """Página pública: nombre de pila + horario + vencimiento; 404 desconocido, 410 expirada. No muta."""
    from app.servicios.reserva_servicio import generar_token, hash_token

    token, vencido = generar_token(), generar_token()
    entradas = [
        _oferta(1, hash_token(token)),
        _oferta(2, hash_token(vencido), oferta_expira_en=datetime.now(timezone.utc) - timedelta(seconds=1)),
    ]
    _, cli, _, mundo = armar_app(usuarios=STAFF, pacientes=PACIENTES, entradas=entradas)
    async with cli:
        ok = await cli.get(f"/lista-espera/oferta/{token}")
        expirada = await cli.get(f"/lista-espera/oferta/{vencido}")
        desconocida = await cli.get(f"/lista-espera/oferta/{generar_token()}")

    assert ok.status_code == 200
    assert set(ok.json()) == {"nombre_pila", "inicio", "fin", "oferta_expira_en"}  # sin apellido/teléfono/clínica
    assert ok.json()["nombre_pila"] == "Ana"
    assert expirada.status_code == 410
    assert desconocida.status_code == 404
    assert (await mundo.espera.get(2)).estado == "ofrecida"  # un GET jamás muta
    assert mundo.sesion.commits == 0
