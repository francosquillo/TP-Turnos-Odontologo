"""Servicio de presupuestos (C-09, D-03..D-10, D-13, D-19, D-20).

Reglas:
- odontologo: escribe solo sus presupuestos (autor) y solo con vínculo al paciente
  (turno no cancelado); lee los de cualquier colega vinculado.
- secretaria: lee cualquiera, nunca escribe. admin: lee con vista financiera
  (`pieza_fdi`, `cara` y `motivo_rechazo` en `None`), nunca escribe (D-09).
- Toda transición y edición toma `SELECT ... FOR UPDATE` y valida el estado
  recién después del lock (D-13). `aceptar` crea el cargo en la misma transacción.

Solo hace `flush`: el router es dueño del commit/rollback. NO loguea nada: los
motivos y los ítems son PHI (D-20); los errores de dominio llevan mensajes fijos.
Reutiliza `Actor`, los errores y los chequeos de acceso de `clinica_servicio`.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

from sqlalchemy.exc import IntegrityError

from app.esquemas.presupuesto import ItemIn, ItemOut, PresupuestoOut
from app.modelos import HistoriaClinica, Presupuesto
from app.repos.cuenta_repo import CuentaRepository
from app.repos.presupuesto_repo import ItemDetalle, PresupuestoRepository
from app.repos.tratamiento_repo import TratamientoRepository
from app.servicios import clinica_servicio as cs
from app.servicios.clinica_servicio import (  # noqa: F401  (reexportados al router y a los tests)
    AccesoDenegadoError, Actor, ClinicaError, ConflictoError, NoEncontradoError,
    ValidacionClinicaError, construir_actor,
)

_MSG_HALLAZGO = "hallazgo inválido para el paciente"
_MSG_HALLAZGO_CAMBIO = "un hallazgo del presupuesto fue corregido o dado de baja"
_CENTAVOS = Decimal("0.01")


@dataclass
class PresupuestoRepos:
    clinica: cs.ClinicaRepos
    presupuestos: PresupuestoRepository
    cuentas: CuentaRepository
    tratamientos: TratamientoRepository

    @classmethod
    def de_sesion(cls, sesion) -> "PresupuestoRepos":
        return cls(
            clinica=cs.ClinicaRepos.de_sesion(sesion),
            presupuestos=PresupuestoRepository(sesion),
            cuentas=CuentaRepository(sesion),
            tratamientos=TratamientoRepository(sesion),
        )


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


# --- acceso -----------------------------------------------------------------------------

async def _exigir_lectura(repos: PresupuestoRepos, actor: Actor, paciente_id: int) -> None:
    """Admin lee (vista financiera); secretaria y odontólogo vinculado, como en C-08."""
    if actor.rol == "admin":
        return
    await cs.exigir_lectura(repos.clinica, actor, paciente_id)


async def _exigir_autor(repos: PresupuestoRepos, actor: Actor, presupuesto: Presupuesto) -> None:
    """Escribir exige ser odontólogo vinculado Y el autor del presupuesto (D-10)."""
    await cs.exigir_escritura(repos.clinica, actor, presupuesto.paciente_id)
    if presupuesto.profesional_id != actor.profesional_id:
        raise AccesoDenegadoError("solo el autor puede modificar el presupuesto")


# --- ítems ----------------------------------------------------------------------------------

async def _historia_activa_del_paciente(repos: PresupuestoRepos, paciente_id: int) -> HistoriaClinica:
    hc = await repos.clinica.historias.por_paciente(paciente_id)
    if hc is None or hc.deleted_at is not None:
        raise ValidacionClinicaError("el paciente no tiene historia clínica activa")
    return hc


async def _armar_items(
    repos: PresupuestoRepos, hc: HistoriaClinica, items: Sequence[ItemIn]
) -> tuple[list[dict], Decimal]:
    """Valida cada ítem y copia `precio_base`; devuelve (filas, total)."""
    filas: list[dict] = []
    total = Decimal("0")
    for item in items:
        hallazgo = await repos.clinica.hallazgos.get_en_hc(hc.id, item.hallazgo_id)
        # Mismo mensaje si no existe, es de otro paciente o está dado de baja (D-04).
        if hallazgo is None or hallazgo.deleted_at is not None:
            raise ValidacionClinicaError(_MSG_HALLAZGO)
        tratamiento = await repos.tratamientos.get(item.tratamiento_id)
        if tratamiento is None:
            raise ValidacionClinicaError("tratamiento inexistente")
        filas.append({
            "hallazgo_id": hallazgo.id, "tratamiento_id": tratamiento.id,
            "cantidad": item.cantidad, "precio": tratamiento.precio_base,
        })
        total += item.cantidad * tratamiento.precio_base
    return filas, total.quantize(_CENTAVOS)


# --- alta ---------------------------------------------------------------------------------------

async def crear(
    repos: PresupuestoRepos, actor: Actor, paciente_id: int, items: Sequence[ItemIn],
    ahora: datetime | None = None,
) -> Presupuesto:
    """Borrador del odontólogo autenticado; estado, autor, precio y total los fija el servidor."""
    ahora = ahora or _ahora()
    if actor.rol != "odontologo" or actor.profesional_id is None:
        raise AccesoDenegadoError("sin permiso de escritura de presupuestos")
    paciente = await repos.clinica.pacientes.get(paciente_id)
    if paciente is None or paciente.deleted_at is not None:
        raise NoEncontradoError("paciente inexistente")
    await cs.exigir_escritura(repos.clinica, actor, paciente_id)
    hc = await _historia_activa_del_paciente(repos, paciente_id)
    filas, total = await _armar_items(repos, hc, items)
    presupuesto = await repos.presupuestos.crear(
        paciente_id=paciente_id, profesional_id=actor.profesional_id, estado="borrador",
        total=total, created_at=ahora, updated_at=ahora,
    )
    await repos.presupuestos.reemplazar_items(presupuesto.id, filas)
    return presupuesto


# --- edición y baja (solo borrador, solo autor) ------------------------------------------------

async def _bloquear_del_autor(
    repos: PresupuestoRepos, actor: Actor, presupuesto_id: int
) -> Presupuesto:
    """404 si no existe, lock `FOR UPDATE` y 403 si no es el autor (el estado se valida después)."""
    presupuesto = await repos.presupuestos.get_para_actualizar(presupuesto_id)
    if presupuesto is None:
        raise NoEncontradoError("presupuesto inexistente")
    await _exigir_autor(repos, actor, presupuesto)
    return presupuesto


def _exigir_estado(presupuesto: Presupuesto, esperado: str) -> None:
    if presupuesto.estado != esperado:
        raise ConflictoError(f"el presupuesto no está en estado {esperado}")


async def reemplazar_items(
    repos: PresupuestoRepos, actor: Actor, presupuesto_id: int, items: Sequence[ItemIn],
    ahora: datetime | None = None,
) -> Presupuesto:
    """Reemplaza la lista completa de ítems de un borrador y recalcula el total."""
    presupuesto = await _bloquear_del_autor(repos, actor, presupuesto_id)
    _exigir_estado(presupuesto, "borrador")
    hc = await _historia_activa_del_paciente(repos, presupuesto.paciente_id)
    filas, total = await _armar_items(repos, hc, items)
    await repos.presupuestos.reemplazar_items(presupuesto.id, filas)
    return await repos.presupuestos.actualizar(
        presupuesto, total=total, updated_at=ahora or _ahora()
    )


async def dar_de_baja(
    repos: PresupuestoRepos, actor: Actor, presupuesto_id: int, motivo: str,
    ahora: datetime | None = None,
) -> Presupuesto:
    """Baja lógica con motivo, solo de un borrador (D-18); la fila se conserva."""
    presupuesto = await _bloquear_del_autor(repos, actor, presupuesto_id)
    _exigir_estado(presupuesto, "borrador")
    ahora = ahora or _ahora()
    return await repos.presupuestos.actualizar(
        presupuesto, deleted_at=ahora, motivo_baja=motivo, updated_at=ahora
    )


# --- máquina de estados ------------------------------------------------------------------------

async def _exigir_hallazgos_vigentes(repos: PresupuestoRepos, presupuesto: Presupuesto) -> None:
    """409 si algún ítem apunta a un hallazgo dado de baja o corregido (D-05)."""
    detalle = await repos.presupuestos.items_detalle(presupuesto.id)
    if not all(d.hallazgo_vigente for d in detalle):
        raise ConflictoError(_MSG_HALLAZGO_CAMBIO)


async def presentar(
    repos: PresupuestoRepos, actor: Actor, presupuesto_id: int, ahora: datetime | None = None,
) -> Presupuesto:
    """borrador -> presentado: revalida hallazgos (409) y exige total > 0 (422, D-08)."""
    presupuesto = await _bloquear_del_autor(repos, actor, presupuesto_id)
    _exigir_estado(presupuesto, "borrador")
    await _exigir_hallazgos_vigentes(repos, presupuesto)
    if presupuesto.total <= 0:
        raise ValidacionClinicaError("el presupuesto debe tener un total mayor que cero")
    ahora = ahora or _ahora()
    return await repos.presupuestos.actualizar(
        presupuesto, estado="presentado", presentado_at=ahora, updated_at=ahora
    )


async def rechazar(
    repos: PresupuestoRepos, actor: Actor, presupuesto_id: int, motivo: str,
    ahora: datetime | None = None,
) -> Presupuesto:
    """presentado -> rechazado (final, sin movimientos). No revalida hallazgos (D-05)."""
    presupuesto = await _bloquear_del_autor(repos, actor, presupuesto_id)
    _exigir_estado(presupuesto, "presentado")
    ahora = ahora or _ahora()
    return await repos.presupuestos.actualizar(
        presupuesto, estado="rechazado", motivo_rechazo=motivo, decidido_at=ahora, updated_at=ahora
    )


async def aceptar(
    repos: PresupuestoRepos, actor: Actor, presupuesto_id: int, ahora: datetime | None = None,
) -> Presupuesto:
    """presentado -> aceptado + un único cargo por `total`, en la misma transacción (D-13).

    El segundo `aceptar` espera el lock, ve `aceptado` y recibe 409. Red de seguridad:
    el índice único parcial del cargo; su `IntegrityError` también es 409 y el
    savepoint deja el presupuesto sin tocar.
    """
    presupuesto = await _bloquear_del_autor(repos, actor, presupuesto_id)
    _exigir_estado(presupuesto, "presentado")
    await _exigir_hallazgos_vigentes(repos, presupuesto)
    ahora = ahora or _ahora()
    try:
        async with repos.presupuestos.sesion.begin_nested():
            cuenta = await repos.cuentas.asegurar(presupuesto.paciente_id)
            await repos.cuentas.crear_movimiento(
                cuenta.id, tipo="cargo", monto=presupuesto.total,
                concepto=f"Presupuesto {presupuesto.id}", presupuesto_id=presupuesto.id,
                creado_por=actor.usuario_id,
            )
    except IntegrityError:
        raise ConflictoError("el presupuesto ya tiene un cargo") from None
    return await repos.presupuestos.actualizar(
        presupuesto, estado="aceptado", decidido_at=ahora, updated_at=ahora
    )


# --- lectura (la vista financiera del admin se arma en `a_salida`) ---------------------------

async def obtener(repos: PresupuestoRepos, actor: Actor, presupuesto_id: int) -> Presupuesto:
    presupuesto = await repos.presupuestos.get_activo(presupuesto_id)
    if presupuesto is None:
        raise NoEncontradoError("presupuesto inexistente")
    await _exigir_lectura(repos, actor, presupuesto.paciente_id)
    return presupuesto


async def listar(
    repos: PresupuestoRepos, actor: Actor, paciente_id: int, estado: str | None = None
) -> list[Presupuesto]:
    await _exigir_lectura(repos, actor, paciente_id)
    return await repos.presupuestos.listar(paciente_id, estado)


# --- armado de la respuesta (único punto: la vista financiera del admin vive acá, D-09) ----

def _item_out(detalle: ItemDetalle, financiera: bool) -> ItemOut:
    item = detalle.item
    return ItemOut(
        id=item.id, hallazgo_id=item.hallazgo_id, tratamiento_id=item.tratamiento_id,
        tratamiento_nombre=detalle.tratamiento_nombre,
        pieza_fdi=None if financiera else detalle.pieza_fdi,
        cara=None if financiera else detalle.cara,
        cantidad=item.cantidad, precio=item.precio,
        subtotal=(item.cantidad * item.precio).quantize(_CENTAVOS),
        hallazgo_vigente=detalle.hallazgo_vigente,
    )


async def a_salidas(
    repos: PresupuestoRepos, actor: Actor, presupuestos: Sequence[Presupuesto]
) -> list[PresupuestoOut]:
    """Respuesta de cada presupuesto; el admin recibe la vista financiera (sin datos clínicos)."""
    financiera = actor.rol == "admin"
    anulados = await repos.cuentas.presupuestos_con_cargo_anulado([p.id for p in presupuestos])
    salidas: list[PresupuestoOut] = []
    for p in presupuestos:
        detalle = await repos.presupuestos.items_detalle(p.id)
        salidas.append(PresupuestoOut(
            id=p.id, paciente_id=p.paciente_id, profesional_id=p.profesional_id,
            estado=p.estado, total=p.total,
            motivo_rechazo=None if financiera else p.motivo_rechazo,
            presentado_at=p.presentado_at, decidido_at=p.decidido_at,
            created_at=p.created_at, updated_at=p.updated_at,
            cargo_anulado=p.id in anulados,
            es_propio=actor.profesional_id is not None and p.profesional_id == actor.profesional_id,
            items=[_item_out(d, financiera) for d in detalle],
        ))
    return salidas


async def a_salida(repos: PresupuestoRepos, actor: Actor, presupuesto: Presupuesto) -> PresupuestoOut:
    return (await a_salidas(repos, actor, [presupuesto]))[0]
