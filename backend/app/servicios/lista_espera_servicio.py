"""Servicio lista de espera: oferta, expiración 2 h, cascada, conversión (C-07).

Compone `agenda_servicio` y `reserva_servicio` SIN modificarlas (patrón
componer-no-modificar de C-05/C-06). Reutiliza `generar_token`/`hash_token`
de `reserva_servicio` para el token de oferta.

Toda oferta: `oferta_expira_en = ahora + OFERTA_EXPIRA_HORAS` (2 h),
hash SHA-256 en DB, un solo uso: al consumirse la entry deja de estar
`ofrecida` y el hash queda como tombstone (reusar el link = 410, no 404).
"""
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.seed_plantillas import (
    VariableNoDeclaradaError,
    sin_phi,
    variables_para_payload,
)
from app.modelos import EsperaEntry
from app.repos.notificacion_repo import NotificacionRepository
from app.servicios import agenda_servicio as agenda
from app.servicios import notificacion_servicio as notif_svc
from app.servicios.reserva_servicio import generar_token, hash_token

OFERTA_EXPIRA_HORAS = 2
TZ_BA = ZoneInfo("America/Argentina/Buenos_Aires")

_log = logging.getLogger(__name__)


class HuecoOcupadoError(agenda.HuecoOcupadoError):
    """Re-export de agenda_servicio.HuecoOcupadoError para el router."""


class EntradaNoEncontradaError(LookupError):
    """EsperaEntry inexistente (se mapea a 404)."""


class OfertaYaActivaError(ValueError):
    """La entry ya tiene una oferta sobresaliente (se mapea a 409)."""


class TokenDesconocidoError(LookupError):
    """Token que nunca existió (se mapea a 404 genérico)."""


class TokenUsadoError(ValueError):
    """Token ya consumido (entry convertida/vencida → 410, sin mutar)."""


class TokenExpiradoError(ValueError):
    """Token vencido (ofrecida con ahora >= oferta_expira_en → 410 + cascada)."""


async def intentar_ofrecer(
    *,
    espera_repo,
    turnos_repo,
    profesionales_repo,
    sillones_repo,
    pacientes_repo,
    notif_repo,
    tienda,
    cliente,
    hueco: dict,
    ahora: datetime | None = None,
) -> EsperaEntry | None:
    """Ofrece al primero compatible (FIFO) o no-op si no hay.

    `hueco = {profesional_id, sillon_id, inicio, fin, turno_id?}`; `turno_id`
    es el turno cancelado que liberó el hueco (trazabilidad del aviso).
    La entry pasa a `ofrecida` con `oferta_expira_en = ahora + 2 h`,
    `token_oferta_hash` y snapshot `oferta_hueco`, y se encola la
    notificación `oferta_lista_espera` vía C-06 (mock OK). No pre-chequea
    solapamiento (D-03): el EXCLUDE de DB arbitra al aceptar.
    """
    momento = ahora or datetime.now(timezone.utc)
    profesional_id = hueco["profesional_id"]
    inicio = hueco["inicio"]

    profesional = await profesionales_repo.get(profesional_id)
    if profesional is None:
        _log.warning("intentar_ofrecer: profesional %s inexistente", profesional_id)
        return None
    especialidades_profesional = getattr(profesional, "especialidades", "") or ""

    compatibles = await espera_repo.activas_compatibles(
        profesional_id=profesional_id,
        especialidades_profesional=especialidades_profesional,
        inicio=inicio,
    )
    if not compatibles:
        _log.info("intentar_ofrecer: sin compatibles para profesional %s", profesional_id)
        return None

    # D-03: la oferta NO bloquea el hueco ni lo pre-chequea; el EXCLUDE de DB
    # arbitra al aceptar (hueco tomado -> 409 + vencida 'hueco_tomado' + cascada).
    return await _ofrecer_a_entry(
        espera_repo, notif_repo, pacientes_repo, cliente, compatibles[0],
        hueco, momento,
    )


async def ofrecer_a_entry(
    *,
    espera_repo,
    notif_repo,
    pacientes_repo,
    cliente,
    entry_id: int,
    hueco: dict,
    ahora: datetime | None = None,
) -> EsperaEntry:
    """Oferta manual (staff): ofrece `hueco` a una entry `activa` puntual.

    Permite a secretaría saltear/adelantar la cola (design: riesgo cascada
    lenta). 404 si no existe; `OfertaYaActivaError` (409) si no está `activa`.
    """
    entry = await espera_repo.get(entry_id)
    if entry is None:
        raise EntradaNoEncontradaError(f"entrada {entry_id} inexistente")
    if entry.estado != "activa":
        raise OfertaYaActivaError("la entrada no está activa")
    momento = ahora or datetime.now(timezone.utc)
    return await _ofrecer_a_entry(
        espera_repo, notif_repo, pacientes_repo, cliente, entry, hueco, momento,
    )


