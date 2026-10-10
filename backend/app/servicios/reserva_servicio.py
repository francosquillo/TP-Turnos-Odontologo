"""Servicio reserva publica (C-05): token, paciente minimo y confirmacion.

Compone `agenda_servicio` SIN modificarlo (D-03/D-06/D-08): huecos, creacion
con EXCLUDE como autoridad final y maquina pendiente->confirmado se reutilizan.
La via publica NUNCA crea sobreturnos y `creado_por` queda NULL (sin JWT).

Token (D-01): opaco 256 bits; en DB solo hash SHA-256; un solo uso (NULL al
confirmar). Expiracion derivada min(created_at + 72 h, inicio), sin DDL (D-02).

Reuso vs desconocido (spec > D-06): el hash se borra al confirmar, asi que el
reuso se distingue del token jamas emitido con un set de usados
(`reserva:usado:{hash}`, TTL 30 dias). Sin tienda (o Redis caido) el reuso
degrada a 404 generico en vez de 410:documentado, nunca 500.
"""
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.servicios import agenda_servicio as agenda

TOKEN_EXPIRA_HORAS = 72
USADOS_TTL_SEG = 30 * 24 * 3600
# Telefono ficticio del consultorio para pantallas 410 (dato de prueba,
# configurable en frontend via VITE_CONSULTORIO_TEL; nunca un numero real).
CONTACTO_CONSULTORIO = "+54 11 4000-0000"
APELLIDO_RESERVA_ONLINE = "(online)"

_log = logging.getLogger(__name__)


class TelefonoInvalidoError(ValueError):
    """Telefono con menos de 8 digitos (se mapea a 422)."""


class NombreInvalidoError(ValueError):
    """Nombre con menos de 2 caracteres (se mapea a 422)."""


class TokenDesconocidoError(LookupError):
    """Token que nunca existio (se mapea a 404 generico)."""


class TokenExpiradoError(ValueError):
    """Token vencido por 72 h o por inicio (se mapea a 410 + contacto)."""

    def __init__(
        self, mensaje: str = "token expirado", contacto: str = CONTACTO_CONSULTORIO
    ) -> None:
        super().__init__(mensaje)
        self.contacto = contacto


class TokenUsadoError(ValueError):
    """Token ya confirmado (se mapea a 410, segundo uso no cambia nada)."""


class TurnoNoConfirmableError(ValueError):
    """Turno ya no pendiente, p. ej. cancelado (se mapea a 410 honesto)."""


@dataclass
class ReservaCreada:
    turno: object
    token: str
    expira_en: datetime


