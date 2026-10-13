"""Servicio notificaciones: barrido 48/24 h, reintentos y fallback (C-06, D-03).

- `barrido_recordatorios` (RN-NO-01): cada hora busca turnos
  `pendiente|confirmado` con `inicio` en `[48h±30min]/[24h±30min]` (TZ
  America/Argentina/Buenos_Aires); por candidato reserva la clave Redis
  `notif:{turno_id}:{tipo}` con `SET NX EX 49h` (primera barrera) y crea la
  fila `encolada` (el UNIQUE parcial D-01 es la segunda). Sin numero valido
  ni email -> `fallida 'sin_numero_valido'` sin encolar (D-06).
- Reprogramacion (resolucion humana 2026-10-13 P1): si la fila activa guarda
  otra hora que el turno actual, la anterior se marca `fallida
  'reprogramado'` (libera el UNIQUE) y se encola la nueva.
- Redis caido (D-04): degrada a filas `encolada` sin enviar; el proximo tick
  (`reintentar_fallidas`) las envia sin duplicar.
- `enviar_con_reintentos` (RN-NO-02/03): 3 intentos registrando
  `intentos + ultimo_error` (sin PHI); tras el 3er fallo, fallback `email`
  (si hay) o `sms` stub en la MISMA fila (muta `canal`, `via_fallback:true`,
  costo 0); sin canal posible marca `fallida`. Costo: 0 mock/stub, 0.026 real.
- `encolar_confirmacion`: efecto lateral aditivo del SI por webhook y del
  `GET /confirmar/:token` (tasks 5.2/6.1); idempotente por clave + UNIQUE.
"""
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.seed_plantillas import (
    VariableNoDeclaradaError,
    sin_phi,
    variables_para_payload,
)
from app.servicios.reserva_servicio import CONTACTO_CONSULTORIO
from app.servicios.whatsapp_cliente import (
    ResultadoEnvio,
    enmascarar_ref,
)

MAX_INTENTOS = 3
MAX_REINTENTOS_FALLIDA = 6  # dos rondas de 3 antes de rendirse del todo
VENTANA_MIN = 30
TTL_CLAVE_SEG = 49 * 3600
TZ = "America/Argentina/Buenos_Aires"
TIPOS = (("recordatorio_48h", 48), ("recordatorio_24h", 24))
# Fallidas que NUNCA se reintentan (permanentes, D-06).
ERRORES_PERMANENTES = (
    "sin_numero_valido", "sin_canal", "reprogramado", "contenido_bloqueado",
)

_log = logging.getLogger(__name__)


def telefono_valido(ref: str | None) -> str | None:
    """Digitos normalizados si tiene 8+ (misma regla que C-05 D-05)."""
    digitos = "".join(c for c in str(ref or "") if c.isdigit())
    return digitos if len(digitos) >= 8 else None


def formatear_horario(inicio: datetime) -> tuple[str, str]:
    """(fecha DD/MM, hora HH:MM) del turno en TZ BA para las plantillas."""
    local = inicio.astimezone(ZoneInfo(TZ))
    return local.strftime("%d/%m"), local.strftime("%H:%M")


def _error_limpio(exc: Exception) -> str:
    """Ultimo error sin PHI: tipo + mensaje truncado (nunca cuerpo ni numero)."""
    texto = f"{type(exc).__name__}: {exc}".strip()
    return texto[:200] if texto else type(exc).__name__


async def _reservar_clave(tienda, clave: str) -> bool | None:
    """True=reservada (proceder), False=ya existe (skip), None=Redis caido."""
    try:
        try:
            tomada = await tienda.set(clave, "1", ex=TTL_CLAVE_SEG, nx=True)
        except TypeError:
            # Tiendas sin NX (FakeStore C-03): emula con get+set.
            if await tienda.get(clave) is not None:
                return False
            await tienda.set(clave, "1", ex=TTL_CLAVE_SEG)
            return True
        return bool(tomada)  # redis real: True | None
    except Exception as exc:  # noqa: BLE001 - Redis caido degrada (D-04)
        _log.warning("redis no disponible, degrada a encolada: %s", type(exc).__name__)
        return None


