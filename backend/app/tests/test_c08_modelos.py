"""C-08 grupo 1: modelos clínicos + CHECK/UNIQUE/FK contra PG real (D-02..D-06, D-10).

RED primero: los modelos no existen. Postgres real (nunca SQLite): los CHECK,
la FK compuesta y el UNIQUE parcial solo se prueban ahí. Datos ficticios.
"""
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import cargar_catalogo_estados, sesion_pg  # noqa: E402, F401

PIEZAS_VALIDAS = [q * 10 + n for q in (1, 2, 3, 4) for n in range(1, 9)]
PIEZAS_INVALIDAS = [10, 19, 20, 29, 30, 39, 40, 49, 51, 85]


async def _base(sesion, dni="30111222"):
    """Paciente + profesional + catálogo V1 (ficticios); devuelve (paciente, profesional)."""
    from app.modelos import Paciente, Profesional

    await cargar_catalogo_estados(sesion)
    paciente = Paciente(nombre="Ana", apellido="Ficticia", dni=dni)
    profesional = Profesional(matricula=f"DEMO-{dni}", especialidades="Odontología general")
    sesion.add_all([paciente, profesional])
    await sesion.flush()
    return paciente, profesional


async def _hc(sesion, paciente):
    from app.modelos import HistoriaClinica

    hc = HistoriaClinica(paciente_id=paciente.id)
    sesion.add(hc)
    await sesion.flush()
    return hc


def _hallazgo(hc, profesional, **cambios):
    from app.modelos import HallazgoOdontograma

    datos = {
        "hc_id": hc.id, "pieza_fdi": 16, "cara": "oclusal", "estado": "caries",
        "catalogo_version": 1, "fecha": sa.func.now(), "profesional_id": profesional.id,
    }
    datos.update(cambios)
    return HallazgoOdontograma(**datos)


async def _rechaza(sesion, entidad):
    sesion.add(entidad)
    with pytest.raises(IntegrityError):
        await sesion.flush()
    await sesion.rollback()


# --- 1.2 catálogo de estados y tratamiento -----------------------------------

@pytest.mark.asyncio
async def test_catalogo_codigo_version_duplicado_rechazado(sesion_pg):
    from app.modelos import EstadoHallazgoCatalogo

    await cargar_catalogo_estados(sesion_pg)
    await _rechaza(sesion_pg, EstadoHallazgoCatalogo(
        codigo="caries", version=1, nombre="Otra", alcance="cualquiera", vigente=True))


@pytest.mark.asyncio
async def test_catalogo_misma_clave_en_otra_version_ok(sesion_pg):
    from app.modelos import EstadoHallazgoCatalogo

    await cargar_catalogo_estados(sesion_pg)
    sesion_pg.add(EstadoHallazgoCatalogo(
        codigo="caries", version=2, nombre="Caries", alcance="cualquiera", vigente=True))
    await sesion_pg.flush()  # no levanta


@pytest.mark.asyncio
async def test_catalogo_alcance_fuera_de_valores_rechazado(sesion_pg):
    from app.modelos import EstadoHallazgoCatalogo

    await _rechaza(sesion_pg, EstadoHallazgoCatalogo(
        codigo="x", version=1, nombre="X", alcance="cara", vigente=True))


def test_catalogo_v1_constante_tiene_los_siete_estados_de_la_kb():
    from app.modelos.hallazgo_odontograma import CATALOGO_ESTADOS_V1

    por_alcance = {"pieza": set(), "cualquiera": set()}
    for codigo, _nombre, alcance in CATALOGO_ESTADOS_V1:
        por_alcance[alcance].add(codigo)
    assert por_alcance["pieza"] == {"corona", "endodoncia", "implante", "ausente"}
    assert por_alcance["cualquiera"] == {"sano", "caries", "obturacion"}
    assert len(CATALOGO_ESTADOS_V1) == 7


@pytest.mark.asyncio
async def test_tratamiento_codigo_duplicado_rechazado(sesion_pg):
    from app.modelos import Tratamiento

    sesion_pg.add(Tratamiento(codigo="OBT-1", nombre="Obturación", precio_base=100))
    await sesion_pg.flush()
    await _rechaza(sesion_pg, Tratamiento(codigo="OBT-1", nombre="Otra", precio_base=1))