def generar_token() -> str:
    """Token opaco 256 bits para URL (nunca se persiste ni se loguea)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 hex del token: lo unico que toca la DB (D-01)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def expira_en(creado_en: datetime, inicio: datetime) -> datetime:
    """Vencimiento derivado min(creado + 72 h, inicio), sin columna (D-02)."""
    return min(creado_en + timedelta(hours=TOKEN_EXPIRA_HORAS), inicio)


def token_expirado(creado_en: datetime, inicio: datetime, ahora: datetime) -> bool:
    """True si `ahora` alcanzo el vencimiento derivado."""
    return ahora >= expira_en(creado_en, inicio)


def normalizar_telefono(telefono: str) -> str:
    """Solo digitos, minimo 8 (D-05); invalido -> TelefonoInvalidoError."""
    digitos = "".join(c for c in str(telefono or "") if c.isdigit())
    if len(digitos) < 8:
        raise TelefonoInvalidoError("telefono invalido (minimo 8 digitos)")
    return digitos


def _validar_nombre(nombre: str) -> str:
    limpio = (nombre or "").strip()
    if len(limpio) < 2:
        raise NombreInvalidoError("nombre invalido (minimo 2 caracteres)")
    return limpio


async def obtener_o_crear_paciente_minimo(
    pacientes_repo,
    nombre: str,
    telefono: str,
    dni: str | None = None,
    email: str | None = None,
):
    """Match por telefono normalizado (no soft-deleted) o crea minimo (D-05).

    El modelo exige `apellido` NOT NULL: se marca "(online)" para que
    secretaria lo complete (resto NULL). Sin verificacion por SMS en v1.0
    (riesgo aceptado: pendiente que secretaria cancela con motivo).
    """
    nombre_ok = _validar_nombre(nombre)
    telefono_ok = normalizar_telefono(telefono)
    existente = await pacientes_repo.por_telefono(telefono_ok)
    if existente is not None:
        return existente
    return await pacientes_repo.crear(
        nombre=nombre_ok,
        apellido=APELLIDO_RESERVA_ONLINE,
        telefono=telefono_ok,
        dni=dni,
        email=email,
    )


def _cubre_horario(
    huecos: list[tuple[datetime, datetime]], inicio: datetime, fin: datetime
) -> bool:
    """True si los slots libres embaldosan [inicio, fin) sin huecos (RN-TU-05)."""
    cursor = inicio
    for slot_ini, slot_fin in sorted(huecos):
        if slot_ini != cursor:
            return False
        cursor = slot_fin
        if cursor >= fin:
            return True
    return cursor >= fin


async def _exigir_hueco_ofrecible(
    turnos_repo, profesionales_repo, profesional, sillon_id: int,
    inicio: datetime, fin: datetime,
) -> None:
    """409 con re-oferta si [inicio, fin) no es ofrecible ahora (D-03)."""
    config = getattr(profesional, "agenda_config", None) or {}
    ocupados_raw = await turnos_repo.activos_en_rango(
        inicio, fin,
        profesional_id=getattr(profesional, "id", None), sillon_id=sillon_id,
    )
    huecos = agenda.calcular_huecos(
        config, inicio, fin, [(t.inicio, t.fin) for t in ocupados_raw]
    )
    solapa = await turnos_repo.hay_solapamiento(
        getattr(profesional, "id", None), sillon_id, inicio, fin
    )
    if solapa or not _cubre_horario(huecos, inicio, fin):
        alternativas = await agenda.sugerir_alternativas(
            turnos_repo, profesional, sillon_id, inicio, fin - inicio
        )
        raise agenda.HuecoOcupadoError("hueco ocupado", alternativas=alternativas)


async def crear_reserva(
    turnos_repo,
    pacientes_repo,
    profesionales_repo,
    sillones_repo,
    *,
    profesional_id: int,
    sillon_id: int,
    inicio: datetime,
    fin: datetime,
    nombre: str,
    telefono: str,
    dni: str | None = None,
    email: str | None = None,
    ahora: datetime | None = None,
) -> ReservaCreada:
    """Reserva publica: valida hueco, matchea paciente, delega en agenda (D-03).

    Nace `pendiente` con `origen="online"`, sin sobreturno, `creado_por=NULL`.
    Colision -> HuecoOcupadoError (el router mapea a 409 con alternativas).
    """
    if fin <= inicio:
        raise ValueError("fin debe ser > inicio")
    momento = ahora or datetime.now(timezone.utc)
    profesional = await profesionales_repo.get(profesional_id)
    if profesional is None:
        raise agenda.EntidadNoEncontradaError("profesional inexistente")
    if await sillones_repo.get(sillon_id) is None:
        raise agenda.EntidadNoEncontradaError("sillon inexistente")
    paciente = await obtener_o_crear_paciente_minimo(
        pacientes_repo, nombre, telefono, dni=dni, email=email
    )
    await _exigir_hueco_ofrecible(
        turnos_repo, profesionales_repo, profesional, sillon_id, inicio, fin
    )
    try:
        turno = await agenda.crear_turno(
            turnos_repo,
            pacientes_repo,
            profesionales_repo,
            sillones_repo,
            paciente_id=paciente.id,
            profesional_id=profesional_id,
            sillon_id=sillon_id,
            inicio=inicio,
            fin=fin,
            origen="online",
            sobre_turno=False,
            creado_por=None,
            ahora=momento,
        )
    except agenda.HuecoOcupadoError as exc:
        # Carrera: el pre-chequeo paso pero la DB (EXCLUDE) decidio. Si el
        # error no trae re-oferta, se calcula aca para el 409 del router.
        if not exc.alternativas:
            exc.alternativas = await agenda.sugerir_alternativas(
                turnos_repo, profesional, sillon_id, inicio, fin - inicio
            )
        raise
    token = generar_token()
    await turnos_repo.actualizar(
        turno, token_confirmacion_hash=hash_token(token)
    )
    creado_en = getattr(turno, "created_at", None) or momento
    return ReservaCreada(
        turno=turno, token=token, expira_en=expira_en(creado_en, inicio)
    )


def _clave_usado(token_hash: str) -> str:
    return f"reserva:usado:{token_hash}"


async def _fue_usado(tienda_usados, token_hash: str) -> bool:
    if tienda_usados is None:
        return False
    try:
        return await tienda_usados.get(_clave_usado(token_hash)) is not None
    except Exception:
        return False


async def _marcar_usado(tienda_usados, token_hash: str) -> None:
    if tienda_usados is None:
        return
    try:
        await tienda_usados.set(_clave_usado(token_hash), "1", ex=USADOS_TTL_SEG)
    except Exception as exc:  # Redis caido: el reuso degrada a 404, nunca 500
        _log.warning("no se pudo marcar token usado: %s", exc)


async def confirmar_por_token(
    turnos_repo,
    token: str,
    ahora: datetime | None = None,
    tienda_usados=None,
):
    """Confirma via token: pendiente->confirmado + hash NULL (D-06).

    Desconocido -> TokenDesconocidoError (404 generico, sin filtrar si el
    token fue real). Reusado -> TokenUsadoError (410). Expirado ->
    TokenExpiradoError (410 + contacto). No pendiente -> 410 honesto.
    """
    momento = ahora or datetime.now(timezone.utc)
    token_hash = hash_token(token or "")
    turno = await turnos_repo.por_token_hash(token_hash)
    if turno is None:
        if await _fue_usado(tienda_usados, token_hash):
            raise TokenUsadoError("este turno ya fue confirmado")
        raise TokenDesconocidoError("token inexistente")
    creado_en = getattr(turno, "created_at", None) or momento
    if token_expirado(creado_en, turno.inicio, momento):
        raise TokenExpiradoError()
    if turno.estado != "pendiente":
        if turno.estado == "cancelado":
            raise TurnoNoConfirmableError(
                f"este turno ya fue cancelado, llamá al consultorio ({CONTACTO_CONSULTORIO})"
            )
        raise TurnoNoConfirmableError(
            f"este turno ya está {turno.estado}, llamá al consultorio ({CONTACTO_CONSULTORIO})"
        )
    turno = await agenda.cambiar_estado(turnos_repo, turno.id, "confirmado")
    await turnos_repo.actualizar(turno, token_confirmacion_hash=None)
    await _marcar_usado(tienda_usados, token_hash)
    return turno


__all__ = [
    "APELLIDO_RESERVA_ONLINE",
    "CONTACTO_CONSULTORIO",
    "TOKEN_EXPIRA_HORAS",
    "NombreInvalidoError",
    "ReservaCreada",
    "TelefonoInvalidoError",
    "TokenDesconocidoError",
    "TokenExpiradoError",
    "TokenUsadoError",
    "TurnoNoConfirmableError",
    "confirmar_por_token",
    "crear_reserva",
    "expira_en",
    "generar_token",
    "hash_token",
    "normalizar_telefono",
    "obtener_o_crear_paciente_minimo",
    "token_expirado",
]