async def _ofrecer_a_entry(
    espera_repo, notif_repo, pacientes_repo, cliente, entry: EsperaEntry,
    hueco: dict, momento: datetime,
) -> EsperaEntry:
    """Pasa la entry a `ofrecida` (2 h, hash, snapshot) y avisa por C-06."""
    token = generar_token()
    oferta_expira_en = momento + timedelta(hours=OFERTA_EXPIRA_HORAS)
    snapshot = {
        "profesional_id": hueco["profesional_id"],
        "sillon_id": hueco["sillon_id"],
        "inicio": hueco["inicio"].isoformat(),
        "fin": hueco["fin"].isoformat(),
    }
    if hueco.get("turno_id") is not None:
        snapshot["turno_id"] = hueco["turno_id"]
    await espera_repo.actualizar(
        entry,
        estado="ofrecida",
        oferta_expira_en=oferta_expira_en,
        token_oferta_hash=hash_token(token),
        oferta_hueco=snapshot,
        motivo_baja=None,
    )
    await _enviar_aviso_oferta(
        notif_repo, pacientes_repo, cliente, entry,
        turno_id=hueco.get("turno_id"), inicio=hueco["inicio"],
        token=token, expira_en=oferta_expira_en,
    )
    return entry


async def aceptar_por_token(
    *,
    espera_repo,
    turnos_repo,
    profesionales_repo,
    sillones_repo,
    pacientes_repo,
    notif_repo,
    tienda,
    cliente,
    token: str | None = None,
    token_hash: str | None = None,
    ahora: datetime | None = None,
):
    """Acepta oferta por token: crear_turno(origen=lista_espera) +
    cambiar_estado→confirmado + entry→convertida + encolar confirmacion.

    Se pasa `token` (público, se hashea) o `token_hash` (staff conversión,
    ya se tiene el hash). Desconocido → TokenDesconocidoError (404).
    Reusado → TokenUsadoError (410). Expirado → TokenExpiradoError (410)
    + entry vencida 'expirada' + cascada. Hueco tomado → HuecoOcupadoError +
    entry vencida 'hueco_tomado' + cascada. NUNCA sobre_turno=True.
    """
    momento = ahora or datetime.now(timezone.utc)
    if token_hash is None:
        if token is None:
            raise ValueError("se requiere token o token_hash")
        token_hash = hash_token(token)
    entry = await espera_repo.get_by_token_hash(token_hash)
    if entry is None:
        raise TokenDesconocidoError("token de oferta inexistente")
    if entry.estado != "ofrecida":
        raise TokenUsadoError("token ya consumido")  # convertida|vencida|activa

    # Se captura TODO lo que se necesita de la entry ANTES de crear el turno:
    # ante un rollback del servicio de agenda la instancia queda expirada y
    # leerla en async dispararía una carga perezosa (MissingGreenlet).
    paciente_id = entry.paciente_id
    oferta_hueco = dict(entry.oferta_hueco or {})
    profesional_entry = entry.profesional_id
    expira_en = entry.oferta_expira_en

    if expira_en is not None and momento >= expira_en:
        await _marcar_vencida_y_cascada(
            espera_repo, turnos_repo, profesionales_repo, sillones_repo,
            pacientes_repo, notif_repo, tienda, cliente, entry,
            oferta_hueco, profesional_entry, ahora=momento,
            motivo_baja="expirada",
        )
        raise TokenExpiradoError("token de oferta expirado")

    # Conversión en dos pasos (D-06): crear_turno + cambiar_estado
    inicio = _parse_iso(oferta_hueco.get("inicio"))
    fin = _parse_iso(oferta_hueco.get("fin"))
    if inicio is None or fin is None:
        raise ValueError("oferta_hueco incompleto")
    try:
        turno = await agenda.crear_turno(
            turnos_repo, pacientes_repo, profesionales_repo, sillones_repo,
            paciente_id=paciente_id,
            profesional_id=oferta_hueco.get("profesional_id", profesional_entry),
            sillon_id=oferta_hueco.get("sillon_id", 1),
            inicio=inicio, fin=fin,
            origen="lista_espera", sobre_turno=False,
            ahora=momento,
        )
        turno = await agenda.cambiar_estado(turnos_repo, turno.id, "confirmado")
    except agenda.HuecoOcupadoError as exc:
        await _marcar_vencida_y_cascada(
            espera_repo, turnos_repo, profesionales_repo, sillones_repo,
            pacientes_repo, notif_repo, tienda, cliente, entry,
            oferta_hueco, profesional_entry, ahora=momento,
            motivo_baja="hueco_tomado",
        )
        raise HuecoOcupadoError("hueco ocupado", alternativas=exc.alternativas) from exc
    except agenda.PasadoNoPermitidoError as exc:
        # El hueco ya empezó: la oferta no sirve más (sin cascada, mismo hueco).
        await espera_repo.actualizar(
            entry, estado="vencida", motivo_baja="hueco_pasado",
        )
        raise TokenExpiradoError("el hueco ofrecido ya pasó") from exc
    await espera_repo.actualizar(entry, estado="convertida", motivo_baja=None)
    await _encolar_confirmacion(
        notif_repo, tienda, cliente, pacientes_repo, turno, paciente_id,
    )
    return turno


