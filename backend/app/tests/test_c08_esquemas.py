"""C-08 grupo 2: esquemas Pydantic estrictos de historia clínica y odontograma (D-02, D-03, D-08).

Puro (sin DB): siempre corre. Datos ficticios.
"""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

VALIDAS = [11, 18, 21, 28, 31, 38, 41, 48, 16, 36]
INVALIDAS = [10, 19, 20, 29, 30, 39, 40, 49, 51, 85, 0, -11, 111]
HALLAZGO = {"pieza_fdi": 16, "cara": "oclusal", "estado": "caries"}


# --- 2.1 historia ----------------------------------------------------------------

@pytest.mark.parametrize("pieza", VALIDAS)
def test_pieza_fdi_valida_aceptada(pieza):
    from app.esquemas.clinica import HallazgoIn

    cara = "oclusal"
    assert HallazgoIn(**{**HALLAZGO, "pieza_fdi": pieza, "cara": cara}).pieza_fdi == pieza


@pytest.mark.parametrize("pieza", INVALIDAS)
def test_pieza_fdi_invalida_rechazada(pieza):
    from app.esquemas.clinica import HallazgoIn

    with pytest.raises(ValidationError):
        HallazgoIn(**{**HALLAZGO, "pieza_fdi": pieza})


@pytest.mark.parametrize("vacia", ["", "   ", "\n\t "])
def test_historia_alergias_vacias_normalizan_a_null(vacia):
    from app.esquemas.clinica import HistoriaIn, HistoriaPatch

    assert HistoriaIn(paciente_id=1, alergias=vacia).alergias is None
    assert HistoriaPatch(alergias=vacia).alergias is None


def test_historia_alergias_con_texto_se_conservan_recortadas():
    from app.esquemas.clinica import HistoriaIn

    h = HistoriaIn(paciente_id=1, alergias="  Penicilina  ", antecedentes="Hipertensión")
    assert h.alergias == "Penicilina" and h.antecedentes == "Hipertensión"


def test_historia_patch_distingue_campo_omitido_de_null():
    from app.esquemas.clinica import HistoriaPatch

    assert HistoriaPatch(alergias="Látex").model_dump(exclude_unset=True) == {"alergias": "Látex"}
    assert HistoriaPatch(alergias="").model_dump(exclude_unset=True) == {"alergias": None}


@pytest.mark.parametrize("clase,args", [
    ("HistoriaIn", {"paciente_id": 1, "extra": "x"}),
    ("HistoriaPatch", {"campo": "x"}),
    ("BajaIn", {"motivo_baja": "x", "otro": 1}),
    ("HallazgoIn", {**HALLAZGO, "catalogo_version": 1}),
    ("HallazgoIn", {**HALLAZGO, "profesional_id": 1}),
    ("HallazgoIn", {**HALLAZGO, "fecha": "2026-10-30T10:00:00Z"}),
])
def test_historia_campo_extra_422(clase, args):
    from app.esquemas import clinica

    with pytest.raises(ValidationError):
        getattr(clinica, clase)(**args)


@pytest.mark.parametrize("campo,largo", [("alergias", 2001), ("antecedentes", 10001)])
def test_historia_texto_demasiado_largo_invalido(campo, largo):
    from app.esquemas.clinica import HistoriaIn

    with pytest.raises(ValidationError):
        HistoriaIn(paciente_id=1, **{campo: "a" * largo})


@pytest.mark.parametrize("motivo", [None, "", "   "])
def test_baja_sin_motivo_invalida(motivo):
    from app.esquemas.clinica import BajaIn

    with pytest.raises(ValidationError):
        BajaIn(motivo_baja=motivo)
    with pytest.raises(ValidationError):
        BajaIn()


def test_baja_con_motivo_valida():
    from app.esquemas.clinica import BajaIn

    assert BajaIn(motivo_baja="  cargada por error ").motivo_baja == "cargada por error"


def test_historia_out_incluye_alergias_aunque_sean_null():
    from datetime import datetime, timezone

    from app.esquemas.clinica import HistoriaOut

    ahora = datetime(2026, 10, 30, tzinfo=timezone.utc)
    out = HistoriaOut(id=1, paciente_id=2, antecedentes=None, alergias=None,
                      created_at=ahora, updated_at=ahora, deleted_at=None, motivo_baja=None)
    assert "alergias" in out.model_dump() and out.alergias is None


