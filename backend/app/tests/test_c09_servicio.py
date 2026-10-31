"""C-09 grupo 4: servicio de presupuestos (alta, edición, estados, aceptación, lectura) sobre PG real.

El servicio solo hace flush; los tests verifican reglas y errores de dominio.
`freezegun` fija el reloj de `presentado_at`, `decidido_at` y `created_at`. Datos ficticios.
"""
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from freezegun import freeze_time

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import crear_turno  # noqa: E402
from c09_helpers import sembrar_c09  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

AHORA = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


def _it(hallazgo, tratamiento, cantidad=1):
    from app.esquemas.presupuesto import ItemIn

    return ItemIn(hallazgo_id=hallazgo.id, tratamiento_id=tratamiento.id, cantidad=cantidad)


async def _escenario(sesion, vincular_a=True):
    """Mundo C-09; devuelve (ps, repos, m, actores)."""
    from app.servicios import clinica_servicio as cs
    from app.servicios import presupuesto_servicio as ps

    m = await sembrar_c09(sesion, vincular_a=vincular_a)
    repos = ps.PresupuestoRepos.de_sesion(sesion)
    actores = {
        "a": cs.Actor(usuario_id=m.odo_a.id, rol="odontologo", profesional_id=m.prof_a.id),
        "b": cs.Actor(usuario_id=m.odo_b.id, rol="odontologo", profesional_id=m.prof_b.id),
        "sec": cs.Actor(usuario_id=m.secretaria.id, rol="secretaria", profesional_id=None),
        "admin": cs.Actor(usuario_id=m.admin.id, rol="admin", profesional_id=None),
        "sin_prof": cs.Actor(usuario_id=m.odo_sin_prof.id, rol="odontologo", profesional_id=None),
    }
    return ps, repos, m, actores


async def _crear(ps, repos, m, a, items=None, paciente=None):
    items = items or [_it(m.h1, m.trat["CON-001"])]
    return await ps.crear(repos, a["a"], (paciente or m.ana).id, items, AHORA)


async def _cantidad(sesion, tabla):
    return await sesion.scalar(sa.text(f"SELECT count(*) FROM {tabla}"))


# --- 4.1 alta -------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_crear_copia_precio_base(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a, [_it(m.h1, m.trat["CON-001"]), _it(m.h2, m.trat["OBT-001"])])
    detalle = await repos.presupuestos.items_detalle(p.id)
    assert [d.item.precio for d in detalle] == [Decimal("1000.50"), Decimal("15000.00")]
    assert p.estado == "borrador" and p.profesional_id == m.prof_a.id


@pytest.mark.asyncio
async def test_crear_calcula_total(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a, [_it(m.h1, m.trat["CON-001"], 2), _it(m.h2, m.trat["PRO-001"], 1)])
    assert p.total == Decimal("2501.00")
    otro = await _crear(ps, repos, m, a, [_it(m.h3, m.trat["OBT-001"], 3)])
    assert otro.total == Decimal("45000.00")


@pytest.mark.asyncio
async def test_crear_fija_fechas_del_reloj(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a)
    assert p.created_at == AHORA and p.updated_at == AHORA
    assert p.presentado_at is None and p.decidido_at is None