async def enviar_con_reintentos(
    notif_repo,
    notificacion,
    cliente,
    email: str | None = None,
    max_intentos: int = MAX_INTENTOS,
) -> ResultadoEnvio:
    """Envia por WhatsApp con reintentos + fallback stub (RN-NO-03)."""
    from app.servicios.whatsapp_cliente import EmailStubCliente, SmsStubCliente

    payload = dict(getattr(notificacion, "payload", {}) or {})
    destinatario = getattr(notificacion, "destinatario_ref", None)
    ultimo_error = ""
    for _ in range(max_intentos):
        try:
            resultado = await cliente.enviar(
                destinatario, notificacion.plantilla, payload
            )
        except Exception as exc:  # noqa: BLE001 - todo fallo cuenta intento
            ultimo_error = _error_limpio(exc)
            await notif_repo.actualizar(
                notificacion,
                intentos=notificacion.intentos + 1,
                ultimo_error=ultimo_error,
            )
            _log.warning(
                "notif %s intento %s fallo a %s: %s",
                getattr(notificacion, "id", "?"),
                notificacion.intentos,
                enmascarar_ref(destinatario),
                ultimo_error,
            )
            continue
        payload_con_id = dict(payload)
        if resultado.message_id:
            payload_con_id["message_id"] = resultado.message_id
        await notif_repo.actualizar(
            notificacion,
            estado="enviada",
            costo=resultado.costo,
            intentos=notificacion.intentos + 1,
            payload=payload_con_id,
            ultimo_error=None,
        )
        return resultado
    # 3 fallos: fallback en la misma fila (D-05) o fallida sin canal.
    # El fallback tambien puede fallar (stub roto): nunca propaga, la fila
    # queda fallida con traza (el worker no debe caerse por un envio).
    try:
        if email:
            stub = EmailStubCliente()
            resultado = await stub.enviar(email, notificacion.plantilla, payload)
            await notif_repo.actualizar(
                notificacion,
                canal="email",
                destinatario_ref=email,
                estado="enviada",
                costo=0.0,
                payload={**payload, "via_fallback": True,
                         "message_id": resultado.message_id},
            )
            _log.info(
                "notif %s fallback email a %s",
                getattr(notificacion, "id", "?"), enmascarar_ref(email),
            )
            return resultado
        if telefono_valido(destinatario):
            stub = SmsStubCliente()
            resultado = await stub.enviar(
                destinatario, notificacion.plantilla, payload
            )
            await notif_repo.actualizar(
                notificacion,
                canal="sms",
                estado="enviada",
                costo=0.0,
                payload={**payload, "via_fallback": True,
                         "message_id": resultado.message_id},
            )
            _log.info(
                "notif %s fallback sms a %s",
                getattr(notificacion, "id", "?"), enmascarar_ref(destinatario),
            )
            return resultado
    except Exception as exc:  # noqa: BLE001 - fallback roto -> fallida trazada
        ultimo_error = f"{ultimo_error} | fallback: {_error_limpio(exc)}"
    await notif_repo.actualizar(
        notificacion,
        estado="fallida",
        ultimo_error=f"sin_canal: fallida tras {max_intentos} intentos: {ultimo_error}",
    )
    return ResultadoEnvio(estado="fallida", costo=0.0)


def _clave(tipo: str, turno_id: int) -> str:
    return f"notif:{turno_id}:{tipo}"


def _misma_hora(payload: dict, inicio: datetime) -> bool:
    fecha, hora = formatear_horario(inicio)
    return payload.get("fecha") == fecha and payload.get("hora") == hora


async def _variables_turno(pacientes_repo, turno, consultorio_tel: str):
    paciente = await pacientes_repo.get(turno.paciente_id)
    nombre_pila = str(getattr(paciente, "nombre", "") or "").split()[0] or "paciente"
    fecha, hora = formatear_horario(turno.inicio)
    variables = {
        "nombre_pila": nombre_pila, "fecha": fecha, "hora": hora,
        "consultorio_tel": consultorio_tel,
    }
    email = getattr(paciente, "email", None) if paciente is not None else None
    telefono = telefono_valido(getattr(paciente, "telefono", None))
    return variables, telefono, email