@pytest.mark.asyncio
@pytest.mark.parametrize("precio", [-1, "-0.01"])
async def test_tratamiento_precio_negativo_rechazado(sesion_pg, precio):
    from app.modelos import Tratamiento

    await _rechaza(sesion_pg, Tratamiento(codigo="NEG", nombre="N", precio_base=precio))


@pytest.mark.asyncio
async def test_tratamiento_precio_cero_y_nomenclador_opcional_ok(sesion_pg):
    from app.modelos import Tratamiento

    t = Tratamiento(codigo="CERO", nombre="Control", precio_base=0)
    sesion_pg.add(t)
    await sesion_pg.flush()
    assert t.codigo_nomenclador is None and t.id is not None


# --- 1.3 historia clínica -------------------------------------------------------

@pytest.mark.asyncio
async def test_hc_paciente_duplicado_rechazado(sesion_pg):
    from app.modelos import HistoriaClinica

    paciente, _ = await _base(sesion_pg)
    await _hc(sesion_pg, paciente)
    await _rechaza(sesion_pg, HistoriaClinica(paciente_id=paciente.id))


@pytest.mark.asyncio
async def test_hc_duplicada_aun_con_baja_rechazada(sesion_pg):
    from app.modelos import HistoriaClinica

    paciente, _ = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    hc.deleted_at = sa.func.now()
    hc.motivo_baja = "error de carga"
    await sesion_pg.flush()
    await _rechaza(sesion_pg, HistoriaClinica(paciente_id=paciente.id))


@pytest.mark.asyncio
async def test_hc_baja_sin_motivo_rechazada(sesion_pg):
    from app.modelos import HistoriaClinica

    paciente, _ = await _base(sesion_pg)
    await _rechaza(sesion_pg, HistoriaClinica(paciente_id=paciente.id, deleted_at=sa.func.now()))


@pytest.mark.asyncio
async def test_hc_motivo_sin_baja_rechazado(sesion_pg):
    from app.modelos import HistoriaClinica

    paciente, _ = await _base(sesion_pg)
    await _rechaza(sesion_pg, HistoriaClinica(paciente_id=paciente.id, motivo_baja="x"))


@pytest.mark.asyncio
@pytest.mark.parametrize("campo,largo", [("antecedentes", 10001), ("alergias", 2001)])
async def test_hc_texto_sobre_el_limite_rechazado(sesion_pg, campo, largo):
    from app.modelos import HistoriaClinica

    paciente, _ = await _base(sesion_pg)
    await _rechaza(sesion_pg, HistoriaClinica(paciente_id=paciente.id, **{campo: "a" * largo}))


@pytest.mark.asyncio
async def test_hc_texto_en_el_limite_ok(sesion_pg):
    from app.modelos import HistoriaClinica

    paciente, _ = await _base(sesion_pg)
    sesion_pg.add(HistoriaClinica(paciente_id=paciente.id, antecedentes="a" * 10000, alergias="b" * 2000))
    await sesion_pg.flush()


# --- 1.4 hallazgos ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_hallazgo_las_32_piezas_validas_pasan(sesion_pg):
    paciente, profesional = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    sesion_pg.add_all([_hallazgo(hc, profesional, pieza_fdi=p) for p in PIEZAS_VALIDAS])
    await sesion_pg.flush()
    total = await sesion_pg.scalar(sa.text("SELECT count(*) FROM hallazgo_odontograma"))
    assert total == 32


@pytest.mark.asyncio
@pytest.mark.parametrize("pieza", PIEZAS_INVALIDAS)
async def test_hallazgo_pieza_invalida_rechazada(sesion_pg, pieza):
    paciente, profesional = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    await _rechaza(sesion_pg, _hallazgo(hc, profesional, pieza_fdi=pieza))


@pytest.mark.asyncio
async def test_hallazgo_palatina_inferior_rechazada(sesion_pg):
    paciente, profesional = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    await _rechaza(sesion_pg, _hallazgo(hc, profesional, pieza_fdi=36, cara="palatina"))


@pytest.mark.asyncio
async def test_hallazgo_lingual_superior_rechazada(sesion_pg):
    paciente, profesional = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    await _rechaza(sesion_pg, _hallazgo(hc, profesional, pieza_fdi=16, cara="lingual"))