@pytest.mark.asyncio
async def test_crear_hallazgo_dado_de_baja_422(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    m.h1.deleted_at, m.h1.motivo_baja = AHORA, "error"
    await sesion_pg.flush()
    with pytest.raises(ps.ValidacionClinicaError):
        await _crear(ps, repos, m, a)
    assert await _cantidad(sesion_pg, "presupuesto") == 0


@pytest.mark.asyncio
async def test_crear_hallazgo_de_otro_paciente_422(sesion_pg):
    from app.modelos import HallazgoOdontograma, HistoriaClinica

    ps, repos, m, a = await _escenario(sesion_pg)
    hc_beto = HistoriaClinica(paciente_id=m.beto.id)
    sesion_pg.add(hc_beto)
    await sesion_pg.flush()
    de_beto = HallazgoOdontograma(
        hc_id=hc_beto.id, pieza_fdi=11, cara="oclusal", estado="caries",
        catalogo_version=1, fecha=AHORA, profesional_id=m.prof_a.id)
    sesion_pg.add(de_beto)
    await sesion_pg.flush()
    with pytest.raises(ps.ValidacionClinicaError) as exc:
        await _crear(ps, repos, m, a, [_it(de_beto, m.trat["CON-001"])])
    assert "Beto" not in str(exc.value) and "11" not in str(exc.value)
    # un hallazgo que no existe da el mismo mensaje: no revela si existe en otro paciente
    inexistente = type("H", (), {"id": 987654})()
    with pytest.raises(ps.ValidacionClinicaError) as exc2:
        await _crear(ps, repos, m, a, [_it(inexistente, m.trat["CON-001"])])
    assert str(exc.value) == str(exc2.value)


@pytest.mark.asyncio
async def test_crear_historia_dada_de_baja_422(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    m.hc.deleted_at, m.hc.motivo_baja = AHORA, "error"
    await sesion_pg.flush()
    with pytest.raises(ps.ValidacionClinicaError):
        await _crear(ps, repos, m, a)


@pytest.mark.asyncio
async def test_crear_paciente_sin_historia_422(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    await crear_turno(sesion_pg, m.beto, m.prof_a, m.sillon)
    with pytest.raises(ps.ValidacionClinicaError):
        await _crear(ps, repos, m, a, paciente=m.beto)


@pytest.mark.asyncio
async def test_crear_tratamiento_inexistente_422(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    from app.esquemas.presupuesto import ItemIn

    with pytest.raises(ps.ValidacionClinicaError):
        await _crear(ps, repos, m, a, [ItemIn(hallazgo_id=m.h1.id, tratamiento_id=987654)])
    assert await _cantidad(sesion_pg, "presupuesto") == 0


@pytest.mark.asyncio
async def test_crear_paciente_eliminado_404(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    m.ana.deleted_at = AHORA
    await sesion_pg.flush()
    with pytest.raises(ps.NoEncontradoError):
        await _crear(ps, repos, m, a)


@pytest.mark.asyncio
async def test_crear_paciente_inexistente_404(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    with pytest.raises(ps.NoEncontradoError):
        await ps.crear(repos, a["a"], 987654, [_it(m.h1, m.trat["CON-001"])], AHORA)


@pytest.mark.asyncio
async def test_crear_sin_vinculo_403(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    with pytest.raises(ps.AccesoDenegadoError):
        await ps.crear(repos, a["b"], m.ana.id, [_it(m.h1, m.trat["CON-001"])], AHORA)


@pytest.mark.asyncio
@pytest.mark.parametrize("quien", ["sin_prof", "sec", "admin"])
async def test_crear_sin_profesional_o_sin_rol_403(sesion_pg, quien):
    ps, repos, m, a = await _escenario(sesion_pg)
    with pytest.raises(ps.AccesoDenegadoError):
        await ps.crear(repos, a[quien], m.ana.id, [_it(m.h1, m.trat["CON-001"])], AHORA)
    assert await _cantidad(sesion_pg, "presupuesto") == 0


@pytest.mark.asyncio
async def test_crear_autor_del_token(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_b, m.sillon)
    p_a = await _crear(ps, repos, m, a)
    p_b = await ps.crear(repos, a["b"], m.ana.id, [_it(m.h1, m.trat["CON-001"])], AHORA)
    assert (p_a.profesional_id, p_b.profesional_id) == (m.prof_a.id, m.prof_b.id)


@pytest.mark.asyncio
async def test_crear_hallazgo_de_otro_profesional_ok(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_b, m.sillon)
    # los hallazgos los cargó A; B igual puede presupuestarlos (HC compartida, D-04)
    p = await ps.crear(repos, a["b"], m.ana.id, [_it(m.h1, m.trat["CON-001"])], AHORA)
    assert p.profesional_id == m.prof_b.id


@pytest.mark.asyncio
async def test_mismo_hallazgo_en_dos_presupuestos_ok(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p1 = await _crear(ps, repos, m, a)
    p2 = await _crear(ps, repos, m, a, [_it(m.h1, m.trat["OBT-001"])])
    assert p1.id != p2.id and p2.total == Decimal("15000.00")


@pytest.mark.asyncio
async def test_crear_acepta_hallazgo_de_cualquier_estado(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    # h3 es `ausente` (implante) y un `sano` también se presupuesta (limpieza, D-04)
    p = await _crear(ps, repos, m, a, [_it(m.h3, m.trat["OBT-001"])])
    assert p.total == Decimal("15000.00")


# --- 4.2 reemplazo de ítems y baja ---------------------------------------------------------

@pytest.mark.asyncio
async def test_reemplazar_recalcula_total(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a, [_it(m.h1, m.trat["CON-001"], 2)])
    assert p.total == Decimal("2001.00")
    p = await ps.reemplazar_items(
        repos, a["a"], p.id, [_it(m.h2, m.trat["PRO-001"], 1), _it(m.h3, m.trat["OBT-001"], 1)],
        AHORA + timedelta(minutes=5))
    assert p.total == Decimal("15500.00")
    assert p.updated_at == AHORA + timedelta(minutes=5)
    detalle = await repos.presupuestos.items_detalle(p.id)
    assert sorted(d.item.hallazgo_id for d in detalle) == sorted([m.h2.id, m.h3.id])


@pytest.mark.asyncio
async def test_reemplazar_toma_precio_vigente(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a, [_it(m.h1, m.trat["CON-001"])])
    m.trat["CON-001"].precio_base = Decimal("2000.00")
    await sesion_pg.flush()
    p = await ps.reemplazar_items(repos, a["a"], p.id, [_it(m.h1, m.trat["CON-001"])], AHORA)
    assert p.total == Decimal("2000.00")
    assert (await repos.presupuestos.items_detalle(p.id))[0].item.precio == Decimal("2000.00")


@pytest.mark.asyncio
async def test_reemplazar_presentado_409(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a)
    p.estado = "presentado"
    await sesion_pg.flush()
    with pytest.raises(ps.ConflictoError):
        await ps.reemplazar_items(repos, a["a"], p.id, [_it(m.h2, m.trat["PRO-001"])], AHORA)
    detalle = await repos.presupuestos.items_detalle(p.id)
    assert [d.item.hallazgo_id for d in detalle] == [m.h1.id]


@pytest.mark.asyncio
async def test_reemplazar_ajeno_403(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_b, m.sillon)
    p = await _crear(ps, repos, m, a)
    with pytest.raises(ps.AccesoDenegadoError):
        await ps.reemplazar_items(repos, a["b"], p.id, [_it(m.h2, m.trat["PRO-001"])], AHORA)
    assert p.total == Decimal("1000.50")


@pytest.mark.asyncio
@pytest.mark.parametrize("quien", ["sec", "admin"])
async def test_reemplazar_sin_rol_de_escritura_403(sesion_pg, quien):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a)
    with pytest.raises(ps.AccesoDenegadoError):
        await ps.reemplazar_items(repos, a[quien], p.id, [_it(m.h2, m.trat["PRO-001"])], AHORA)


@pytest.mark.asyncio
async def test_reemplazar_inexistente_404_y_item_invalido_422_sin_cambios(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    with pytest.raises(ps.NoEncontradoError):
        await ps.reemplazar_items(repos, a["a"], 987654, [_it(m.h1, m.trat["CON-001"])], AHORA)
    p = await _crear(ps, repos, m, a)
    m.h2.deleted_at, m.h2.motivo_baja = AHORA, "error"
    await sesion_pg.flush()
    with pytest.raises(ps.ValidacionClinicaError):
        await ps.reemplazar_items(repos, a["a"], p.id, [_it(m.h2, m.trat["CON-001"])], AHORA)


@pytest.mark.asyncio
async def test_baja_borrador_conserva_fila(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a)
    baja = await ps.dar_de_baja(repos, a["a"], p.id, "duplicado", AHORA + timedelta(hours=1))
    assert baja.deleted_at == AHORA + timedelta(hours=1) and baja.motivo_baja == "duplicado"
    assert await _cantidad(sesion_pg, "presupuesto") == 1
    assert await _cantidad(sesion_pg, "item_presupuesto") == 1


@pytest.mark.asyncio
async def test_baja_presentado_409(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a)
    p.estado = "presentado"
    await sesion_pg.flush()
    with pytest.raises(ps.ConflictoError):
        await ps.dar_de_baja(repos, a["a"], p.id, "x", AHORA)
    assert p.deleted_at is None


@pytest.mark.asyncio
async def test_baja_ajena_403_y_baja_repetida_404(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_b, m.sillon)
    p = await _crear(ps, repos, m, a)
    with pytest.raises(ps.AccesoDenegadoError):
        await ps.dar_de_baja(repos, a["b"], p.id, "x", AHORA)
    await ps.dar_de_baja(repos, a["a"], p.id, "x", AHORA)
    with pytest.raises(ps.NoEncontradoError):
        await ps.dar_de_baja(repos, a["a"], p.id, "x", AHORA)


@pytest.mark.asyncio
async def test_baja_oculta_presupuesto_404(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a)
    await ps.dar_de_baja(repos, a["a"], p.id, "duplicado", AHORA)
    with pytest.raises(ps.NoEncontradoError):
        await ps.obtener(repos, a["a"], p.id)
    assert await ps.listar(repos, a["a"], m.ana.id) == []


# --- 4.3 presentar y rechazar ------------------------------------------------------------------

async def _presentado(ps, repos, m, a, items=None):
    p = await _crear(ps, repos, m, a, items)
    return await ps.presentar(repos, a["a"], p.id, AHORA)


async def _corregir_h1(sesion, m, a):
    """Corrige el hallazgo h1 (C-08): el original queda dado de baja."""
    from app.servicios import clinica_servicio as cs

    repos = cs.ClinicaRepos.de_sesion(sesion)
    return await cs.corregir_hallazgo(
        repos, a["a"], m.hc.id, m.h1.id, 16, "mesial", "caries", "cara equivocada", AHORA)


@pytest.mark.asyncio
async def test_presentar_fija_fecha(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a)
    with freeze_time("2026-11-02 15:30:00"):
        p = await ps.presentar(repos, a["a"], p.id)
    assert p.estado == "presentado"
    assert p.presentado_at == datetime(2026, 11, 2, 15, 30, tzinfo=timezone.utc)
    assert p.updated_at == p.presentado_at and p.decidido_at is None


@pytest.mark.asyncio
async def test_presentar_con_fecha_explicita_usa_esa_fecha(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a)
    p = await ps.presentar(repos, a["a"], p.id, AHORA + timedelta(days=1))
    assert p.presentado_at == AHORA + timedelta(days=1)


@pytest.mark.asyncio
async def test_presentar_total_cero_422(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a, [_it(m.h1, m.trat["GRATIS"])])
    assert p.total == Decimal("0.00")
    with pytest.raises(ps.ValidacionClinicaError):
        await ps.presentar(repos, a["a"], p.id, AHORA)
    assert p.estado == "borrador" and p.presentado_at is None


@pytest.mark.asyncio
async def test_presentar_con_total_positivo_aunque_un_item_sea_gratis(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a, [_it(m.h1, m.trat["GRATIS"]), _it(m.h2, m.trat["PRO-001"])])
    assert (await ps.presentar(repos, a["a"], p.id, AHORA)).estado == "presentado"


@pytest.mark.asyncio
async def test_presentar_hallazgo_corregido_409(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a)
    nuevo = await _corregir_h1(sesion_pg, m, a)
    with pytest.raises(ps.ConflictoError):
        await ps.presentar(repos, a["a"], p.id, AHORA)
    assert p.estado == "borrador"
    # sigue editable con el hallazgo nuevo
    p = await ps.reemplazar_items(repos, a["a"], p.id, [_it(nuevo, m.trat["CON-001"])], AHORA)
    assert (await ps.presentar(repos, a["a"], p.id, AHORA)).estado == "presentado"


@pytest.mark.asyncio
async def test_presentar_hallazgo_dado_de_baja_409(sesion_pg):
    from app.servicios import clinica_servicio as cs

    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a, [_it(m.h1, m.trat["CON-001"]), _it(m.h2, m.trat["PRO-001"])])
    await cs.dar_de_baja_hallazgo(
        cs.ClinicaRepos.de_sesion(sesion_pg), a["a"], m.hc.id, m.h2.id, "error", AHORA)
    with pytest.raises(ps.ConflictoError):
        await ps.presentar(repos, a["a"], p.id, AHORA)


@pytest.mark.asyncio
async def test_presentar_dos_veces_409(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _presentado(ps, repos, m, a)
    with pytest.raises(ps.ConflictoError):
        await ps.presentar(repos, a["a"], p.id, AHORA + timedelta(hours=1))
    assert p.presentado_at == AHORA


@pytest.mark.asyncio
async def test_presentar_ajeno_o_sin_rol_403(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_b, m.sillon)
    p = await _crear(ps, repos, m, a)
    for quien in ("b", "sec", "admin"):
        with pytest.raises(ps.AccesoDenegadoError):
            await ps.presentar(repos, a[quien], p.id, AHORA)
    assert p.estado == "borrador"
    with pytest.raises(ps.NoEncontradoError):
        await ps.presentar(repos, a["a"], 987654, AHORA)


@pytest.mark.asyncio
async def test_rechazar_guarda_motivo_sin_movimientos(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _presentado(ps, repos, m, a)
    p = await ps.rechazar(repos, a["a"], p.id, "Prefiere esperar", AHORA + timedelta(days=2))
    assert p.estado == "rechazado" and p.motivo_rechazo == "Prefiere esperar"
    assert p.decidido_at == AHORA + timedelta(days=2)
    assert await _cantidad(sesion_pg, "movimiento") == 0
    assert await _cantidad(sesion_pg, "cuenta_corriente") == 0


@pytest.mark.asyncio
async def test_rechazar_borrador_409(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a)
    with pytest.raises(ps.ConflictoError):
        await ps.rechazar(repos, a["a"], p.id, "x", AHORA)
    assert p.estado == "borrador" and p.motivo_rechazo is None


@pytest.mark.asyncio
async def test_rechazado_es_final_409(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _presentado(ps, repos, m, a)
    await ps.rechazar(repos, a["a"], p.id, "caro", AHORA)
    with pytest.raises(ps.ConflictoError):
        await ps.presentar(repos, a["a"], p.id, AHORA)
    with pytest.raises(ps.ConflictoError):
        await ps.rechazar(repos, a["a"], p.id, "otra vez", AHORA)
    with pytest.raises(ps.ConflictoError):
        await ps.reemplazar_items(repos, a["a"], p.id, [_it(m.h2, m.trat["PRO-001"])], AHORA)
    assert p.motivo_rechazo == "caro"


@pytest.mark.asyncio
async def test_rechazar_presentado_con_hallazgo_corregido_igual_se_puede(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _presentado(ps, repos, m, a)
    await _corregir_h1(sesion_pg, m, a)  # D-05: queda sin salida más que rechazar
    p = await ps.rechazar(repos, a["a"], p.id, "desactualizado", AHORA)
    assert p.estado == "rechazado"


@pytest.mark.asyncio
async def test_rechazar_ajeno_403(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_b, m.sillon)
    p = await _presentado(ps, repos, m, a)
    with pytest.raises(ps.AccesoDenegadoError):
        await ps.rechazar(repos, a["b"], p.id, "x", AHORA)
    assert p.estado == "presentado"


# --- 4.4 aceptar ----------------------------------------------------------------------------------

async def _movimientos(sesion):
    filas = await sesion.execute(sa.text(
        "SELECT tipo, monto, concepto, presupuesto_id, creado_por, motivo FROM movimiento ORDER BY id"))
    return filas.all()


@pytest.mark.asyncio
async def test_aceptar_genera_cargo_por_total(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _presentado(ps, repos, m, a, [_it(m.h1, m.trat["CON-001"], 2), _it(m.h2, m.trat["PRO-001"])])
    p = await ps.aceptar(repos, a["a"], p.id, AHORA + timedelta(days=1))
    assert p.estado == "aceptado" and p.decidido_at == AHORA + timedelta(days=1)
    (mov,) = await _movimientos(sesion_pg)
    assert (mov.tipo, mov.monto, mov.presupuesto_id) == ("cargo", Decimal("2501.00"), p.id)
    cuenta = await repos.cuentas.por_paciente(m.ana.id)
    assert await repos.cuentas.saldo(cuenta.id) == Decimal("2501.00")


@pytest.mark.asyncio
async def test_aceptar_segundo_presupuesto_reutiliza_la_cuenta(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p1 = await _presentado(ps, repos, m, a)
    p2 = await _presentado(ps, repos, m, a, [_it(m.h2, m.trat["OBT-001"])])
    await ps.aceptar(repos, a["a"], p1.id, AHORA)
    await ps.aceptar(repos, a["a"], p2.id, AHORA)
    assert await _cantidad(sesion_pg, "cuenta_corriente") == 1
    assert await _cantidad(sesion_pg, "movimiento") == 2
    cuenta = await repos.cuentas.por_paciente(m.ana.id)
    assert await repos.cuentas.saldo(cuenta.id) == Decimal("16000.50")


@pytest.mark.asyncio
async def test_aceptar_concepto_sin_phi(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _presentado(ps, repos, m, a)
    await ps.aceptar(repos, a["a"], p.id, AHORA)
    (mov,) = await _movimientos(sesion_pg)
    assert mov.concepto == f"Presupuesto {p.id}"
    for prohibido in ("caries", "oclusal", "16", "Trat", m.ana.apellido):
        assert prohibido not in mov.concepto.replace(str(p.id), "")


@pytest.mark.asyncio
async def test_aceptar_guarda_creado_por(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _presentado(ps, repos, m, a)
    await ps.aceptar(repos, a["a"], p.id, AHORA)
    (mov,) = await _movimientos(sesion_pg)
    assert mov.creado_por == m.odo_a.id


@pytest.mark.asyncio
async def test_aceptar_hallazgo_dado_de_baja_409_sin_movimiento(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _presentado(ps, repos, m, a)
    await _corregir_h1(sesion_pg, m, a)
    with pytest.raises(ps.ConflictoError):
        await ps.aceptar(repos, a["a"], p.id, AHORA)
    assert p.estado == "presentado" and p.decidido_at is None
    assert await _cantidad(sesion_pg, "movimiento") == 0
    assert await _cantidad(sesion_pg, "cuenta_corriente") == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("estado_previo", ["borrador", "rechazado", "aceptado"])
async def test_aceptar_fuera_de_presentado_409(sesion_pg, estado_previo):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a)
    if estado_previo != "borrador":
        await ps.presentar(repos, a["a"], p.id, AHORA)
    if estado_previo == "rechazado":
        await ps.rechazar(repos, a["a"], p.id, "x", AHORA)
    if estado_previo == "aceptado":
        await ps.aceptar(repos, a["a"], p.id, AHORA)
    cargos = 1 if estado_previo == "aceptado" else 0
    with pytest.raises(ps.ConflictoError):
        await ps.aceptar(repos, a["a"], p.id, AHORA)
    assert await _cantidad(sesion_pg, "movimiento") == cargos


@pytest.mark.asyncio
async def test_aceptar_borrador_409(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a)
    with pytest.raises(ps.ConflictoError):
        await ps.aceptar(repos, a["a"], p.id, AHORA)
    assert p.estado == "borrador" and await _cantidad(sesion_pg, "movimiento") == 0


@pytest.mark.asyncio
async def test_aceptar_repetido_409_un_cargo(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _presentado(ps, repos, m, a)
    await ps.aceptar(repos, a["a"], p.id, AHORA)
    with pytest.raises(ps.ConflictoError):
        await ps.aceptar(repos, a["a"], p.id, AHORA + timedelta(hours=1))
    assert await _cantidad(sesion_pg, "movimiento") == 1
    assert p.decidido_at == AHORA


@pytest.mark.asyncio
async def test_aceptar_ajeno_403_sin_cargo(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_b, m.sillon)
    p = await _presentado(ps, repos, m, a)
    for quien in ("b", "sec", "admin"):
        with pytest.raises(ps.AccesoDenegadoError):
            await ps.aceptar(repos, a[quien], p.id, AHORA)
    assert p.estado == "presentado" and await _cantidad(sesion_pg, "movimiento") == 0


@pytest.mark.asyncio
async def test_aceptar_inexistente_404(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    with pytest.raises(ps.NoEncontradoError):
        await ps.aceptar(repos, a["a"], 987654, AHORA)


@pytest.mark.asyncio
async def test_catalogo_cambia_tras_presentar_conserva_total(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _presentado(ps, repos, m, a, [_it(m.h1, m.trat["CON-001"], 2)])
    m.trat["CON-001"].precio_base = Decimal("9999.00")
    await sesion_pg.flush()
    p = await ps.aceptar(repos, a["a"], p.id, AHORA)
    assert p.total == Decimal("2001.00")
    assert (await repos.presupuestos.items_detalle(p.id))[0].item.precio == Decimal("1000.50")
    (mov,) = await _movimientos(sesion_pg)
    assert mov.monto == Decimal("2001.00")


@pytest.mark.asyncio
async def test_aceptar_con_cargo_preexistente_traduce_integridad_a_409(sesion_pg):
    """Red de seguridad (D-13): si ya hay un cargo del presupuesto, el índice único da 409."""
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _presentado(ps, repos, m, a)
    cuenta = await repos.cuentas.asegurar(m.ana.id)
    await repos.cuentas.crear_movimiento(
        cuenta.id, tipo="cargo", monto=Decimal("1.00"), concepto="previo",
        presupuesto_id=p.id, creado_por=m.admin.id)
    with pytest.raises(ps.ConflictoError):
        await ps.aceptar(repos, a["a"], p.id, AHORA)
    assert p.estado == "presentado"
    assert await _cantidad(sesion_pg, "movimiento") == 1


# --- 4.6 lectura y vista financiera --------------------------------------------------------------

async def _rechazado(ps, repos, m, a):
    p = await _presentado(ps, repos, m, a)
    return await ps.rechazar(repos, a["a"], p.id, "Motivo clínico reservado", AHORA)


@pytest.mark.asyncio
async def test_listar_secretaria_ok(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p1 = await _crear(ps, repos, m, a)
    p2 = await _crear(ps, repos, m, a, [_it(m.h2, m.trat["PRO-001"])])
    lista = await ps.listar(repos, a["sec"], m.ana.id)
    assert [p.id for p in lista] == [p2.id, p1.id]
    assert [p.id for p in await ps.listar(repos, a["sec"], m.ana.id, "borrador")] == [p2.id, p1.id]
    assert await ps.listar(repos, a["sec"], m.ana.id, "aceptado") == []
    assert await ps.listar(repos, a["sec"], m.beto.id) == []


@pytest.mark.asyncio
async def test_listar_odontologo_sin_vinculo_403(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    await _crear(ps, repos, m, a)
    with pytest.raises(ps.AccesoDenegadoError):
        await ps.listar(repos, a["b"], m.ana.id)
    with pytest.raises(ps.AccesoDenegadoError):
        await ps.listar(repos, a["sin_prof"], m.ana.id)


@pytest.mark.asyncio
async def test_listar_admin_ok(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a)
    assert [x.id for x in await ps.listar(repos, a["admin"], m.ana.id)] == [p.id]


@pytest.mark.asyncio
async def test_detalle_otro_odontologo_vinculado_ok(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_b, m.sillon)
    p = await _crear(ps, repos, m, a)
    visto = await ps.obtener(repos, a["b"], p.id)
    salida = await ps.a_salida(repos, a["b"], visto)
    assert salida.id == p.id and salida.es_propio is False
    assert (await ps.a_salida(repos, a["a"], p)).es_propio is True


@pytest.mark.asyncio
async def test_detalle_odontologo_sin_vinculo_403_e_inexistente_404(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a)
    with pytest.raises(ps.AccesoDenegadoError):
        await ps.obtener(repos, a["b"], p.id)
    with pytest.raises(ps.NoEncontradoError):
        await ps.obtener(repos, a["sec"], 987654)


@pytest.mark.asyncio
async def test_detalle_secretaria_ve_pieza_cara_y_subtotales(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _crear(ps, repos, m, a, [_it(m.h1, m.trat["CON-001"], 2), _it(m.h3, m.trat["PRO-001"])])
    salida = await ps.a_salida(repos, a["sec"], await ps.obtener(repos, a["sec"], p.id))
    assert salida.total == Decimal("2501.00") and salida.es_propio is False
    primero, segundo = salida.items
    assert (primero.pieza_fdi, primero.cara) == (16, "oclusal")
    assert (primero.tratamiento_nombre, primero.cantidad) == ("Trat CON-001", 2)
    assert (primero.precio, primero.subtotal) == (Decimal("1000.50"), Decimal("2001.00"))
    assert (segundo.pieza_fdi, segundo.cara, segundo.subtotal) == (36, "pieza_completa", Decimal("500.00"))
    assert salida.cargo_anulado is False and primero.hallazgo_vigente is True


@pytest.mark.asyncio
@pytest.mark.parametrize("campo", ["pieza_fdi", "cara", "motivo_rechazo"])
async def test_detalle_admin_oculta_campo(sesion_pg, campo):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _rechazado(ps, repos, m, a)
    asum = await ps.a_salida(repos, a["admin"], await ps.obtener(repos, a["admin"], p.id))
    valor = asum.items[0] if campo != "motivo_rechazo" else asum
    assert getattr(valor, campo) is None
    # control: la secretaria sí ve ese mismo campo (el ocultamiento depende del rol)
    sec = await ps.a_salida(repos, a["sec"], await ps.obtener(repos, a["sec"], p.id))
    visto = sec.items[0] if campo != "motivo_rechazo" else sec
    assert getattr(visto, campo) is not None


@pytest.mark.asyncio
async def test_detalle_admin_oculta_campos_tambien_en_el_json(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _rechazado(ps, repos, m, a)
    asum = await ps.a_salida(repos, a["admin"], p)
    texto = asum.model_dump_json()
    assert "Motivo clínico reservado" not in texto and "oclusal" not in texto


@pytest.mark.asyncio
async def test_detalle_admin_conserva_importes(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _presentado(ps, repos, m, a, [_it(m.h1, m.trat["CON-001"], 2), _it(m.h2, m.trat["PRO-001"])])
    asum = await ps.a_salida(repos, a["admin"], await ps.obtener(repos, a["admin"], p.id))
    assert asum.total == Decimal("2501.00") and asum.estado == "presentado"
    assert [i.subtotal for i in asum.items] == [Decimal("2001.00"), Decimal("500.00")]
    assert [i.tratamiento_nombre for i in asum.items] == ["Trat CON-001", "Trat PRO-001"]
    assert asum.es_propio is False


@pytest.mark.asyncio
async def test_detalle_corregido_tras_aceptar_no_vigente(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p = await _presentado(ps, repos, m, a, [_it(m.h1, m.trat["CON-001"]), _it(m.h2, m.trat["PRO-001"])])
    await ps.aceptar(repos, a["a"], p.id, AHORA)
    await _corregir_h1(sesion_pg, m, a)  # la corrección procede (D-05)
    salida = await ps.a_salida(repos, a["a"], await ps.obtener(repos, a["a"], p.id))
    assert salida.estado == "aceptado" and salida.total == Decimal("1500.50")
    assert [i.hallazgo_vigente for i in salida.items] == [False, True]
    # el ítem conserva la fila original (pieza y cara del hallazgo corregido)
    assert (salida.items[0].pieza_fdi, salida.items[0].cara) == (16, "oclusal")
    assert await _cantidad(sesion_pg, "movimiento") == 1


@pytest.mark.asyncio
async def test_salidas_en_lote_conservan_el_orden(sesion_pg):
    ps, repos, m, a = await _escenario(sesion_pg)
    p1 = await _crear(ps, repos, m, a)
    p2 = await _crear(ps, repos, m, a, [_it(m.h2, m.trat["PRO-001"])])
    salidas = await ps.a_salidas(repos, a["a"], [p2, p1])
    assert [s.id for s in salidas] == [p2.id, p1.id]
    assert [s.total for s in salidas] == [Decimal("500.00"), Decimal("1000.50")]
