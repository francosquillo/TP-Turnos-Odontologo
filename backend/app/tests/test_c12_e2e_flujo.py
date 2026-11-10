"""C-12 4.2: recorrido E2E de la demo a nivel API, sobre la base sembrada (D-07). Postgres real.

Reserva con el telefono del paciente demo con plan -> confirmar con token -> agenda ->
`asistido` -> historia y hallazgo -> presupuesto (presentar y aceptar) -> cobrar en caja ->
liquidacion (generar, presentar, cobrar) -> cierre de caja con diferencia 0.

El orden es el de D-07: cobrar una liquidacion registra un ingreso en la caja de hoy, y con la
caja de hoy cerrada responde 409; por eso el cierre va al final. Parte de `run_seed` (no crea
cajas ni recibos). `freezegun` fija un lunes dentro del horario del profesional demo y los
tokens se emiten dentro del tiempo congelado (un `iat` futuro daria 401). El catalogo de
estados de hallazgo se carga en el test, no se asume. Datos ficticios.
"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from freezegun import freeze_time

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente  # noqa: E402
from c10_helpers import clave_nueva  # noqa: E402
from db_utils import cargar_catalogo_estados, sesion_pg  # noqa: E402, F401

# Lunes 2026-11-02, 12:00 en Buenos Aires. El profesional demo atiende los lunes 14:00-18:00.
AHORA = "2026-11-02 15:00:00"
HOY = date(2026, 11, 2)
INICIO = "2026-11-02T17:00:00Z"  # 14:00 BA
FIN = "2026-11-02T17:30:00Z"


def _arancel_vigente(plan: str, codigo: str, hoy: date) -> Decimal:
    from app.db.seed import ARANCELES_DEMO

    vigentes = [
        precio for p, c, precio, desde, hasta in ARANCELES_DEMO
        if p == plan and c == codigo and desde <= hoy and (hasta is None or hoy <= hasta)
    ]
    assert len(vigentes) == 1, "el seed debe dejar un unico arancel vigente"
    return vigentes[0]


def _precio_base(codigo: str) -> Decimal:
    from app.db.seed import TRATAMIENTOS_DEMO

    return next(precio for c, _, precio in TRATAMIENTOS_DEMO if c == codigo)


@pytest.mark.asyncio
async def test_e2e_demo_de_la_reserva_al_cierre_de_caja(sesion_pg, monkeypatch):
    from sqlalchemy import func, select

    from app.core.deps import get_redis
    from app.core.security import crear_access_token
    from app.db.seed import (
        ODONTOLOGO_DEMO_EMAIL, PACIENTES_DEMO, PROFESIONAL_DEMO_MATRICULA, SECRETARIA_DEMO_EMAIL,
        SILLON_DEMO_NOMBRE, run_seed,
    )
    from app.modelos import (
        Caja, ObraSocial, Paciente, Profesional, Recibo, Sillon, Tratamiento, Turno, Usuario,
    )
    from c03_fakes import FakeStore

    monkeypatch.setenv("SEED_ADMIN_EMAIL", "admin@demo.test")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "demo-ficticia-123")
    # Seed "en el pasado": su horizonte (turnos, cajas) no pisa el dia congelado del flujo.
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo as _ZI
    await run_seed(sesion_pg, ahora=_dt(2026, 10, 1, 8, 0, tzinfo=_ZI("America/Argentina/Buenos_Aires")))
    await cargar_catalogo_estados(sesion_pg)

    # El ultimo Plan Base: los primeros pacientes ya traen historia clinica del seed rico.
    demo = [p for p in PACIENTES_DEMO if p.plan == "Plan Base"][-1]
    paciente_id = await sesion_pg.scalar(select(Paciente.id).where(Paciente.dni == demo.dni))
    profesional_id = await sesion_pg.scalar(
        select(Profesional.id).where(Profesional.matricula == PROFESIONAL_DEMO_MATRICULA))
    sillon_id = await sesion_pg.scalar(select(Sillon.id).where(Sillon.nombre == SILLON_DEMO_NOMBRE))
    os_id = await sesion_pg.scalar(select(ObraSocial.id).where(ObraSocial.nombre == "OS Ficticia Demo"))
    tratamiento_id = await sesion_pg.scalar(select(Tratamiento.id).where(Tratamiento.codigo == "OBT-001"))
    usuarios = {
        rol: (await sesion_pg.scalar(select(Usuario.id).where(Usuario.email == email)), rol)
        for rol, email in (("admin", "admin@demo.test"), ("odontologo", ODONTOLOGO_DEMO_EMAIL),
                           ("secretaria", SECRETARIA_DEMO_EMAIL))
    }
    pacientes_antes = await sesion_pg.scalar(select(func.count()).select_from(Paciente))
    # Contrato del seed rico: ya hay cajas pasadas cerradas y recibos demo; el flujo suma uno mas.
    assert await sesion_pg.scalar(
        select(func.count()).select_from(Caja).where(Caja.estado == "abierta")) == 0
    recibos_antes = await sesion_pg.scalar(select(func.count()).select_from(Recibo))

    precio = _precio_base("OBT-001")
    cubierto = min(_arancel_vigente("Plan Base", "OBT-001", HOY), precio)
    a_cargo = precio - cubierto

    cli, _, app = await armar_cliente(sesion_pg)  # confirma lo sembrado antes de operar
    tienda = FakeStore()
    app.dependency_overrides[get_redis] = lambda: tienda
    # Warmup: FastAPI compila el TypeAdapter de cada body de forma perezosa y freezegun
    # parchea `datetime`, con lo que Pydantic no puede construirlo dentro del freeze.
    from fastapi._compat import get_cached_model_fields
    from pydantic import BaseModel

    for ruta in app.routes:
        cuerpo = getattr(getattr(ruta, "dependant", None), "body_params", None) or []
        if len(cuerpo) == 1 and isinstance(cuerpo[0].type_, type) and issubclass(cuerpo[0].type_, BaseModel):
            get_cached_model_fields(cuerpo[0].type_)

    with freeze_time(AHORA, tz_offset=0, real_asyncio=True):
        def hdr(rol: str) -> dict[str, str]:
            uid, nombre = usuarios[rol]
            return {"Authorization": f"Bearer {crear_access_token(uid, nombre)}"}

        async with cli:
            # 1. Reserva publica con el telefono del paciente demo: reutiliza su ficha.
            r = await cli.post("/reservas", json={
                "profesional_id": profesional_id, "sillon_id": sillon_id, "inicio": INICIO,
                "fin": FIN, "nombre": demo.nombre, "telefono": f"+{demo.telefono}"})
            assert r.status_code == 201, r.text
            token, turno_id = r.json()["token"], r.json()["turno_id"]

            # 2. El paciente confirma con el link.
            r = await cli.get(f"/confirmar/{token}")
            assert r.status_code == 200 and r.json()["estado"] == "confirmado"

            # 3. La secretaria ve el turno en la agenda del dia, con el nombre del paciente.
            r = await cli.get("/agenda?vista=dia&fecha=2026-11-02", headers=hdr("secretaria"))
            assert r.status_code == 200, r.text
            item = next(t for t in r.json() if t["id"] == turno_id)
            assert item["paciente_id"] == paciente_id and demo.nombre in (item["paciente_nombre"] or "")

            # 4. El odontologo del profesional demo marca asistido.
            r = await cli.patch(f"/turnos/{turno_id}/estado", json={"estado": "asistido"},
                                headers=hdr("odontologo"))
            assert r.status_code == 200 and r.json()["estado"] == "asistido", r.text

            # 5. Abre la historia y registra una caries en 16 oclusal.
            r = await cli.post("/historias", json={"paciente_id": paciente_id}, headers=hdr("odontologo"))
            assert r.status_code == 201, r.text
            hc_id = r.json()["id"]
            r = await cli.post(f"/odontograma/{hc_id}/hallazgos", headers=hdr("odontologo"),
                               json={"pieza_fdi": 16, "cara": "oclusal", "estado": "caries"})
            assert r.status_code == 201, r.text
            hallazgo_id = r.json()["hallazgo"]["id"]

            # 6. Presupuesta la obturacion, la presenta y el paciente acepta con cobertura.
            r = await cli.post("/presupuestos", headers=hdr("odontologo"), json={
                "paciente_id": paciente_id,
                "items": [{"hallazgo_id": hallazgo_id, "tratamiento_id": tratamiento_id, "cantidad": 1}]})
            assert r.status_code == 201, r.text
            presupuesto_id = r.json()["id"]
            assert (await cli.post(f"/presupuestos/{presupuesto_id}/presentar",
                                   headers=hdr("odontologo"))).status_code == 200
            r = await cli.post(f"/presupuestos/{presupuesto_id}/aceptar", headers=hdr("odontologo"))
            assert r.status_code == 200 and r.json()["estado"] == "aceptado", r.text
            cuenta = (await cli.get(f"/cuentas/{paciente_id}", headers=hdr("secretaria"))).json()
            assert Decimal(cuenta["saldo"]) == a_cargo
            assert [Decimal(p["pendiente"]) for p in cuenta["pendientes"]] == [a_cargo]

            # 7. Cobro en caja: la seed no dejo una caja pendiente, asi que no hay 409.
            r = await cli.post("/caja/cobrar", headers=hdr("secretaria"), json={
                "presupuesto_id": presupuesto_id, "monto": f"{a_cargo:.2f}", "medio": "efectivo",
                "clave_idempotencia": clave_nueva()})
            assert r.status_code == 201, r.text
            assert r.json()["presupuesto_estado"] == "cobrado"

            # 8. Liquidacion del mes: generar, presentar y cobrar.
            r = await cli.post("/liquidaciones", json={"os_id": os_id, "periodo": "2026-11"},
                               headers=hdr("admin"))
            assert r.status_code == 201, r.text
            assert Decimal(r.json()["total"]) == cubierto
            liquidacion_id = r.json()["id"]
            r = await cli.post(f"/liquidaciones/{liquidacion_id}/presentar", headers=hdr("admin"))
            assert r.status_code == 200 and r.json()["estado"] == "presentada", r.text
            r = await cli.post(f"/liquidaciones/{liquidacion_id}/cobrar",
                               json={"medio": "transferencia"}, headers=hdr("admin"))
            assert r.status_code == 200 and r.json()["estado"] == "cobrada", r.text

            # 9. Cierre de caja: lo cobrado al paciente mas lo que pago la obra social.
            estado = (await cli.get("/caja", headers=hdr("secretaria"))).json()
            assert Decimal(estado["caja"]["total_sistema"]) == a_cargo + cubierto == precio
            r = await cli.post("/caja/cierre", headers=hdr("secretaria"), json={
                "caja_id": estado["caja"]["id"], "total_contado": f"{precio:.2f}"})
            assert r.status_code == 200 and Decimal(r.json()["diferencia"]) == 0, r.text

    # El telefono reutilizo la ficha demo: no aparecio ningun paciente nuevo.
    assert await sesion_pg.scalar(select(func.count()).select_from(Paciente)) == pacientes_antes
    turno = await sesion_pg.get(Turno, turno_id)
    assert turno.paciente_id == paciente_id and turno.estado == "asistido"
    assert await sesion_pg.scalar(select(func.count()).select_from(Recibo)) == recibos_antes + 1
