"""C-08 grupo 3: repos de historia, tratamientos, hallazgos y vínculo de turno (PG real).

Datos ficticios; `fecha` explícita (el repo no usa reloj, lo fija el servicio).
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import crear_turno, sembrar_mundo  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401


def _dt(dia, hora=10):
    return datetime(2026, 10, dia, hora, 0, tzinfo=timezone.utc)


async def _hc(sesion, paciente):
    from app.repos.historia_repo import HistoriaRepository

    return await HistoriaRepository(sesion).crear(paciente_id=paciente.id)


async def _hallazgo(sesion, hc, prof, fecha, **cambios):
    from app.repos.hallazgo_repo import HallazgoRepository

    datos = {"hc_id": hc.id, "pieza_fdi": 16, "cara": "oclusal", "estado": "caries",
             "catalogo_version": 1, "fecha": fecha, "profesional_id": prof.id}
    datos.update(cambios)
    return await HallazgoRepository(sesion).crear(**datos)


# --- 3.1 historia y tratamientos ---------------------------------------------------

@pytest.mark.asyncio
async def test_historia_con_baja_no_es_activa(sesion_pg):
    from app.repos.historia_repo import HistoriaRepository

    m = await sembrar_mundo(sesion_pg)
    repo = HistoriaRepository(sesion_pg)
    viva = await _hc(sesion_pg, m.ana)
    muerta = await _hc(sesion_pg, m.beto)
    await repo.soft_delete(muerta, "error de carga", _dt(30))
    assert (await repo.activa_por_id(viva.id)).id == viva.id
    assert await repo.activa_por_id(muerta.id) is None
    assert await repo.activa_por_id(99999) is None


@pytest.mark.asyncio
async def test_soft_delete_guarda_fecha_y_motivo_sin_borrar_la_fila(sesion_pg):
    from app.repos.historia_repo import HistoriaRepository

    m = await sembrar_mundo(sesion_pg)
    repo = HistoriaRepository(sesion_pg)
    hc = await _hc(sesion_pg, m.ana)
    await repo.soft_delete(hc, "duplicada por error", _dt(30))
    assert hc.deleted_at == _dt(30) and hc.motivo_baja == "duplicada por error"
    assert (await repo.get(hc.id)) is not None


@pytest.mark.asyncio
async def test_por_paciente_devuelve_baja_para_distinguir_409(sesion_pg):
    from app.repos.historia_repo import HistoriaRepository

    m = await sembrar_mundo(sesion_pg)
    repo = HistoriaRepository(sesion_pg)
    hc = await _hc(sesion_pg, m.ana)
    assert (await repo.por_paciente(m.ana.id)).id == hc.id
    await repo.soft_delete(hc, "x", _dt(30))
    dada_de_baja = await repo.por_paciente(m.ana.id)
    assert dada_de_baja.id == hc.id and dada_de_baja.deleted_at is not None
    assert await repo.por_paciente(m.beto.id) is None


@pytest.mark.asyncio
async def test_tratamientos_ordenados_por_codigo(sesion_pg):
    from app.modelos import Tratamiento
    from app.repos.tratamiento_repo import TratamientoRepository

    sesion_pg.add_all([
        Tratamiento(codigo="ZZ", nombre="Z", precio_base=1),
        Tratamiento(codigo="AA", nombre="A", precio_base=2),
        Tratamiento(codigo="MM", nombre="M", precio_base=3),
    ])
    await sesion_pg.flush()
    assert [t.codigo for t in await TratamientoRepository(sesion_pg).listar()] == ["AA", "MM", "ZZ"]


@pytest.mark.asyncio
async def test_tratamientos_vacio_devuelve_lista_vacia(sesion_pg):
    from app.repos.tratamiento_repo import TratamientoRepository

    assert await TratamientoRepository(sesion_pg).listar() == []


# --- 3.2 hallazgos ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_historial_pieza_mas_reciente_primero(sesion_pg):
    from app.repos.hallazgo_repo import HallazgoRepository

    m = await sembrar_mundo(sesion_pg)
    hc = await _hc(sesion_pg, m.ana)
    caries = await _hallazgo(sesion_pg, hc, m.prof_a, _dt(1))
    obt = await _hallazgo(sesion_pg, hc, m.prof_a, _dt(20), estado="obturacion")
    otra_pieza = await _hallazgo(sesion_pg, hc, m.prof_a, _dt(25), pieza_fdi=26)
    filas = await HallazgoRepository(sesion_pg).listar(hc.id, pieza=16)
    assert [h.id for h in filas] == [obt.id, caries.id]
    assert otra_pieza.id not in [h.id for h in filas]


@pytest.mark.asyncio
async def test_listado_desempata_por_id_descendente(sesion_pg):
    from app.repos.hallazgo_repo import HallazgoRepository

    m = await sembrar_mundo(sesion_pg)
    hc = await _hc(sesion_pg, m.ana)
    primero = await _hallazgo(sesion_pg, hc, m.prof_a, _dt(5))
    segundo = await _hallazgo(sesion_pg, hc, m.prof_a, _dt(5), cara="mesial")
    filas = await HallazgoRepository(sesion_pg).listar(hc.id)
    assert [h.id for h in filas] == [segundo.id, primero.id]


@pytest.mark.asyncio
async def test_listado_excluye_anulados_por_defecto(sesion_pg):
    from app.repos.hallazgo_repo import HallazgoRepository

    m = await sembrar_mundo(sesion_pg)
    hc = await _hc(sesion_pg, m.ana)
    activo = await _hallazgo(sesion_pg, hc, m.prof_a, _dt(5))
    await _hallazgo(sesion_pg, hc, m.prof_a, _dt(6), deleted_at=_dt(7), motivo_baja="error")
    assert [h.id for h in await HallazgoRepository(sesion_pg).listar(hc.id)] == [activo.id]


@pytest.mark.asyncio
async def test_historial_incluye_anulados_si_se_pide(sesion_pg):
    from app.repos.hallazgo_repo import HallazgoRepository

    m = await sembrar_mundo(sesion_pg)
    hc = await _hc(sesion_pg, m.ana)
    activo = await _hallazgo(sesion_pg, hc, m.prof_a, _dt(5))
    anulado = await _hallazgo(sesion_pg, hc, m.prof_a, _dt(6), deleted_at=_dt(7), motivo_baja="error")
    filas = await HallazgoRepository(sesion_pg).listar(hc.id, pieza=16, incluir_anulados=True)
    assert [h.id for h in filas] == [anulado.id, activo.id]
    assert filas[0].motivo_baja == "error"


@pytest.mark.asyncio
async def test_hallazgo_no_se_filtra_a_otra_hc(sesion_pg):
    from app.repos.hallazgo_repo import HallazgoRepository

    m = await sembrar_mundo(sesion_pg)
    hc_ana = await _hc(sesion_pg, m.ana)
    hc_beto = await _hc(sesion_pg, m.beto)
    de_ana = await _hallazgo(sesion_pg, hc_ana, m.prof_a, _dt(5))
    repo = HallazgoRepository(sesion_pg)
    assert await repo.listar(hc_beto.id) == []
    assert await repo.get_en_hc(hc_beto.id, de_ana.id) is None
    assert (await repo.get_en_hc(hc_ana.id, de_ana.id)).id == de_ana.id


@pytest.mark.asyncio
async def test_estados_vigentes_solo_ultima_version(sesion_pg):
    from app.modelos import EstadoHallazgoCatalogo
    from app.repos.hallazgo_repo import HallazgoRepository

    await sembrar_mundo(sesion_pg)
    repo = HallazgoRepository(sesion_pg)
    version, estados = await repo.estados_vigentes()
    assert version == 1 and len(estados) == 7
    # Entra una V2: la V1 pasa a no vigente y solo cuenta la nueva.
    for fila in estados:
        fila.vigente = False
    sesion_pg.add(EstadoHallazgoCatalogo(codigo="caries", version=2, nombre="Caries", alcance="cualquiera", vigente=True))
    sesion_pg.add(EstadoHallazgoCatalogo(codigo="fractura", version=2, nombre="Fractura", alcance="cualquiera", vigente=True))
    await sesion_pg.flush()
    version, estados = await repo.estados_vigentes()
    assert version == 2 and {e.codigo for e in estados} == {"caries", "fractura"}


@pytest.mark.asyncio
async def test_estados_vigentes_sin_catalogo_devuelve_vacio(sesion_pg):
    from app.repos.hallazgo_repo import HallazgoRepository

    version, estados = await HallazgoRepository(sesion_pg).estados_vigentes()
    assert version is None and estados == []


# --- 3.3 vínculo de turno ---------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("estado", ["asistido", "pendiente", "confirmado", "ausente"])
async def test_vinculo_turno_no_cancelado_true(sesion_pg, estado):
    from app.repos.turno_repo import TurnoRepository

    m = await sembrar_mundo(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_a, m.sillon, estado=estado)
    assert await TurnoRepository(sesion_pg).existe_vinculo(m.prof_a.id, m.ana.id) is True


@pytest.mark.asyncio
async def test_vinculo_solo_cancelado_false(sesion_pg):
    from app.repos.turno_repo import TurnoRepository

    m = await sembrar_mundo(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_a, m.sillon, estado="cancelado")
    assert await TurnoRepository(sesion_pg).existe_vinculo(m.prof_a.id, m.ana.id) is False


@pytest.mark.asyncio
async def test_vinculo_cancelado_mas_uno_vigente_true(sesion_pg):
    from app.repos.turno_repo import TurnoRepository

    m = await sembrar_mundo(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_a, m.sillon, estado="cancelado")
    await crear_turno(sesion_pg, m.ana, m.prof_a, m.sillon, estado="confirmado")
    assert await TurnoRepository(sesion_pg).existe_vinculo(m.prof_a.id, m.ana.id) is True


@pytest.mark.asyncio
async def test_vinculo_otro_profesional_o_paciente_false(sesion_pg):
    from app.repos.turno_repo import TurnoRepository

    m = await sembrar_mundo(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_b, m.sillon)
    repo = TurnoRepository(sesion_pg)
    assert await repo.existe_vinculo(m.prof_a.id, m.ana.id) is False
    assert await repo.existe_vinculo(m.prof_b.id, m.beto.id) is False