async def rechazar_por_token(
    *,
    espera_repo,
    turnos_repo,
    profesionales_repo,
    sillones_repo,
    pacientes_repo,
    notif_repo,
    tienda,
    cliente,
    token_hash: str,
    ahora: datetime | None = None,
) -> bool:
    """Rechaza oferta por hash: entry→vencida 'rechazo_paciente' + cascada.

    Desconocido → TokenDesconocidoError (404); ya resuelta → TokenUsadoError
    (410), igual que aceptar. Devuelve True al rechazar.
    """
    momento = ahora or datetime.now(timezone.utc)
    entry = await espera_repo.get_by_token_hash(token_hash)
    if entry is None:
        raise TokenDesconocidoError("token de oferta inexistente")
    if entry.estado != "ofrecida":
        raise TokenUsadoError("oferta ya resuelta")
    await _marcar_vencida_y_cascada(
        espera_repo, turnos_repo, profesionales_repo, sillones_repo,
        pacientes_repo, notif_repo, tienda, cliente, entry,
        dict(entry.oferta_hueco or {}), entry.profesional_id, ahora=momento,
        motivo_baja="rechazo_paciente",
    )
    return True


async def expirar_y_cascada(
    *,
    espera_repo,
    turnos_repo,
    profesionales_repo,
    sillones_repo,
    pacientes_repo,
    notif_repo,
    tienda,
    cliente,
    entry: EsperaEntry,
    ahora: datetime,
) -> EsperaEntry | None:
    """Vence una oferta sin respuesta ('expirada') y encadena (worker, D-05)."""
    return await _marcar_vencida_y_cascada(
        espera_repo, turnos_repo, profesionales_repo, sillones_repo,
        pacientes_repo, notif_repo, tienda, cliente, entry,
        dict(entry.oferta_hueco or {}), entry.profesional_id, ahora=ahora,
        motivo_baja="expirada",
    )


async def _marcar_vencida_y_cascada(
    espera_repo, turnos_repo, profesionales_repo, sillones_repo,
    pacientes_repo, notif_repo, tienda, cliente, entry: EsperaEntry,
    oferta_hueco: dict, profesional_entry: int | None,
    ahora: datetime, motivo_baja: str,
) -> EsperaEntry | None:
    """Marca la entry vencida e intenta ofrecer el mismo hueco al siguiente."""
    await espera_repo.actualizar(entry, estado="vencida", motivo_baja=motivo_baja)
    inicio = _parse_iso(oferta_hueco.get("inicio"))
    fin = _parse_iso(oferta_hueco.get("fin"))
    if inicio is None or fin is None:
        return None
    return await intentar_ofrecer(
        espera_repo=espera_repo, turnos_repo=turnos_repo,
        profesionales_repo=profesionales_repo, sillones_repo=sillones_repo,
        pacientes_repo=pacientes_repo, notif_repo=notif_repo,
        tienda=tienda, cliente=cliente,
        hueco={
            "profesional_id": oferta_hueco.get("profesional_id", profesional_entry),
            "sillon_id": oferta_hueco.get("sillon_id", 1),
            "inicio": inicio, "fin": fin,
            "turno_id": oferta_hueco.get("turno_id"),
        },
        ahora=ahora,
    )


def _parse_iso(texto: str | None) -> datetime | None:
    if not texto:
        return None
    return datetime.fromisoformat(texto)