def test_tratamiento_out_conserva_precio_exacto():
    from decimal import Decimal

    from app.esquemas.clinica import TratamientoOut

    t = TratamientoOut(id=1, codigo="OBT", codigo_nomenclador=None, nombre="Obturación",
                       precio_base=Decimal("1234.50"))
    assert t.model_dump(mode="json")["precio_base"] == "1234.50"


# --- 2.2 hallazgos -----------------------------------------------------------------

def test_hallazgo_palatina_pieza_36_invalida():
    from app.esquemas.clinica import HallazgoIn

    with pytest.raises(ValidationError):
        HallazgoIn(pieza_fdi=36, cara="palatina", estado="caries")


def test_hallazgo_lingual_pieza_16_invalida():
    from app.esquemas.clinica import HallazgoIn

    with pytest.raises(ValidationError):
        HallazgoIn(pieza_fdi=16, cara="lingual", estado="caries")


@pytest.mark.parametrize("pieza,cara", [(16, "palatina"), (26, "palatina"), (36, "lingual"), (46, "lingual")])
def test_hallazgo_cara_de_su_arcada_valida(pieza, cara):
    from app.esquemas.clinica import HallazgoCorreccionIn, HallazgoIn

    HallazgoIn(pieza_fdi=pieza, cara=cara, estado="caries")
    HallazgoCorreccionIn(pieza_fdi=pieza, cara=cara, estado="caries", motivo="x")


def test_hallazgo_cara_fuera_de_catalogo_o_omitida_invalida():
    from app.esquemas.clinica import HallazgoIn

    with pytest.raises(ValidationError):
        HallazgoIn(pieza_fdi=16, cara="incisal", estado="caries")
    with pytest.raises(ValidationError):
        HallazgoIn(pieza_fdi=16, estado="caries")


def test_hallazgo_con_profesional_id_invalido():
    from app.esquemas.clinica import HallazgoIn

    with pytest.raises(ValidationError):
        HallazgoIn(**HALLAZGO, profesional_id=1)


def test_hallazgo_con_fecha_invalido():
    from app.esquemas.clinica import HallazgoIn

    with pytest.raises(ValidationError):
        HallazgoIn(**HALLAZGO, fecha="2026-10-30T10:00:00Z")


def test_hallazgo_con_catalogo_version_invalido():
    from app.esquemas.clinica import HallazgoCorreccionIn, HallazgoIn

    with pytest.raises(ValidationError):
        HallazgoIn(**HALLAZGO, catalogo_version=1)
    with pytest.raises(ValidationError):
        HallazgoCorreccionIn(**HALLAZGO, motivo="x", catalogo_version=1)


@pytest.mark.parametrize("motivo", [None, "", "  "])
def test_correccion_sin_motivo_invalida(motivo):
    from app.esquemas.clinica import HallazgoCorreccionIn

    with pytest.raises(ValidationError):
        HallazgoCorreccionIn(**HALLAZGO, motivo=motivo)
    with pytest.raises(ValidationError):
        HallazgoCorreccionIn(**HALLAZGO)


def test_correccion_con_motivo_valida():
    from app.esquemas.clinica import HallazgoCorreccionIn

    assert HallazgoCorreccionIn(**HALLAZGO, motivo=" error de pieza ").motivo == "error de pieza"


def test_respuestas_con_alergias_en_la_raiz():
    from app.esquemas.clinica import HallazgoConAlergias, HallazgosConAlergias

    assert set(HallazgosConAlergias.model_fields) == {"alergias", "hallazgos"}
    assert set(HallazgoConAlergias.model_fields) == {"alergias", "hallazgo"}


def test_catalogo_out_lleva_version_y_estados():
    from app.esquemas.clinica import CatalogoOut

    out = CatalogoOut(version=1, estados=[{"codigo": "caries", "nombre": "Caries", "alcance": "cualquiera"}])
    assert out.model_dump()["estados"][0]["alcance"] == "cualquiera"
