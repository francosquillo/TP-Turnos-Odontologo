"""C-09 grupo 5: servicio de cuenta corriente (consulta y anulación) sobre PG real (D-11, D-14, D-15).

El servicio solo hace flush. Datos ficticios; `freezegun` donde importa el reloj.
"""
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import crear_turno  # noqa: E402
from c09_helpers import sembrar_c09  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

AHORA = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


async def _escenario(sesion):
    """Mundo C-09; devuelve (ps, cs, repos, m, actores)."""
    from app.servicios import clinica_servicio as clinica
    from app.servicios import cuenta_servicio as cs
    from app.servicios import presupuesto_servicio as ps

    m = await sembrar_c09(sesion)
    repos = ps.PresupuestoRepos.de_sesion(sesion)
    a = {
        "odo": clinica.Actor(usuario_id=m.odo_a.id, rol="odontologo", profesional_id=m.prof_a.id),
        "sec": clinica.Actor(usuario_id=m.secretaria.id, rol="secretaria", profesional_id=None),
        "admin": clinica.Actor(usuario_id=m.admin.id, rol="admin", profesional_id=None),
    }
    return ps, cs, repos, m, a


async def _aceptado(ps, repos, m, a, hallazgo=None, codigo="CON-001", cantidad=1, paciente=None):
    from app.esquemas.presupuesto import ItemIn

    hallazgo = hallazgo or m.h1
    p = await ps.crear(repos, a["odo"], (paciente or m.ana).id, [
        ItemIn(hallazgo_id=hallazgo.id, tratamiento_id=m.trat[codigo].id, cantidad=cantidad)], AHORA)
    await ps.presentar(repos, a["odo"], p.id, AHORA)
    await ps.aceptar(repos, a["odo"], p.id, AHORA)
    return p


async def _cargo_de(repos, m, p=None):
    cuenta = await repos.cuentas.por_paciente(m.ana.id)
    filas = await repos.cuentas.movimientos(cuenta.id)
    return next(f.movimiento for f in filas if f.movimiento.tipo == "cargo")


async def _contar(sesion, tabla):
    return await sesion.scalar(sa.text(f"SELECT count(*) FROM {tabla}"))


# --- 5.1 consulta ---------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cuenta_sin_movimientos_no_crea_filas(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    cuenta = await cs.obtener_cuenta(repos, a["sec"], m.ana.id)
    assert cuenta.paciente_id == m.ana.id and cuenta.saldo == Decimal("0")
    assert cuenta.movimientos == []
    assert cuenta.model_dump(mode="json")["saldo"] == "0.00"
    assert await _contar(sesion_pg, "cuenta_corriente") == 0
    assert await _contar(sesion_pg, "movimiento") == 0


