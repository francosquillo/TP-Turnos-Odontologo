"""Datos demo ricos del seed: turnos, clinica y cobros/caja (100 % ficticios, idempotentes).

Se invoca desde `app.db.seed.run_seed`. Todo cuelga de pacientes con DNI de prueba 9000xxxx.
Usa la capa de servicios (agenda, clinica, presupuestos, caja) para respetar las invariantes:
sin solapamiento, hallazgo en cada item de presupuesto, recibos sin huecos, anulacion por
contramovimiento y cajas cerradas dia a dia. No crea notificaciones.

Claves naturales (re-ejecutar no duplica ni falla):
- turno: (paciente, profesional, inicio). La grilla de cada dia sale de un RNG sembrado con la
  fecha, asi un dia ya generado se regenera igual y solo entran los dias nuevos del horizonte.
  Si un hueco ya esta ocupado por otro turno (p. ej. uno real) se omite, nunca falla.
- historia clinica: una por paciente (UNIQUE). Si existe, ese paciente se omite entero
  (hallazgos, presupuestos y cobros), por lo que un paciente ya sembrado no se toca.
- cobro: clave de idempotencia determinista por (paciente, orden); cajas: una por fecha.
  Un dia que ya tiene caja no se usa, y si hay una caja anterior abierta o la de hoy esta
  cerrada, el bloque de cobros se omite.
"""
import hashlib
import random
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.esquemas.caja import CierreIn, CobroIn
from app.esquemas.presupuesto import ItemIn
from app.modelos import EstadoHallazgoCatalogo, Paciente, Profesional, Sillon, Tratamiento, Turno, Usuario
from app.modelos.hallazgo_odontograma import CATALOGO_ESTADOS_V1, CATALOGO_VERSION_V1
from app.repos.paciente_repo import PacienteRepository
from app.repos.profesional_repo import ProfesionalRepository
from app.repos.sillon_repo import SillonRepository
from app.repos.turno_repo import TurnoRepository
from app.servicios import agenda_servicio, caja_servicio, clinica_servicio, presupuesto_servicio
from app.servicios.caja_servicio import CajaRepos
from app.servicios.clinica_servicio import Actor, ConflictoError

DIAS_PASADO = 21
DIAS_FUTURO = 14
_DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
_ACTIVOS = ("pendiente", "confirmado", "asistido")

CANDIDATOS_CLINICOS = 14
DIAS_CAJA = 10
MEDIOS_DEMO = ("efectivo", "transferencia", "tarjeta_simulada", "efectivo")

# (pieza FDI, cara, estado): 4 consecutivas siempre incluyen algo tratable (caries/corona/endodoncia).
HALLAZGOS_DEMO = (
    (16, "oclusal", "caries"), (26, "mesial", "caries"), (36, "oclusal", "obturacion"),
    (21, "pieza_completa", "corona"), (46, "distal", "caries"), (24, "pieza_completa", "endodoncia"),
    (48, "pieza_completa", "ausente"), (11, "vestibular", "caries"), (37, "pieza_completa", "implante"),
    (45, "lingual", "caries"), (14, "oclusal", "sano"), (25, "palatina", "caries"),
)
# estado del hallazgo -> codigo del tratamiento del catalogo demo que lo resuelve.
TRATAMIENTO_POR_ESTADO = {"caries": "OBT-001", "corona": "COR-001", "endodoncia": "END-001"}
ANTECEDENTES_DEMO = (
    "Sin antecedentes relevantes (dato ficticio).", "Hipertension controlada (dato ficticio).",
    "Bruxismo nocturno (dato ficticio).", "Tratamiento de ortodoncia previo (dato ficticio).",
)
ALERGIAS_DEMO = ("Ninguna conocida", "Penicilina", "Latex", "Ninguna conocida")


def _clave_cobro(dni: str, orden: int) -> str:
    """UUID v4 determinista (formato exigido por `ck_recibo_clave_formato`)."""
    digest = hashlib.md5(f"seed-demo-cobro-{dni}-{orden}".encode()).digest()
    return str(uuid.UUID(bytes=digest, version=4))


# --- turnos --------------------------------------------------------------------------------------