@pytest.mark.asyncio
@pytest.mark.parametrize("pieza,cara", [(16, "palatina"), (26, "palatina"), (36, "lingual"), (46, "lingual")])
async def test_hallazgo_cara_de_su_arcada_ok(sesion_pg, pieza, cara):
    paciente, profesional = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    sesion_pg.add(_hallazgo(hc, profesional, pieza_fdi=pieza, cara=cara))
    await sesion_pg.flush()


@pytest.mark.asyncio
async def test_hallazgo_cara_fuera_de_catalogo_rechazada(sesion_pg):
    paciente, profesional = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    await _rechaza(sesion_pg, _hallazgo(hc, profesional, cara="incisal"))


@pytest.mark.asyncio
@pytest.mark.parametrize("estado,version", [("desconocido", 1), ("caries", 7)])
async def test_hallazgo_estado_fuera_de_catalogo_rechazado(sesion_pg, estado, version):
    paciente, profesional = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    await _rechaza(sesion_pg, _hallazgo(hc, profesional, estado=estado, catalogo_version=version))


@pytest.mark.asyncio
async def test_hallazgo_baja_sin_motivo_rechazada(sesion_pg):
    paciente, profesional = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    await _rechaza(sesion_pg, _hallazgo(hc, profesional, deleted_at=sa.func.now()))


@pytest.mark.asyncio
async def test_hallazgo_motivo_sin_baja_rechazado(sesion_pg):
    paciente, profesional = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    await _rechaza(sesion_pg, _hallazgo(hc, profesional, motivo_baja="x"))


@pytest.mark.asyncio
async def test_hallazgo_baja_con_motivo_ok(sesion_pg):
    paciente, profesional = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    sesion_pg.add(_hallazgo(hc, profesional, deleted_at=sa.func.now(), motivo_baja="cargado por error"))
    await sesion_pg.flush()


@pytest.mark.asyncio
async def test_hallazgo_segunda_correccion_rechazada(sesion_pg):
    paciente, profesional = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    original = _hallazgo(hc, profesional, deleted_at=sa.func.now(), motivo_baja="error")
    sesion_pg.add(original)
    await sesion_pg.flush()
    sesion_pg.add(_hallazgo(hc, profesional, corrige_a_id=original.id))
    await sesion_pg.flush()
    await _rechaza(sesion_pg, _hallazgo(hc, profesional, corrige_a_id=original.id))


@pytest.mark.asyncio
async def test_hallazgo_sin_correccion_pueden_ser_muchos(sesion_pg):
    """El UNIQUE parcial solo aplica a corrige_a_id no nulo."""
    paciente, profesional = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    sesion_pg.add_all([_hallazgo(hc, profesional), _hallazgo(hc, profesional)])
    await sesion_pg.flush()


@pytest.mark.asyncio
async def test_hc_con_hallazgos_no_se_borra_fisicamente(sesion_pg):
    paciente, profesional = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    sesion_pg.add(_hallazgo(hc, profesional))
    await sesion_pg.flush()
    with pytest.raises(IntegrityError):
        await sesion_pg.execute(sa.text("DELETE FROM historia_clinica WHERE id = :i"), {"i": hc.id})
    await sesion_pg.rollback()


@pytest.mark.asyncio
async def test_profesional_con_hallazgos_no_se_borra(sesion_pg):
    paciente, profesional = await _base(sesion_pg)
    hc = await _hc(sesion_pg, paciente)
    sesion_pg.add(_hallazgo(hc, profesional))
    await sesion_pg.flush()
    with pytest.raises(IntegrityError):
        await sesion_pg.execute(sa.text("DELETE FROM profesional WHERE id = :i"), {"i": profesional.id})
    await sesion_pg.rollback()


def test_hallazgo_declara_los_cuatro_indices_de_d05():
    from app.modelos import HallazgoOdontograma

    nombres = {i.name for i in HallazgoOdontograma.__table__.indexes}
    assert nombres >= {"ix_hallazgo_hc_pieza", "ix_hallazgo_profesional_id",
                       "ix_hallazgo_estado_version", "uq_hallazgo_corrige_a"}