def nombre_pila(paciente) -> str:
    partes = str(getattr(paciente, "nombre", "") or "").split() if paciente else []
    return partes[0] if partes else "paciente"


async def _enviar_aviso_oferta(
    notif_repo: NotificacionRepository,
    pacientes_repo,
    cliente,
    entry: EsperaEntry,
    turno_id: int | None,
    inicio: datetime,
    token: str,
    expira_en: datetime,
) -> None:
    """Encola notificación oferta_lista_espera (sin PHI, best-effort).

    La fila cuelga del turno cancelado que liberó el hueco (`turno_id`, FK).
    Sin `turno_id` (oferta manual sin turno de origen) no hay dónde colgarla:
    la entry igual queda `ofrecida` y visible para convertir por teléfono.
    """
    from app.core.config import get_settings

    if turno_id is None:
        _log.info("oferta entry %s sin turno de origen: sin aviso", entry.id)
        return
    try:
        paciente = await pacientes_repo.get(entry.paciente_id)
    except Exception:  # noqa: BLE001 - el aviso es best-effort
        paciente = None
    fecha, hora = notif_svc.formatear_horario(inicio)
    variables = {
        "nombre_pila": nombre_pila(paciente),
        "fecha": fecha,
        "hora": hora,
        "expira_en": expira_en.astimezone(TZ_BA).strftime("%d/%m %H:%M"),
        "link_oferta": f"{get_settings().cors_origins[0]}/lista-espera/{token}",
    }
    try:
        payload = variables_para_payload("oferta_lista_espera", variables)
    except VariableNoDeclaradaError as exc:
        _log.warning("plantilla oferta_lista_espera sin variable: %s", exc)
        return
    # El link lleva un token opaco aleatorio (puede contener "fdi" o 8+ dígitos
    # por azar): se escanea el texto humano, no el link generado por el sistema.
    if not sin_phi(" ".join(str(v) for k, v in payload.items() if k != "link_oferta")):
        _log.warning("payload oferta_lista_espera bloqueado por sin-PHI")
        return

    # UNIQUE parcial (turno_id, plantilla) WHERE estado != 'fallida': en la
    # cascada el mismo turno cancelado ofrece a varios pacientes. La oferta
    # anterior ya está resuelta (vencida/rechazada): se libera su cupo.
    previa = await notif_repo.activa_de_turno(turno_id, "oferta_lista_espera")
    if previa is not None:
        await notif_repo.actualizar(
            previa, estado="fallida", ultimo_error="oferta_superada",
        )

    telefono = notif_svc.telefono_valido(getattr(paciente, "telefono", None))
    email = getattr(paciente, "email", None) if paciente else None
    if telefono is None and not email:
        await notif_repo.crear(
            turno_id=turno_id, canal="whatsapp",
            plantilla="oferta_lista_espera", estado="fallida",
            payload=payload, ultimo_error="sin_numero_valido",
        )
        return
    fila = await notif_repo.crear(
        turno_id=turno_id, canal="whatsapp", plantilla="oferta_lista_espera",
        destinatario_ref=telefono or email, payload=payload,
    )
    try:
        await notif_svc.enviar_con_reintentos(notif_repo, fila, cliente, email=email)
    except Exception as exc:  # noqa: BLE001 - queda encolada, tick lo reintenta
        _log.warning(
            "aviso oferta entry %s queda encolado: %s", entry.id, type(exc).__name__
        )


async def _encolar_confirmacion(
    notif_repo, tienda, cliente, pacientes_repo, turno, paciente_id: int,
) -> None:
    """Encola plantilla confirmacion tras conversión (efecto aditivo C-06)."""
    try:
        paciente = await pacientes_repo.get(paciente_id)
    except Exception:  # noqa: BLE001
        paciente = None
    await notif_svc.encolar_confirmacion(
        notif_repo, tienda, turno, nombre_pila=nombre_pila(paciente),
        cliente=cliente,
        email=getattr(paciente, "email", None) if paciente else None,
    )


__all__ = [
    "EntradaNoEncontradaError",
    "HuecoOcupadoError",
    "OFERTA_EXPIRA_HORAS",
    "OfertaYaActivaError",
    "TokenDesconocidoError",
    "TokenExpiradoError",
    "TokenUsadoError",
    "aceptar_por_token",
    "expirar_y_cascada",
    "intentar_ofrecer",
    "ofrecer_a_entry",
    "rechazar_por_token",
]