def _grilla_del_dia(dia: date, agenda: dict, tz: ZoneInfo) -> list[tuple[datetime, datetime, float, float]]:
    """Turnos del dia dentro del horario de `agenda`: (inicio, fin, azar_paciente, azar_estado)."""
    ventanas = agenda["horario"].get(_DIAS[dia.weekday()], [])
    if not ventanas:
        return []
    paso = agenda["duracion_slot_min"]
    rng = random.Random(f"seed-demo-turnos-{dia.isoformat()}")
    candidatos: list[tuple[int, int, int]] = []  # (inicio_min, ventana_fin_min, ventana_idx)
    for idx, (desde, hasta) in enumerate(ventanas):
        h1, m1 = map(int, desde.split(":"))
        h2, m2 = map(int, hasta.split(":"))
        fin_min = h2 * 60 + m2
        candidatos += [(m, fin_min, idx) for m in range(h1 * 60 + m1, fin_min, paso)]
    rng.shuffle(candidatos)
    objetivo = rng.randint(4, 7)
    ocupados: list[tuple[int, int]] = []
    salida: list[tuple[datetime, datetime, float, float]] = []
    for inicio_min, fin_ventana, _ in candidatos:
        if len(salida) == objetivo:
            break
        fin_min = inicio_min + rng.choice((paso, paso, 2 * paso))
        azar_paciente, azar_estado = rng.random(), rng.random()
        if fin_min > fin_ventana or any(inicio_min < f and fin_min > i for i, f in ocupados):
            continue
        ocupados.append((inicio_min, fin_min))
        base = datetime(dia.year, dia.month, dia.day, tzinfo=tz)
        salida.append((
            base + timedelta(minutes=inicio_min), base + timedelta(minutes=fin_min),
            azar_paciente, azar_estado,
        ))
    return sorted(salida)


def _estado_demo(inicio: datetime, fin: datetime, ahora: datetime, azar: float) -> str:
    if fin <= ahora:
        return "asistido" if azar < 0.60 else "ausente" if azar < 0.75 else "cancelado"
    return "confirmado" if azar < 0.50 else "pendiente" if azar < 0.85 else "cancelado"


async def seed_turnos_demo(
    sesion, profesional: Profesional, sillon: Sillon, agenda: dict, ahora: datetime,
    creado_por: int | None = None,
) -> int:
    """Turnos de los ultimos ~3 y proximos ~2 semanas, relativos a `ahora`; devuelve los creados."""
    tz = ahora.tzinfo if isinstance(ahora.tzinfo, ZoneInfo) else ZoneInfo("America/Argentina/Buenos_Aires")
    pacientes_ids = list((await sesion.execute(
        select(Paciente.id).where(Paciente.dni.like("9000%"), Paciente.deleted_at.is_(None))
        .order_by(Paciente.dni)
    )).scalars().all())
    if not pacientes_ids:
        return 0
    turnos = TurnoRepository(sesion)
    pacientes, profesionales, sillones = (
        PacienteRepository(sesion), ProfesionalRepository(sesion), SillonRepository(sesion)
    )
    creados = 0
    hoy = ahora.astimezone(tz).date()
    for delta in range(-DIAS_PASADO, DIAS_FUTURO + 1):
        for inicio, fin, azar_paciente, azar_estado in _grilla_del_dia(hoy + timedelta(days=delta), agenda, tz):
            paciente_id = pacientes_ids[int(azar_paciente * len(pacientes_ids))]
            existe = await sesion.scalar(select(Turno.id).where(
                Turno.paciente_id == paciente_id, Turno.profesional_id == profesional.id,
                Turno.inicio == inicio,
            ))
            if existe is not None or await turnos.hay_solapamiento(
                profesional.id, sillon.id, inicio, fin
            ):
                continue
            estado = _estado_demo(inicio, fin, ahora, azar_estado)
            turno = await agenda_servicio.crear_turno(
                turnos, pacientes, profesionales, sillones,
                paciente_id=paciente_id, profesional_id=profesional.id, sillon_id=sillon.id,
                inicio=inicio, fin=fin, origen="online" if estado == "pendiente" else "secretaria",
                creado_por=creado_por, es_admin=True, ahora=ahora,
            )
            if estado in ("asistido", "ausente"):
                await agenda_servicio.cambiar_estado(turnos, turno.id, estado)
            elif estado == "cancelado":
                await agenda_servicio.cambiar_estado(
                    turnos, turno.id, "cancelado", motivo="Cancelado por el paciente (demo)"
                )
            creados += 1
    return creados


