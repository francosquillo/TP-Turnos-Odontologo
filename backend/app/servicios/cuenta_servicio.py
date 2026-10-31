"""Servicio de cuenta corriente (C-09, D-11, D-14, D-15, D-16).

Reglas:
- secretaria y admin leen cualquier cuenta; solo admin anula; odontólogo sin acceso (D-15).
- El saldo se deriva con SUM en cada lectura y consultar NO crea filas (D-11).
- Un paciente dado de baja sin cuenta es 404; con cuenta se consulta igual, porque la
  deuda sobrevive a la baja (RN-GL-01).
- La anulación crea un `ajuste` opuesto con `anula_a_id` y motivo, bajo `FOR UPDATE` sobre
  el cargo; solo se anula un `cargo`, una sola vez (D-14). El presupuesto no cambia de
  estado: `cargo_anulado` es derivado. No existe escritura directa de movimientos.

Solo hace `flush` (el router hace commit). NO loguea nada: los motivos son datos sensibles.
Reutiliza `Actor` y los errores de dominio de `clinica_servicio`.
"""
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.esquemas.cuenta import CuentaOut, MovimientoOut, PendienteOut
from app.modelos import Movimiento
from app.servicios.clinica_servicio import (  # noqa: F401  (reexportados al router y a los tests)
    AccesoDenegadoError, Actor, ClinicaError, ConflictoError, NoEncontradoError,
    ValidacionClinicaError, construir_actor,
)
from app.servicios.presupuesto_servicio import PresupuestoRepos


def _a_movimiento_out(movimiento: Movimiento, anulado: bool) -> MovimientoOut:
    return MovimientoOut(
        id=movimiento.id, tipo=movimiento.tipo, monto=movimiento.monto,
        concepto=movimiento.concepto, motivo=movimiento.motivo, turno_id=movimiento.turno_id,
        presupuesto_id=movimiento.presupuesto_id, recibo_id=movimiento.recibo_id,
        anula_a_id=movimiento.anula_a_id, creado_por=movimiento.creado_por,
        created_at=movimiento.created_at, anulado=anulado,
    )


async def obtener_cuenta(repos: PresupuestoRepos, actor: Actor, paciente_id: int) -> CuentaOut:
    if actor.rol not in ("secretaria", "admin"):
        raise AccesoDenegadoError("sin permiso sobre la cuenta corriente")
    paciente = await repos.clinica.pacientes.get(paciente_id)
    if paciente is None:
        raise NoEncontradoError("paciente inexistente")
    cuenta = await repos.cuentas.por_paciente(paciente_id)
    if cuenta is None:
        if paciente.deleted_at is not None:
            raise NoEncontradoError("paciente inexistente")
        return CuentaOut(paciente_id=paciente_id, saldo=0, movimientos=[])
    movimientos = await repos.cuentas.movimientos(cuenta.id)
    pendientes = await repos.cuentas.pendientes_de_paciente(paciente_id)
    return CuentaOut(
        paciente_id=paciente_id,
        saldo=await repos.cuentas.saldo(cuenta.id),
        movimientos=[_a_movimiento_out(f.movimiento, f.anulado) for f in movimientos],
        pendientes=[
            PendienteOut(presupuesto_id=f.presupuesto_id, total=f.total, pendiente=f.pendiente)
            for f in pendientes
        ],
    )


async def anular_cargo(
    repos: PresupuestoRepos, actor: Actor, paciente_id: int, movimiento_id: int, motivo: str,
) -> MovimientoOut:
    """Contramovimiento (`ajuste`) por el monto opuesto de un cargo, sin tocar el original."""
    if actor.rol != "admin":
        raise AccesoDenegadoError("solo el administrador anula movimientos")
    cuenta = await repos.cuentas.por_paciente(paciente_id)
    if cuenta is None:
        raise NoEncontradoError("movimiento inexistente")
    original = await repos.cuentas.movimiento_para_actualizar(cuenta.id, movimiento_id)
    if original is None:
        raise NoEncontradoError("movimiento inexistente")
    if original.tipo != "cargo":
        raise ConflictoError("solo se anula un cargo; un pago se anula desde su recibo")
    if await repos.cuentas.tiene_anulacion(original.id):
        raise ConflictoError("el cargo ya fue anulado")
    try:
        async with repos.cuentas.sesion.begin_nested():
            anulacion = await repos.cuentas.crear_movimiento(
                cuenta.id, tipo="ajuste", monto=-original.monto,
                concepto=f"Anulación del movimiento {original.id}", motivo=motivo,
                presupuesto_id=original.presupuesto_id, anula_a_id=original.id,
                creado_por=actor.usuario_id,
            )
    except IntegrityError:
        raise ConflictoError("el cargo ya fue anulado") from None
    return _a_movimiento_out(anulacion, anulado=False)
