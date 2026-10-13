"""C-06 tasks 1.3/1.4 + 6.2 RED: seed plantillas, render estricto y sin-PHI (D-02).

Unit (siempre corre, fakes en memoria): doble seed -> 5 filas v1; variable
no declarada -> 422 sin envio; plantillas + payloads sin terminos clinicos
ni digitos largos; la fila guarda variables, no el cuerpo; hueco_liberado
acepta {expira_en} declarada para C-07 sin migrar (6.2).
PG-gated: seed real idempotente contra PG.
Datos 100% ficticios. NUNCA PHI en cuerpos/payloads/logs.
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: E402, F401


def test_seed_plantillas_idempotente():
    """Task 1.3 RED: doble seed -> exactamente 5 plantillas en v1."""
    from app.core.seed_plantillas import contar_plantillas, sembrar_plantillas

    almacen: dict = {}
    assert sembrar_plantillas(almacen) == 5
    assert sembrar_plantillas(almacen) == 5
    assert contar_plantillas(almacen) == 5


def test_render_variable_no_declarada_422():
    """Task 1.3 RED: variable fuera del catalogo -> 422, ningun envio."""
    from app.core.seed_plantillas import VariableNoDeclaradaError, render_plantilla

    with pytest.raises(VariableNoDeclaradaError) as exc:
        render_plantilla(
            "recordatorio_48h",
            {"nombre_pila": "Ana", "fecha": "12/10", "hora": "09:00",
             "consultorio_tel": "4000-0000", "diagnostico": "caries"},
        )
    assert exc.value.status_code == 422


def test_render_hueco_extensible_a_oferta():
    """Task 6.2 RED: hueco_liberado acepta {expira_en} declarada sin migrar."""
    from app.core.seed_plantillas import render_plantilla

    texto = render_plantilla(
        "hueco_liberado",
        {"nombre_pila": "Ana", "fecha": "12/10", "hora": "09:00",
         "consultorio_tel": "4000-0000", "expira_en": "2 h"},
    )
    assert "Ana" in texto and "12/10" in texto


def test_render_faltante_422():
    """Triangulacion: placeholder del cuerpo sin valor -> 422, no se envia."""
    from app.core.seed_plantillas import VariableNoDeclaradaError, render_plantilla

    with pytest.raises(VariableNoDeclaradaError):
        render_plantilla("confirmacion", {"nombre_pila": "Ana"})


def test_plantillas_sin_phi():
    """Task 1.4 RED: las 5 plantillas + payloads no matchean clinica ni digitos."""
    from app.core.seed_plantillas import PLANTILLAS_V1, render_plantilla, sin_phi

    assert set(PLANTILLAS_V1) == {
        "recordatorio_48h", "recordatorio_24h", "confirmacion",
        "hueco_liberado", "resena_google",
    }
    for nombre, datos in PLANTILLAS_V1.items():
        assert sin_phi(datos["cuerpo"]), f"PHI en plantilla {nombre}"
    texto = render_plantilla(
        "recordatorio_48h",
        {"nombre_pila": "Ana", "fecha": "12/10", "hora": "09:00",
         "consultorio_tel": "4000-0000"},
    )
    assert sin_phi(texto)
    assert not sin_phi("control de caries pieza 11 el lunes")
    assert not sin_phi("llamar al 1140001111 por la deuda")


def test_payload_no_persiste_cuerpo():
    """Task 1.4 RED (D-01): la fila guarda variables, no el texto renderizado."""
    from app.core.seed_plantillas import variables_para_payload

    variables = {
        "nombre_pila": "Ana", "fecha": "12/10", "hora": "09:00",
        "consultorio_tel": "4000-0000",
    }
    payload = variables_para_payload("recordatorio_48h", variables)
    assert "cuerpo" not in payload
    assert payload["nombre_pila"] == "Ana"
    for valor in payload.values():
        assert "te recordamos tu turno" not in str(valor)


@pytest.mark.asyncio
async def test_seed_pg_idempotente(sesion_pg):
    """Task 1.3 GREEN (PG real): doble seed real -> 5 filas v1."""
    from app.core.seed_plantillas import sembrar_plantillas_pg
    from app.repos.notificacion_repo import PlantillaRepository

    repo = PlantillaRepository(sesion_pg)
    assert await sembrar_plantillas_pg(repo) == 5
    assert await sembrar_plantillas_pg(repo) == 5
    assert await repo.contar_version("v1") == 5