# --- clinica y cobros --------------------------------------------------------------------------------

async def _asegurar_catalogo_estados(sesion) -> None:
    """El catalogo V1 lo carga la migracion 005; en bases creadas sin ella se completa aca."""
    for codigo, nombre, alcance in CATALOGO_ESTADOS_V1:
        if await sesion.scalar(select(EstadoHallazgoCatalogo.id).where(
            EstadoHallazgoCatalogo.codigo == codigo,
            EstadoHallazgoCatalogo.version == CATALOGO_VERSION_V1,
        )) is None:
            sesion.add(EstadoHallazgoCatalogo(
                codigo=codigo, version=CATALOGO_VERSION_V1, nombre=nombre, alcance=alcance,
                vigente=True,
            ))
    await sesion.flush()


async def _fecha_primera_visita(sesion, paciente_id: int, ahora: datetime) -> datetime:
    inicio = await sesion.scalar(select(Turno.inicio).where(
        Turno.paciente_id == paciente_id, Turno.estado == "asistido", Turno.inicio < ahora,
    ).order_by(Turno.inicio).limit(1))
    return inicio if inicio is not None else ahora - timedelta(days=7)


async def seed_clinica_y_cobros(
    sesion, odontologo: Usuario, secretaria: Usuario, admin: Usuario,
    profesional: Profesional, ahora: datetime,
) -> None:
    """HC + odontograma + presupuestos por paciente y, luego, cobros con cajas cerradas."""
    await _asegurar_catalogo_estados(sesion)
    repos = CajaRepos.de_sesion(sesion)
    actor_odo = Actor(odontologo.id, "odontologo", profesional.id)
    actor_sec = Actor(secretaria.id, "secretaria", None)
    actor_adm = Actor(admin.id, "admin", None)
    tratamientos = {
        codigo: tid for codigo, tid in (await sesion.execute(
            select(Tratamiento.codigo, Tratamiento.id)
        )).all()
    }
    candidatos = (await sesion.execute(
        select(Paciente).where(Paciente.dni.like("9000%"), Paciente.deleted_at.is_(None))
        .order_by(Paciente.dni).limit(CANDIDATOS_CLINICOS)
    )).scalars().all()

    pagos: list[tuple[str, int, Decimal]] = []  # (dni, presupuesto_id, monto) en orden de emision
    for idx, paciente in enumerate(candidatos):
        if await repos.clinica.historias.por_paciente(paciente.id) is not None:
            continue
        if not await repos.clinica.turnos.existe_vinculo(profesional.id, paciente.id):
            continue
        visita = await _fecha_primera_visita(sesion, paciente.id, ahora)
        hc = await clinica_servicio.crear_historia(
            repos.clinica, actor_odo, paciente.id,
            ANTECEDENTES_DEMO[idx % len(ANTECEDENTES_DEMO)], ALERGIAS_DEMO[idx % len(ALERGIAS_DEMO)],
            ahora=visita,
        )
        items: list[ItemIn] = []
        for k in range(4):
            pieza, cara, estado = HALLAZGOS_DEMO[(idx * 3 + k) % len(HALLAZGOS_DEMO)]
            hallazgo = await clinica_servicio.registrar_hallazgo(
                repos.clinica, actor_odo, hc.id, pieza, cara, estado,
                ahora=visita + timedelta(minutes=5 * k),
            )
            codigo = TRATAMIENTO_POR_ESTADO.get(estado)
            if codigo is not None and codigo in tratamientos:
                items.append(ItemIn(hallazgo_id=hallazgo.id, tratamiento_id=tratamientos[codigo]))
        if not items:
            continue
        momento = visita + timedelta(hours=1)
        presupuesto = await presupuesto_servicio.crear(
            repos.base, actor_odo, paciente.id, items, ahora=momento
        )
        escenario = idx % 6  # 0 cobrado, 1 parcial, 2 deuda, 3 presentado, 4 rechazado, 5 borrador
        if escenario == 5:
            continue
        await presupuesto_servicio.presentar(repos.base, actor_odo, presupuesto.id, ahora=momento)
        if escenario == 3:
            continue
        if escenario == 4:
            await presupuesto_servicio.rechazar(
                repos.base, actor_odo, presupuesto.id, "El paciente lo pospone (demo)", ahora=momento
            )
            continue
        await presupuesto_servicio.aceptar(repos.base, actor_odo, presupuesto.id, ahora=momento)
        pendiente = await repos.cuentas.pendiente_de_presupuesto(presupuesto.id)
        if escenario == 0 and pendiente > 0:
            if (idx // 6) % 2 == 1:  # dos cuotas: dos recibos
                mitad = (pendiente / 2).quantize(Decimal("0.01"))
                pagos += [(paciente.dni, presupuesto.id, mitad), (paciente.dni, presupuesto.id, pendiente - mitad)]
            else:
                pagos.append((paciente.dni, presupuesto.id, pendiente))
        elif escenario == 1 and pendiente > 0:
            pagos.append((paciente.dni, presupuesto.id, (pendiente / 2).quantize(Decimal("0.01"))))
    await _cobrar_y_cerrar_cajas(repos, actor_sec, actor_adm, pagos, ahora)


async def _cobrar_y_cerrar_cajas(
    repos: CajaRepos, secretaria: Actor, admin: Actor,
    pagos: list[tuple[str, int, Decimal]], ahora: datetime,
) -> None:
    """Reparte los pagos en dias pasados; cada caja se cierra antes de pasar al dia siguiente."""
    if not pagos:
        return
    hoy = ahora.date()
    caja_hoy = await repos.cajas.por_fecha(hoy)
    if await repos.cajas.pendiente_anterior(hoy) is not None or (
        caja_hoy is not None and caja_hoy.estado == "cerrada"
    ):
        return  # estado de caja real: el seed no interfiere
    dias = [
        d for d in (hoy - timedelta(days=k) for k in range(DIAS_CAJA, 0, -1))
        if d.weekday() != 6 and await repos.cajas.por_fecha(d) is None
    ]
    if not dias:
        return
    por_dia: dict[date, list[tuple[int, str, int, Decimal, int]]] = {d: [] for d in dias}
    contador: dict[str, int] = {}
    for j, (dni, presupuesto_id, monto) in enumerate(pagos):
        contador[dni] = contador.get(dni, 0) + 1
        por_dia[dias[j * len(dias) // len(pagos)]].append((j, dni, presupuesto_id, monto, contador[dni]))
    cerradas = 0
    for dia in dias:
        for j, dni, presupuesto_id, monto, orden in por_dia[dia]:
            try:
                cobro, creado = await caja_servicio.cobrar(
                    repos, secretaria,
                    CobroIn(
                        presupuesto_id=presupuesto_id, monto=monto, medio=MEDIOS_DEMO[j % len(MEDIOS_DEMO)],
                        clave_idempotencia=_clave_cobro(dni, orden),
                    ),
                    hoy=dia,
                )
            except ConflictoError:
                continue
            if j == 0 and creado:  # un recibo anulado: contramovimiento + motivo, nunca borrado
                await caja_servicio.anular_recibo(
                    repos, admin, cobro.id, "Error de carga del medio de pago (demo)", hoy=dia
                )
        caja = await repos.cajas.por_fecha(dia)
        if caja is None or caja.estado != "abierta":
            continue
        total = await repos.cajas.total(caja.id)
        cerradas += 1
        con_diferencia = cerradas == 2 and total >= Decimal("1000.00")
        await caja_servicio.cerrar(
            repos, secretaria,
            CierreIn(
                caja_id=caja.id,
                total_contado=total - Decimal("500.00") if con_diferencia else total,
                motivo_diferencia="Faltante de vuelto en el arqueo (demo)" if con_diferencia else None,
            ),
        )


__all__ = ["seed_clinica_y_cobros", "seed_turnos_demo"]
