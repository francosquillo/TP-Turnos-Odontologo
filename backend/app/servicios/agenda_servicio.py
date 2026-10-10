"""Servicio agenda: huecos, creacion, estados y reprogramacion (C-04).

Huecos = horario semanal de `agenda_config` − turnos activos no-sobreturno
(D-04, formato canonico C-02: {duracion_slot_min, horario: {dia: [[ini,fin]]}}).
La DB (EXCLUDE, D-01) es la autoridad final ante carreras: el pre-chequeo da
409 con re-oferta y el IntegrityError residual solo se mapea a 409 si es
violacion EXCLUDE (solapamiento real); FK rota -> 422, resto propaga.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = "America/Argentina/Buenos_Aires"
ESTADOS_ACTIVOS = ("pendiente", "confirmado", "asistido")
ESTADOS_TERMINALES = ("asistido", "ausente", "cancelado")
TRANSICIONES: dict[str, set[str]] = {
    "pendiente": {"confirmado", "cancelado"},
    "confirmado": {"asistido", "ausente", "cancelado"},
    "asistido": set(),
    "ausente": set(),
    "cancelado": set(),
}
_DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")


class HuecoOcupadoError(Exception):
    """Solapamiento sin sobreturno valido (se mapea a 409 con alternativas)."""

    def __init__(self, mensaje: str = "hueco ocupado", alternativas: list | None = None) -> None:
        super().__init__(mensaje)
        self.alternativas: list[tuple[datetime, datetime]] = alternativas or []


class EntidadNoEncontradaError(LookupError):
    """FK inexistente (se mapea a 422)."""


class TransicionInvalidaError(ValueError):
    """Transicion fuera de la maquina (se mapea a 422)."""


class MotivoRequeridoError(ValueError):
    """Cancelar/sobreturno sin motivo suficiente (se mapea a 422)."""


class PasadoNoPermitidoError(ValueError):
    """Crear en pasado sin rol admin (se mapea a 422)."""


def _a_hora(texto: str) -> tuple[int, int]:
    hora, minuto = texto.split(":")
    return int(hora), int(minuto)


def calcular_huecos(
    agenda_config: dict | None,
    desde: datetime,
    hasta: datetime,
    ocupados: list[tuple[datetime, datetime]],
    duracion_min: int | None = None,
    tz_nombre: str = TZ,
) -> list[tuple[datetime, datetime]]:
    """Slots libres en [desde, hasta) como (inicio, fin) tz-aware.

    Sin config valida o dia fuera de horario -> []. Puro y testeable sin DB.
    """
    try:
        from app.esquemas.profesional import AgendaConfig

        config = AgendaConfig.model_validate(agenda_config or {})
    except Exception:
        return []
    zona = ZoneInfo(tz_nombre)
    paso = timedelta(minutes=duracion_min or config.duracion_slot_min)
    if paso <= timedelta(0):
        return []
    dia: date = desde.astimezone(zona).date()
    ultimo: date = hasta.astimezone(zona).date()
    huecos: list[tuple[datetime, datetime]] = []
    while dia <= ultimo:
        nombre_dia = _DIAS[dia.weekday()]
        for ini_txt, fin_txt in config.horario.get(nombre_dia, []):
            h_ini, m_ini = _a_hora(ini_txt)
            h_fin, m_fin = _a_hora(fin_txt)
            cursor = datetime(dia.year, dia.month, dia.day, h_ini, m_ini, tzinfo=zona)
            cierre = datetime(dia.year, dia.month, dia.day, h_fin, m_fin, tzinfo=zona)
            while cursor + paso <= cierre:
                slot = (cursor, cursor + paso)
                if slot[0] >= desde.astimezone(zona) and slot[1] <= hasta.astimezone(zona):
                    if not any(
                        slot[0] < oc_fin and slot[1] > oc_ini for oc_ini, oc_fin in ocupados
                    ):
                        huecos.append(slot)
                cursor += paso
        dia += timedelta(days=1)
    return huecos


def rango_vista(vista: str, fecha: date, tz_nombre: str = TZ) -> tuple[datetime, datetime]:
    """Rango [desde, hasta) de la vista dia|semana|mes en la TZ dada."""
    zona = ZoneInfo(tz_nombre)
    if vista == "dia":
        desde = datetime(fecha.year, fecha.month, fecha.day, tzinfo=zona)
        return desde, desde + timedelta(days=1)
    if vista == "semana":
        lunes = fecha - timedelta(days=fecha.weekday())
        desde = datetime(lunes.year, lunes.month, lunes.day, tzinfo=zona)
        return desde, desde + timedelta(days=7)
    if vista == "mes":
        desde = datetime(fecha.year, fecha.month, 1, tzinfo=zona)
        if fecha.month == 12:
            hasta = datetime(fecha.year + 1, 1, 1, tzinfo=zona)
        else:
            hasta = datetime(fecha.year, fecha.month + 1, 1, tzinfo=zona)
        return desde, hasta
    raise ValueError(f"vista {vista} invalida (dia|semana|mes)")


async def sugerir_alternativas(
    turnos_repo, profesional, sillon_id: int | None, inicio_deseado: datetime,
    duracion: timedelta, cantidad: int = 3,
) -> list[tuple[datetime, datetime]]:
    """Proximos huecos del profesional (Flujo 1: re-oferta ante 409)."""
    config = getattr(profesional, "agenda_config", None) or {}
    try:
        ocupados_raw = await turnos_repo.activos_en_rango(
            inicio_deseado,
            inicio_deseado + timedelta(days=7),
            profesional_id=getattr(profesional, "id", None),
            sillon_id=sillon_id,
        )
    except Exception:
        return []
    ocupados = [(t.inicio, t.fin) for t in ocupados_raw]
    minutos = max(int(duracion.total_seconds() // 60), 1)
    huecos = calcular_huecos(config, inicio_deseado, inicio_deseado + timedelta(days=7), ocupados, minutos)
    return [h for h in huecos if h[0] >= inicio_deseado][:cantidad]


def _validar_sobreturno(sobre_turno: bool, motivo: str | None) -> None:
    if sobre_turno and (motivo is None or len(motivo.strip()) < 5):
        raise MotivoRequeridoError("el sobreturno exige motivo (≥ 5 caracteres)")


async def _alternativas_ante_conflicto(
    turnos_repo, profesionales_repo, profesional_id: int, sillon_id: int,
    inicio: datetime, fin: datetime,
) -> list[tuple[datetime, datetime]]:
    try:
        profesional = await profesionales_repo.get(profesional_id)
        if profesional is None:
            return []
        return await sugerir_alternativas(
            turnos_repo, profesional, sillon_id, inicio, fin - inicio
        )
    except Exception:
        return []


def _codigo_integridad(exc: Exception) -> str | None:
    """pgcode/sqlstate del error DB (23P01 exclude, 23503 fk, ...)."""
    orig = getattr(exc, "orig", None)
    for fuente in (orig, exc):
        for atributo in ("pgcode", "sqlstate"):
            codigo = getattr(fuente, atributo, None)
            if isinstance(codigo, str) and codigo:
                return codigo
    return None


def _texto_integridad(exc: Exception) -> str:
    partes = [str(exc)]
    orig = getattr(exc, "orig", None)
    if orig is not None:
        partes.append(str(orig))
    causa = getattr(exc, "__cause__", None)
    if causa is not None:
        partes.append(str(causa))
    return " ".join(partes).lower()


def _es_violacion_exclude(exc: Exception) -> bool:
    """True solo si la DB rechazo por EXCLUDE (solapamiento real, D-01)."""
    if _codigo_integridad(exc) == "23P01":
        return True
    texto = _texto_integridad(exc)
    return "exclusion constraint" in texto or "ex_turno_" in texto


def _es_violacion_fk(exc: Exception) -> bool:
    """True si la DB rechazo por FK rota (p. ej. creado_por fantasma)."""
    if _codigo_integridad(exc) == "23503":
        return True
    return "foreign key" in _texto_integridad(exc)


def _nombre_constraint(exc: Exception) -> str | None:
    import re

    coincidencia = re.search(r'constraint "([^"]+)"', _texto_integridad(exc))
    return coincidencia.group(1) if coincidencia else None


async def _rollback_silencioso(turnos_repo) -> None:
    rollback = getattr(getattr(turnos_repo, "sesion", None), "rollback", None)
    if callable(rollback):
        try:
            await rollback()
        except Exception:
            pass


async def crear_turno(
    turnos_repo,
    pacientes_repo,
    profesionales_repo,
    sillones_repo,
    *,
    paciente_id: int,
    profesional_id: int,
    sillon_id: int,
    inicio: datetime,
    fin: datetime,
    origen: str = "secretaria",
    sobre_turno: bool = False,
    motivo_sobreturno: str | None = None,
    creado_por: int | None = None,
    es_admin: bool = False,
    ahora: datetime | None = None,
):
    """Crea un turno validando FKs, fin>inicio, pasado y solapamiento (D-02)."""
    from sqlalchemy.exc import DBAPIError, IntegrityError

    if fin <= inicio:
        raise ValueError("fin debe ser > inicio")
    for repo, nombre, ref_id in (
        (pacientes_repo, "paciente", paciente_id),
        (profesionales_repo, "profesional", profesional_id),
        (sillones_repo, "sillon", sillon_id),
    ):
        if await repo.get(ref_id) is None:
            raise EntidadNoEncontradaError(f"{nombre} inexistente")
    momento = ahora or datetime.now(timezone.utc)
    if inicio < momento and not es_admin:
        raise PasadoNoPermitidoError("solo admin puede crear turnos en pasado")
    _validar_sobreturno(sobre_turno, motivo_sobreturno)
    if await turnos_repo.hay_solapamiento(profesional_id, sillon_id, inicio, fin):
        if not sobre_turno:
            alternativas = await _alternativas_ante_conflicto(
                turnos_repo, profesionales_repo, profesional_id, sillon_id, inicio, fin
            )
            raise HuecoOcupadoError("hueco ocupado", alternativas=alternativas)
    estado_inicial = "confirmado" if origen == "secretaria" else "pendiente"
    try:
        return await turnos_repo.crear(
            paciente_id=paciente_id,
            profesional_id=profesional_id,
            sillon_id=sillon_id,
            inicio=inicio,
            fin=fin,
            estado=estado_inicial,
            origen=origen,
            sobre_turno=sobre_turno,
            motivo_sobreturno=motivo_sobreturno if sobre_turno else None,
            motivo_cancelacion=None,
            creado_por=creado_por,
            token_confirmacion_hash=None,
        )
    except (IntegrityError, DBAPIError) as exc:
        await _rollback_silencioso(turnos_repo)
        if _es_violacion_exclude(exc):
            # Carrera: el pre-chequeo paso pero la DB (EXCLUDE, D-01) decidio.
            alternativas = await _alternativas_ante_conflicto(
                turnos_repo, profesionales_repo, profesional_id, sillon_id, inicio, fin
            )
            raise HuecoOcupadoError("hueco ocupado", alternativas=alternativas) from exc
        if _es_violacion_fk(exc):
            # FK rota (p. ej. creado_por fantasma): 422, nunca 409.
            nombre = _nombre_constraint(exc)
            detalle = (
                f"referencia inexistente ({nombre})"
                if nombre
                else "referencia inexistente"
            )
            raise EntidadNoEncontradaError(detalle) from exc
        raise


async def cambiar_estado(
    turnos_repo, turno_id: int, nuevo_estado: str, *,
    motivo: str | None = None, es_admin: bool = False,
):
    """Avanza la maquina D-03 (cancelar exige motivo; terminales bloqueados)."""
    turno = await turnos_repo.get(turno_id)
    if turno is None:
        raise EntidadNoEncontradaError(f"turno {turno_id} inexistente")
    actual = turno.estado
    if nuevo_estado == actual:
        return turno
    permitidos = set(TRANSICIONES.get(actual, set()))
    if actual == "pendiente" and nuevo_estado == "asistido" and es_admin:
        permitidos = permitidos | {"asistido"}  # carga historica por admin
    if nuevo_estado not in permitidos:
        raise TransicionInvalidaError(f"transicion {actual} -> {nuevo_estado} invalida")
    if nuevo_estado == "cancelado" and (motivo is None or not motivo.strip()):
        raise MotivoRequeridoError("cancelar exige motivo")
    cambios: dict = {"estado": nuevo_estado}
    if nuevo_estado == "cancelado":
        cambios["motivo_cancelacion"] = (motivo or "").strip()
    return await turnos_repo.actualizar(turno, **cambios)


async def reprogramar(
    turnos_repo,
    profesionales_repo,
    turno_id: int,
    *,
    nuevo_inicio: datetime,
    nuevo_fin: datetime,
    sobre_turno: bool = False,
    motivo_sobreturno: str | None = None,
):
    """Mueve un turno revalidando como creacion (D-06, excluye el propio id)."""
    from sqlalchemy.exc import DBAPIError, IntegrityError

    turno = await turnos_repo.get(turno_id)
    if turno is None:
        raise EntidadNoEncontradaError(f"turno {turno_id} inexistente")
    if nuevo_fin <= nuevo_inicio:
        raise ValueError("fin debe ser > inicio")
    _validar_sobreturno(sobre_turno, motivo_sobreturno)
    if await turnos_repo.hay_solapamiento(
        turno.profesional_id, turno.sillon_id, nuevo_inicio, nuevo_fin,
        excluir_id=turno.id,
    ):
        if not sobre_turno:
            alternativas = await _alternativas_ante_conflicto(
                turnos_repo, profesionales_repo, turno.profesional_id,
                turno.sillon_id, nuevo_inicio, nuevo_fin,
            )
            raise HuecoOcupadoError("hueco ocupado", alternativas=alternativas)
    try:
        return await turnos_repo.actualizar(
            turno,
            inicio=nuevo_inicio,
            fin=nuevo_fin,
            sobre_turno=sobre_turno,
            motivo_sobreturno=motivo_sobreturno if sobre_turno else turno.motivo_sobreturno,
        )
    except (IntegrityError, DBAPIError) as exc:
        await _rollback_silencioso(turnos_repo)
        if _es_violacion_exclude(exc):
            alternativas = await _alternativas_ante_conflicto(
                turnos_repo, profesionales_repo, turno.profesional_id,
                turno.sillon_id, nuevo_inicio, nuevo_fin,
            )
            raise HuecoOcupadoError("hueco ocupado", alternativas=alternativas) from exc
        if _es_violacion_fk(exc):
            nombre = _nombre_constraint(exc)
            detalle = (
                f"referencia inexistente ({nombre})"
                if nombre
                else "referencia inexistente"
            )
            raise EntidadNoEncontradaError(detalle) from exc
        raise