@pytest.mark.asyncio
async def test_cuenta_paciente_inexistente_404(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    with pytest.raises(cs.NoEncontradoError):
        await cs.obtener_cuenta(repos, a["sec"], 987654)


@pytest.mark.asyncio
async def test_cuenta_paciente_baja_sin_cuenta_404(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    m.beto.deleted_at = AHORA
    await sesion_pg.flush()
    with pytest.raises(cs.NoEncontradoError):
        await cs.obtener_cuenta(repos, a["admin"], m.beto.id)


@pytest.mark.asyncio
async def test_cuenta_paciente_baja_con_movimientos_ok(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    await _aceptado(ps, repos, m, a, cantidad=2)
    m.ana.deleted_at = AHORA  # la deuda sobrevive a la baja (RN-GL-01)
    await sesion_pg.flush()
    cuenta = await cs.obtener_cuenta(repos, a["sec"], m.ana.id)
    assert cuenta.saldo == Decimal("2001.00") and len(cuenta.movimientos) == 1


@pytest.mark.asyncio
async def test_cuenta_con_pago_directo_refleja_saldo(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    await _aceptado(ps, repos, m, a, codigo="OBT-001")  # 15000.00
    cuenta_db = await repos.cuentas.por_paciente(m.ana.id)
    await repos.cuentas.crear_movimiento(
        cuenta_db.id, tipo="pago", monto=Decimal("-4000.00"), concepto="Pago de prueba",
        recibo_id=123, creado_por=m.admin.id)
    await repos.cuentas.crear_movimiento(
        cuenta_db.id, tipo="ajuste", monto=Decimal("-1000.00"), concepto="Bonificación",
        motivo="cortesía", creado_por=m.admin.id)
    cuenta = await cs.obtener_cuenta(repos, a["admin"], m.ana.id)
    assert cuenta.saldo == Decimal("10000.00")
    assert cuenta.model_dump(mode="json")["saldo"] == "10000.00"
    assert [x.tipo for x in cuenta.movimientos] == ["ajuste", "pago", "cargo"]
    assert cuenta.movimientos[1].recibo_id == 123


@pytest.mark.asyncio
async def test_cuenta_saldo_a_favor_es_negativo(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    await _aceptado(ps, repos, m, a, codigo="PRO-001")  # 500.00
    cuenta_db = await repos.cuentas.por_paciente(m.ana.id)
    await repos.cuentas.crear_movimiento(
        cuenta_db.id, tipo="pago", monto=Decimal("-700.00"), concepto="Pago", creado_por=m.admin.id)
    assert (await cs.obtener_cuenta(repos, a["sec"], m.ana.id)).saldo == Decimal("-200.00")


@pytest.mark.asyncio
async def test_cuenta_no_mezcla_pacientes(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    await _aceptado(ps, repos, m, a)
    beto = await cs.obtener_cuenta(repos, a["sec"], m.beto.id)
    assert beto.saldo == Decimal("0") and beto.movimientos == []


@pytest.mark.asyncio
async def test_cuenta_odontologo_403(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    with pytest.raises(cs.AccesoDenegadoError):
        await cs.obtener_cuenta(repos, a["odo"], m.ana.id)


# --- 5.2 anulación ---------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anular_crea_ajuste_opuesto(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    p = await _aceptado(ps, repos, m, a, cantidad=2)  # 2001.00
    cargo = await _cargo_de(repos, m)
    anul = await cs.anular_cargo(repos, a["admin"], m.ana.id, cargo.id, "Cargado por error")
    assert (anul.tipo, anul.monto, anul.anula_a_id) == ("ajuste", Decimal("-2001.00"), cargo.id)
    assert anul.presupuesto_id == p.id and anul.anulado is False
    cuenta = await cs.obtener_cuenta(repos, a["admin"], m.ana.id)
    assert cuenta.saldo == Decimal("0.00")


@pytest.mark.asyncio
async def test_anular_no_toca_original(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    await _aceptado(ps, repos, m, a)
    cargo = await _cargo_de(repos, m)
    antes = (cargo.tipo, cargo.monto, cargo.concepto, cargo.motivo, cargo.created_at)
    await cs.anular_cargo(repos, a["admin"], m.ana.id, cargo.id, "Error")
    await sesion_pg.refresh(cargo)
    assert (cargo.tipo, cargo.monto, cargo.concepto, cargo.motivo, cargo.created_at) == antes
    assert await _contar(sesion_pg, "movimiento") == 2


@pytest.mark.asyncio
async def test_anular_guarda_creado_por_y_motivo(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    await _aceptado(ps, repos, m, a)
    cargo = await _cargo_de(repos, m)
    await cs.anular_cargo(repos, a["admin"], m.ana.id, cargo.id, "Paciente desistió")
    fila = (await sesion_pg.execute(sa.text(
        "SELECT creado_por, motivo, concepto FROM movimiento WHERE anula_a_id = :i"), {"i": cargo.id})).one()
    assert (fila.creado_por, fila.motivo) == (m.admin.id, "Paciente desistió")
    assert "desist" not in fila.concepto  # el motivo no se copia al concepto


@pytest.mark.asyncio
async def test_anular_dos_veces_409(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    await _aceptado(ps, repos, m, a)
    cargo = await _cargo_de(repos, m)
    await cs.anular_cargo(repos, a["admin"], m.ana.id, cargo.id, "Error")
    with pytest.raises(cs.ConflictoError):
        await cs.anular_cargo(repos, a["admin"], m.ana.id, cargo.id, "Otra vez")
    assert await _contar(sesion_pg, "movimiento") == 2


@pytest.mark.asyncio
async def test_anular_ajuste_409(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    await _aceptado(ps, repos, m, a)
    cargo = await _cargo_de(repos, m)
    anul = await cs.anular_cargo(repos, a["admin"], m.ana.id, cargo.id, "Error")
    with pytest.raises(cs.ConflictoError):
        await cs.anular_cargo(repos, a["admin"], m.ana.id, anul.id, "Anular la anulación")
    assert await _contar(sesion_pg, "movimiento") == 2


@pytest.mark.asyncio
async def test_anular_pago_409(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    await _aceptado(ps, repos, m, a)
    cuenta_db = await repos.cuentas.por_paciente(m.ana.id)
    pago = await repos.cuentas.crear_movimiento(
        cuenta_db.id, tipo="pago", monto=Decimal("-10.00"), concepto="Pago", creado_por=m.admin.id)
    with pytest.raises(cs.ConflictoError):
        await cs.anular_cargo(repos, a["admin"], m.ana.id, pago.id, "x")
    assert await _contar(sesion_pg, "movimiento") == 2


@pytest.mark.asyncio
async def test_anular_de_otra_cuenta_404(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    await _aceptado(ps, repos, m, a)
    cargo = await _cargo_de(repos, m)
    await repos.cuentas.asegurar(m.beto.id)
    with pytest.raises(cs.NoEncontradoError):
        await cs.anular_cargo(repos, a["admin"], m.beto.id, cargo.id, "x")  # cuenta de Beto
    with pytest.raises(cs.NoEncontradoError):
        await cs.anular_cargo(repos, a["admin"], m.ana.id, 987654, "x")  # movimiento inexistente
    sin_cuenta = type("P", (), {"id": 987654})()
    with pytest.raises(cs.NoEncontradoError):
        await cs.anular_cargo(repos, a["admin"], sin_cuenta.id, cargo.id, "x")  # paciente inexistente
    assert await _contar(sesion_pg, "movimiento") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("quien", ["sec", "odo"])
async def test_anular_solo_admin_403(sesion_pg, quien):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    await _aceptado(ps, repos, m, a)
    cargo = await _cargo_de(repos, m)
    with pytest.raises(cs.AccesoDenegadoError):
        await cs.anular_cargo(repos, a[quien], m.ana.id, cargo.id, "x")
    assert await _contar(sesion_pg, "movimiento") == 1


@pytest.mark.asyncio
async def test_anular_con_reloj_congelado(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    await _aceptado(ps, repos, m, a)
    cargo = await _cargo_de(repos, m)
    anul = await cs.anular_cargo(repos, a["admin"], m.ana.id, cargo.id, "Error")
    cuenta = await cs.obtener_cuenta(repos, a["admin"], m.ana.id)
    assert cuenta.movimientos[0].id == anul.id  # el más reciente primero


@pytest.mark.asyncio
async def test_cargo_anulado_presupuesto_sigue_aceptado(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    p = await _aceptado(ps, repos, m, a)
    cargo = await _cargo_de(repos, m)
    await cs.anular_cargo(repos, a["admin"], m.ana.id, cargo.id, "Error")
    salida = await ps.a_salida(repos, a["admin"], await ps.obtener(repos, a["admin"], p.id))
    assert salida.estado == "aceptado" and salida.cargo_anulado is True


@pytest.mark.asyncio
async def test_cargo_sin_anular_no_expone_la_marca(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    p = await _aceptado(ps, repos, m, a)
    salida = await ps.a_salida(repos, a["admin"], await ps.obtener(repos, a["admin"], p.id))
    assert salida.cargo_anulado is False


@pytest.mark.asyncio
async def test_cargo_anulado_expone_flag(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    await _aceptado(ps, repos, m, a)
    cargo = await _cargo_de(repos, m)
    anul = await cs.anular_cargo(repos, a["admin"], m.ana.id, cargo.id, "Error")
    cuenta = await cs.obtener_cuenta(repos, a["sec"], m.ana.id)
    por_id = {x.id: x for x in cuenta.movimientos}
    assert por_id[cargo.id].anulado is True and por_id[anul.id].anulado is False
    assert por_id[anul.id].anula_a_id == cargo.id


@pytest.mark.asyncio
async def test_hallazgos_con_cargo_anulado_se_presupuestan_de_nuevo(sesion_pg):
    ps, cs, repos, m, a = await _escenario(sesion_pg)
    await _aceptado(ps, repos, m, a)
    cargo = await _cargo_de(repos, m)
    await cs.anular_cargo(repos, a["admin"], m.ana.id, cargo.id, "Error")
    nuevo = await _aceptado(ps, repos, m, a, codigo="PRO-001")  # mismo h1
    cuenta = await cs.obtener_cuenta(repos, a["admin"], m.ana.id)
    assert cuenta.saldo == Decimal("500.00")
    assert await _contar(sesion_pg, "movimiento") == 3
    assert nuevo.estado == "aceptado"