async def barrido_recordatorios(
    turnos_repo,
    notif_repo,
    pacientes_repo,
    tienda,
    cliente,
    ahora: datetime | None = None,
    consultorio_tel: str = CONTACTO_CONSULTORIO,
    ventana_min: int = VENTANA_MIN,
) -> dict[str, int]:
    """Barre ventanas 48/24 h y encola+envia idempotente (RN-NO-01)."""
    from sqlalchemy.exc import IntegrityError

    momento = ahora or datetime.now(timezone.utc)
    stats = {"encoladas": 0, "skips": 0, "fallidas": 0, "degradadas": 0,
             "reprogramadas": 0}
    for tipo, horas in TIPOS:
        desde = momento + timedelta(hours=horas, minutes=-ventana_min)
        hasta = momento + timedelta(hours=horas, minutes=ventana_min)
        candidatos = await turnos_repo.por_estado_y_rango(
            ("pendiente", "confirmado"), desde, hasta
        )
        for turno in candidatos:
            # La fila activa manda sobre la clave Redis: asi la reprogramacion
            # (misma clave, otra hora) se detecta aunque la clave siga viva.
            existente = await notif_repo.activa_de_turno(turno.id, tipo)
            if existente is not None and _misma_hora(
                existente.payload or {}, turno.inicio
            ):
                stats["skips"] += 1
                continue
            reprogramado = existente is not None
            reserva = await _reservar_clave(tienda, _clave(tipo, turno.id))
            if reserva is False and not reprogramado:
                stats["skips"] += 1
                continue
            if reprogramado:
                # Reprogramacion (P1): libera el UNIQUE y reenvia nueva hora;
                # la clave se pisa (formato notif:{turno}:{tipo} intacto).
                assert existente is not None
                await notif_repo.actualizar(
                    existente, estado="fallida",
                    ultimo_error="reprogramado: se reenvia con la nueva hora",
                )
                try:
                    await tienda.set(
                        _clave(tipo, turno.id), "1", ex=TTL_CLAVE_SEG
                    )
                except Exception:  # noqa: BLE001 - Redis caido, sigue igual
                    reserva = None
                stats["reprogramadas"] += 1
            variables, telefono, email = await _variables_turno(
                pacientes_repo, turno, consultorio_tel
            )
            if telefono is None and not email:
                if await notif_repo.fallida_de_turno(turno.id, tipo) is None:
                    await notif_repo.crear(
                        turno_id=turno.id, canal="whatsapp", plantilla=tipo,
                        estado="fallida", payload={**variables, "job_key": _clave(tipo, turno.id)},
                        ultimo_error="sin_numero_valido",
                    )
                    stats["fallidas"] += 1
                    _log.info(
                        "notif turno %s sin numero valido (fallida, aviso staff)",
                        turno.id,
                    )
                else:
                    stats["skips"] += 1
                try:
                    await tienda.delete(_clave(tipo, turno.id))
                except Exception:  # noqa: BLE001 - Redis caido, la TTL limpia
                    pass
                continue
            try:
                payload = {**variables_para_payload(tipo, variables),
                           "job_key": _clave(tipo, turno.id)}
            except VariableNoDeclaradaError as exc:
                await notif_repo.crear(
                    turno_id=turno.id, canal="whatsapp", plantilla=tipo,
                    estado="fallida", payload={**variables, "job_key": _clave(tipo, turno.id)},
                    ultimo_error=_error_limpio(exc),
                )
                stats["fallidas"] += 1
                continue
            if not sin_phi(" ".join(str(v) for v in payload.values())):
                await notif_repo.crear(
                    turno_id=turno.id, canal="whatsapp", plantilla=tipo,
                    estado="fallida", payload={"job_key": _clave(tipo, turno.id)},
                    ultimo_error="contenido_bloqueado_sin_phi",
                )
                stats["fallidas"] += 1
                continue
            try:
                fila = await notif_repo.crear(
                    turno_id=turno.id, canal="whatsapp", plantilla=tipo,
                    destinatario_ref=telefono or email, payload=payload,
                )
            except IntegrityError:
                # Carrera: otro tick gano (UNIQUE D-01 decide).
                stats["skips"] += 1
                continue
            stats["encoladas"] += 1
            if reserva is None:
                # D-04: Redis caido -> queda encolada, proximo tick la envia.
                stats["degradadas"] += 1
                continue
            await enviar_con_reintentos(notif_repo, fila, cliente, email=email)
            if fila.estado == "fallida":
                # El envio (y el fallback) fallaron: cuenta como fallida
                # ademas de encolada (la fila existe, quedo fallida).
                stats["fallidas"] += 1
    return stats


