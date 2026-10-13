"""Catalogo seed de plantillas WhatsApp v1 + render estricto sin-PHI (C-06, D-02).

Cinco plantillas versionadas, upsert idempotente por (nombre, version).
El render SOLO acepta variables declaradas: cualquier otra -> 422 interno y
ningun mensaje se envia. Declarada pero no usada en el cuerpo -> OK (asi
`hueco_liberado` ya declara `{expira_en}` para que C-07 especialice la oferta
sin migrar, task 6.2). Placeholder del cuerpo sin valor -> 422.

PROHIBIDO PHI (RN-CL-04/RN-NO-04): solo nombre de pila + fecha/hora +
telefono del consultorio (+ link de resena). NUNCA diagnostico, pieza,
tratamiento, OS ni monto. `sin_phi` escanea cuerpos y payloads contra lista
bloqueada + regex de digitos largos; los tests fallan antes de enviar.
"""
import re

VERSION_ACTUAL = "v1"

PLANTILLAS_V1: dict[str, dict] = {
    "recordatorio_48h": {
        "cuerpo": (
            "Hola {nombre_pila}, te recordamos tu turno del {fecha} a las {hora}. "
            "Respondé SI para confirmar o llamanos al {consultorio_tel}."
        ),
        "variables": ["nombre_pila", "fecha", "hora", "consultorio_tel"],
    },
    "recordatorio_24h": {
        "cuerpo": (
            "Hola {nombre_pila}, mañana {fecha} a las {hora} tenés tu turno. "
            "Respondé SI para confirmar o llamanos al {consultorio_tel}."
        ),
        "variables": ["nombre_pila", "fecha", "hora", "consultorio_tel"],
    },
    "confirmacion": {
        "cuerpo": (
            "Hola {nombre_pila}, tu turno del {fecha} a las {hora} quedó confirmado. "
            "Te esperamos."
        ),
        "variables": ["nombre_pila", "fecha", "hora", "consultorio_tel"],
    },
    "hueco_liberado": {
        "cuerpo": (
            "Hola {nombre_pila}, se liberó un turno el {fecha} a las {hora}. "
            "Si lo querés, respondé SI o llamanos al {consultorio_tel}."
        ),
        # `expira_en` declarada para la futura `oferta_lista_espera` (C-07):
        # el render la tolera aunque este cuerpo no la use (task 6.2).
        "variables": ["nombre_pila", "fecha", "hora", "consultorio_tel", "expira_en"],
    },
    "resena_google": {
        "cuerpo": (
            "Hola {nombre_pila}, gracias por tu visita. "
            "Si querés, dejanos tu reseña aquí: {link_resena}."
        ),
        "variables": ["nombre_pila", "link_resena"],
    },
}

# Lista bloqueada clinica/administrativa (minusculas, subcadena). Si un cuerpo
# o payload la matchea, el test sin-PHI falla antes de cualquier envio.
TERMINOS_BLOQUEADOS = (
    "diagnóstico", "diagnostico", "caries", "endodoncia", "corona", "implante",
    "pieza", "fdi", "obra social", "prepaga", "monto", "deuda", "historia clínica",
    "historia clinica", "tratamiento", "conducto", "extracción", "extraccion",
    "ortodoncia", "bracket", "anestesia", "dolor", "sangrado", "radiografía",
    "radiografia", "presupuesto", "factura",
)
# DNI/telefono accidental en el cuerpo: 8+ digitos seguidos.
_RE_DIGITOS_LARGOS = re.compile(r"\d{8,}")
_RE_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


class VariableNoDeclaradaError(ValueError):
    """Variable fuera del catalogo o placeholder sin valor (se mapea a 422)."""

    status_code = 422


def variables_declaradas(nombre: str) -> list[str]:
    try:
        return list(PLANTILLAS_V1[nombre]["variables"])
    except KeyError:
        raise VariableNoDeclaradaError(f"plantilla {nombre} desconocida") from None


def render_plantilla(nombre: str, variables: dict[str, str]) -> str:
    """Renderiza con SOLO variables declaradas; resto -> 422 sin enviar."""
    datos = PLANTILLAS_V1.get(nombre)
    if datos is None:
        raise VariableNoDeclaradaError(f"plantilla {nombre} desconocida")
    declaradas = set(datos["variables"])
    for clave in variables:
        if clave not in declaradas:
            raise VariableNoDeclaradaError(
                f"variable {clave} no declarada en {nombre}"
            )
    cuerpo: str = datos["cuerpo"]
    for marcador in _RE_PLACEHOLDER.findall(cuerpo):
        if marcador not in variables:
            raise VariableNoDeclaradaError(
                f"variable {marcador} sin valor en {nombre}"
            )
    return cuerpo.format(**{k: variables[k] for k in _RE_PLACEHOLDER.findall(cuerpo)})


def sin_phi(texto: str) -> bool:
    """True si el texto no contiene clinica bloqueada ni digitos largos."""
    bajo = texto.lower()
    if any(termino in bajo for termino in TERMINOS_BLOQUEADOS):
        return False
    return _RE_DIGITOS_LARGOS.search(texto) is None


def variables_para_payload(nombre: str, variables: dict[str, str]) -> dict[str, str]:
    """Payload persistible: solo variables declaradas, nunca el cuerpo (D-01)."""
    declaradas = set(variables_declaradas(nombre))
    for clave in variables:
        if clave not in declaradas:
            raise VariableNoDeclaradaError(
                f"variable {clave} no declarada en {nombre}"
            )
    return {k: v for k, v in variables.items() if k in declaradas}


def sembrar_plantillas(almacen: dict) -> int:
    """Seed idempotente en memoria (tests sin PG): upsert por nombre+version."""
    for nombre, datos in PLANTILLAS_V1.items():
        almacen[(nombre, VERSION_ACTUAL)] = {
            "cuerpo": datos["cuerpo"],
            "variables": list(datos["variables"]),
        }
    return contar_plantillas(almacen)


def contar_plantillas(almacen: dict) -> int:
    return sum(1 for (_, version) in almacen if version == VERSION_ACTUAL)


async def sembrar_plantillas_pg(plantillas_repo) -> int:
    """Seed idempotente contra PG real (upsert por nombre+version, D-02)."""
    for nombre, datos in PLANTILLAS_V1.items():
        await plantillas_repo.upsert(
            nombre, VERSION_ACTUAL, datos["cuerpo"], list(datos["variables"])
        )
    return await plantillas_repo.contar_version(VERSION_ACTUAL)


__all__ = [
    "PLANTILLAS_V1",
    "TERMINOS_BLOQUEADOS",
    "VERSION_ACTUAL",
    "VariableNoDeclaradaError",
    "contar_plantillas",
    "render_plantilla",
    "sembrar_plantillas",
    "sembrar_plantillas_pg",
    "sin_phi",
    "variables_declaradas",
    "variables_para_payload",
]