async def encolar_confirmacion(
    notif_repo,
    tienda,
    turno,
    nombre_pila: str,
    consultorio_tel: str = CONTACTO_CONSULTORIO,
    cliente=None,
    email: str | None = None,
):
    """Encola la plantilla confirmacion (idempotente; efecto aditivo 5.2/6.1)."""
    from sqlalchemy.exc import IntegrityError

    clave = _clave("confirmacion", turno.id)
    if await _reservar_clave(tienda, clave) is False:
        return None
    if await notif_repo.activa_de_turno(turno.id, "confirmacion") is not None:
        return None
    fecha, hora = formatear_horario(turno.inicio)
    variables = {"nombre_pila": nombre_pila, "fecha": fecha, "hora": hora,
                 "consultorio_tel": consultorio_tel}
    try:
        payload = {**variables_para_payload("confirmacion", variables),
                   "job_key": clave}
    except VariableNoDeclaradaError:
        return None
    try:
        fila = await notif_repo.crear(
            turno_id=turno.id, canal="whatsapp", plantilla="confirmacion",
            destinatario_ref=None, payload=payload,
        )
    except IntegrityError:
        return None
    if cliente is not None:
        try:
            await enviar_con_reintentos(notif_repo, fila, cliente, email=email)
        except Exception as exc:  # noqa: BLE001 - queda encolada, tick la envia
            _log.warning("confirmacion turno %s queda encolada: %s",
                         turno.id, type(exc).__name__)
    return fila


async def reintentar_fallidas(
    notif_repo,
    turnos_repo,
    pacientes_repo,
    tienda,
    cliente,
    ahora: datetime | None = None,  # noqa: ARG001 - reserva para backoff real
    limit: int = 100,
) -> dict[str, int]:
    """Reintenta encoladas degradadas + fallidas transitorias (D-04)."""
    stats = {"enviadas": 0, "skips": 0}
    pendientes = list(await notif_repo.encoladas(limit=limit))
    for fila in pendientes:
        turno = await turnos_repo.get(fila.turno_id)
        if turno is None or turno.estado not in ("pendiente", "confirmado"):
            stats["skips"] += 1
            continue
        paciente = await pacientes_repo.get(turno.paciente_id)
        email = getattr(paciente, "email", None) if paciente else None
        await enviar_con_reintentos(notif_repo, fila, cliente, email=email)
        stats["enviadas"] += 1
    for fila in await notif_repo.fallidas(limit=limit):
        if fila.intentos >= MAX_REINTENTOS_FALLIDA:
            stats["skips"] += 1
            continue
        if any(m in (fila.ultimo_error or "") for m in ERRORES_PERMANENTES):
            stats["skips"] += 1
            continue
        turno = await turnos_repo.get(fila.turno_id)
        if turno is None or turno.estado not in ("pendiente", "confirmado"):
            stats["skips"] += 1
            continue
        await notif_repo.actualizar(fila, estado="encolada", ultimo_error=None)
        paciente = await pacientes_repo.get(turno.paciente_id)
        email = getattr(paciente, "email", None) if paciente else None
        await enviar_con_reintentos(notif_repo, fila, cliente, email=email)
        stats["enviadas"] += 1
    return stats


__all__ = [
    "ERRORES_PERMANENTES",
    "MAX_INTENTOS",
    "MAX_REINTENTOS_FALLIDA",
    "barrido_recordatorios",
    "encolar_confirmacion",
    "enviar_con_reintentos",
    "formatear_horario",
    "reintentar_fallidas",
    "telefono_valido",
]
