"""Servicio de caja y recibos (C-10, D-04..D-13, D-15, D-16, D-22, D-23, D-25).

Reglas:
- Solo `secretaria` cobra y cierra; solo `admin` anula recibos; ambos consultan (D-16).
- El día operativo lo decide `hoy_operativo()` en `America/Argentina/Buenos_Aires`; el
  cliente nunca envía fechas (D-04). La caja se abre sola con el primer movimiento (D-05).
- "Operar" significa mover caja: cobrar y anular recibos exigen `_caja_operable` (D-06).
- Orden de locks, siempre `FOR UPDATE`: cobrar caja -> presupuesto -> contador; anular
  caja -> recibo -> presupuesto; cierre caja (D-11).
- Cobro idempotente por `clave_idempotencia` (D-25): la clave se resuelve antes de
  cualquier control de caja o presupuesto, porque repetir la respuesta no mueve dinero.
- Recibo, `pago` y movimiento de caja nacen juntos en un savepoint; el número se pide
  lo más tarde posible y vuelve al contador si algo falla (D-10, D-15).

Solo hace `flush` (el router es dueño del commit). NO loguea nada: los motivos son datos
sensibles. Los mensajes de error son fijos. Sin subclases de error: `a_http` busca el
tipo exacto. Reutiliza `Actor` y los errores de `clinica_servicio`.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.esquemas.caja import (
    CajaOut, CierreIn, CobroIn, CobroOut, DesgloseMedioOut, EstadoCajaOut,
    IngresoLiquidacionOut, ReciboOut,
)
from app.modelos import Caja, Recibo
from app.repos.caja_repo import CajaRepository
from app.repos.recibo_repo import ReciboRepository
from app.servicios.clinica_servicio import (  # noqa: F401  (reexportados al router y a los tests)
    AccesoDenegadoError, Actor, ClinicaError, ConflictoError, NoEncontradoError,
    ValidacionClinicaError, construir_actor,
)
from app.servicios.presupuesto_servicio import PresupuestoRepos, saldar_si_corresponde

_MSG_PENDIENTE = "hay una caja anterior sin cerrar"
_MSG_CERRADA = "la caja de hoy ya está cerrada"
_MSG_OTRA_ABIERTA = "hay otra caja abierta"
_MSG_COLISION = "no se pudo registrar el cobro, reintente"


@dataclass
class CajaRepos:
    base: PresupuestoRepos
    cajas: CajaRepository
    recibos: ReciboRepository

    @property
    def clinica(self):
        return self.base.clinica

    @property
    def presupuestos(self):
        return self.base.presupuestos

    @property
    def cuentas(self):
        return self.base.cuentas

    @classmethod
    def de_sesion(cls, sesion) -> "CajaRepos":
        return cls(
            base=PresupuestoRepos.de_sesion(sesion),
            cajas=CajaRepository(sesion),
            recibos=ReciboRepository(sesion),
        )


def hoy_operativo() -> date:
    """Único lugar que decide el día: zona configurada, no `CURRENT_DATE` (D-04)."""
    return datetime.now(ZoneInfo(get_settings().tz)).date()


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _exigir_rol(actor: Actor, *roles: str) -> None:
    if actor.rol not in roles:
        raise AccesoDenegadoError("sin permiso sobre la caja")


async def _caja_operable(repos: CajaRepos, hoy: date) -> None:
    """409 si hay una caja abierta de un día anterior o la de hoy ya se cerró (D-06, D-07)."""
    if await repos.cajas.pendiente_anterior(hoy) is not None:
        raise ConflictoError(_MSG_PENDIENTE)
    caja_hoy = await repos.cajas.por_fecha(hoy)
    if caja_hoy is not None and caja_hoy.estado == "cerrada":
        raise ConflictoError(_MSG_CERRADA)


async def _asegurar_y_bloquear(repos: CajaRepos, hoy: date, usuario_id: int) -> Caja:
    """Abre la caja de hoy si falta y la bloquea; revalida el estado tras el lock (D-11)."""
    await repos.cajas.asegurar(hoy, usuario_id)
    caja = await repos.cajas.por_fecha_para_actualizar(hoy)
    if caja is None:
        # Otra caja quedó abierta (`uq_caja_una_abierta`) y la de hoy no existe.
        raise ConflictoError(_MSG_OTRA_ABIERTA)
    if caja.estado != "abierta":
        raise ConflictoError(_MSG_CERRADA)
    return caja


async def caja_para_movimiento(repos: CajaRepos, hoy: date, usuario_id: int) -> Caja:
    """Control de caja y bloqueo para cualquier movimiento que mueva dinero (C-11, D-12).

    Pública para que las liquidaciones no copien ni importen nombres privados: 409 si hay
    una caja anterior sin cerrar o la de hoy está cerrada; abre la de hoy si falta y la
    devuelve bloqueada (`FOR UPDATE`).
    """
    await _caja_operable(repos, hoy)
    return await _asegurar_y_bloquear(repos, hoy, usuario_id)


# --- salidas -----------------------------------------------------------------------------

async def _a_recibo_out(repos: CajaRepos, recibo: Recibo, nombre: str | None = None,
                        fecha: date | None = None) -> ReciboOut:
    if nombre is None:
        paciente = await repos.clinica.pacientes.get(recibo.paciente_id)
        nombre = f"{paciente.nombre} {paciente.apellido}"
    if fecha is None:
        fecha = await repos.recibos.fecha_de(recibo.id)
    return ReciboOut(
        id=recibo.id, numero=recibo.numero, paciente_id=recibo.paciente_id,
        paciente_nombre=nombre, monto=recibo.monto, medio=recibo.medio, fecha=fecha,
        emitido_por=recibo.emitido_por, created_at=recibo.created_at, anulado=recibo.anulado,
        motivo_anulacion=recibo.motivo_anulacion, anulado_por=recibo.anulado_por,
        anulado_at=recibo.anulado_at,
    )


async def _a_cobro_out(repos: CajaRepos, recibo: Recibo) -> CobroOut:
    pago = await repos.cuentas.pago_de_recibo(recibo.id)
    base = await _a_recibo_out(repos, recibo)
    return CobroOut(
        **base.model_dump(), presupuesto_id=pago.presupuesto_id,
        presupuesto_estado=await repos.presupuestos.estado_de(pago.presupuesto_id),
    )


async def _a_caja_out(repos: CajaRepos, caja: Caja) -> CajaOut:
    total = caja.total_sistema if caja.estado == "cerrada" else await repos.cajas.total(caja.id)
    return CajaOut(
        id=caja.id, fecha=caja.fecha, estado=caja.estado, abierta_por=caja.abierta_por,
        total_sistema=total, total_contado=caja.total_contado, diferencia=caja.diferencia,
        motivo_diferencia=caja.motivo_diferencia, cerrada_por=caja.cerrada_por,
        cerrada_at=caja.cerrada_at,
    )


# --- cobro ---------------------------------------------------------------------------------

async def _resolver_reintento(repos: CajaRepos, recibo: Recibo, datos: CobroIn) -> CobroOut:
    """Misma clave: igual contenido devuelve el original; otro contenido es 409 (D-25)."""
    pago = await repos.cuentas.pago_de_recibo(recibo.id)
    if (
        pago is None or pago.presupuesto_id != datos.presupuesto_id
        or recibo.monto != datos.monto or recibo.medio != datos.medio
    ):
        raise ConflictoError("la clave ya se usó con otro cobro")
    return await _a_cobro_out(repos, recibo)


async def cobrar(
    repos: CajaRepos, actor: Actor, datos: CobroIn, hoy: date | None = None,
) -> tuple[CobroOut, bool]:
    """Recibo + `pago` + movimiento de caja en una transacción; devuelve (cobro, creado)."""
    _exigir_rol(actor, "secretaria")
    existente = await repos.recibos.por_clave(datos.clave_idempotencia)
    if existente is not None:
        return await _resolver_reintento(repos, existente, datos), False
    hoy = hoy or hoy_operativo()
    await _caja_operable(repos, hoy)
    caja = await _asegurar_y_bloquear_para_cobro(repos, hoy, actor, datos)
    if isinstance(caja, Recibo):  # la relectura de la clave encontró el recibo original
        return await _resolver_reintento(repos, caja, datos), False

    presupuesto = await repos.presupuestos.get_para_actualizar(datos.presupuesto_id)
    if presupuesto is None:
        raise NoEncontradoError("presupuesto inexistente")
    if presupuesto.estado != "aceptado":
        raise ConflictoError("el presupuesto no está aceptado")
    pendiente = await repos.cuentas.pendiente_de_presupuesto(presupuesto.id)
    if pendiente <= 0:
        raise ConflictoError("el presupuesto no tiene importe pendiente")
    if datos.monto > pendiente:
        raise ValidacionClinicaError("el importe supera el pendiente")

    try:
        async with repos.cajas.sesion.begin_nested():
            numero = await repos.recibos.siguiente_numero()
            recibo = await repos.recibos.crear(
                numero=numero, paciente_id=presupuesto.paciente_id, monto=datos.monto,
                medio=datos.medio, emitido_por=actor.usuario_id,
                clave_idempotencia=datos.clave_idempotencia,
            )
            cuenta = await repos.cuentas.por_paciente(presupuesto.paciente_id)
            await repos.cuentas.crear_movimiento(
                cuenta.id, tipo="pago", monto=-datos.monto, concepto=f"Recibo {numero}",
                presupuesto_id=presupuesto.id, recibo_id=recibo.id,
                creado_por=actor.usuario_id,
            )
            await repos.cajas.crear_movimiento(
                caja_id=caja.id, recibo_id=recibo.id, medio=datos.medio, monto=datos.monto,
                creado_por=actor.usuario_id,
            )
            await saldar_si_corresponde(repos.base, presupuesto)
    except IntegrityError:
        raise ConflictoError(_MSG_COLISION) from None
    return await _a_cobro_out(repos, recibo), True


async def _asegurar_y_bloquear_para_cobro(
    repos: CajaRepos, hoy: date, actor: Actor, datos: CobroIn
) -> Caja | Recibo:
    """Toma la caja y relee la clave ANTES de revalidar el estado (D-25, paso 4 antes del 5)."""
    await repos.cajas.asegurar(hoy, actor.usuario_id)
    caja = await repos.cajas.por_fecha_para_actualizar(hoy)
    existente = await repos.recibos.por_clave(datos.clave_idempotencia)
    if existente is not None:
        return existente
    if caja is None:
        raise ConflictoError(_MSG_OTRA_ABIERTA)
    if caja.estado != "abierta":
        raise ConflictoError(_MSG_CERRADA)
    return caja


# --- cierre --------------------------------------------------------------------------------

async def cerrar(repos: CajaRepos, actor: Actor, datos: CierreIn) -> CajaOut:
    """Cierre definitivo: el servidor calcula el total y la diferencia (D-12)."""
    _exigir_rol(actor, "secretaria")
    caja = await repos.cajas.get_para_actualizar(datos.caja_id)
    if caja is None:
        raise NoEncontradoError("caja inexistente")
    if caja.estado != "abierta":
        raise ConflictoError("la caja ya está cerrada")
    total = await repos.cajas.total(caja.id)
    diferencia = datos.total_contado - total
    if diferencia != 0 and datos.motivo_diferencia is None:
        raise ValidacionClinicaError("la diferencia exige un motivo")
    await repos.cajas.actualizar(
        caja, estado="cerrada", total_sistema=total, total_contado=datos.total_contado,
        diferencia=diferencia,
        motivo_diferencia=datos.motivo_diferencia if diferencia != 0 else None,
        cerrada_por=actor.usuario_id, cerrada_at=_ahora(),
    )
    return await _a_caja_out(repos, caja)


# --- anulación -------------------------------------------------------------------------------

async def anular_recibo(
    repos: CajaRepos, actor: Actor, recibo_id: int, motivo: str, hoy: date | None = None,
) -> ReciboOut:
    """Contramovimiento en la caja de HOY; una caja cerrada nunca se toca (D-13)."""
    _exigir_rol(actor, "admin")
    hoy = hoy or hoy_operativo()
    await _caja_operable(repos, hoy)
    caja = await _asegurar_y_bloquear(repos, hoy, actor.usuario_id)
    recibo = await repos.recibos.get_para_actualizar(recibo_id)
    if recibo is None:
        raise NoEncontradoError("recibo inexistente")
    if recibo.anulado:
        raise ConflictoError("el recibo ya está anulado")
    pago = await repos.cuentas.pago_de_recibo(recibo.id)
    presupuesto = await repos.presupuestos.get_para_actualizar(pago.presupuesto_id)
    fecha_original = await repos.recibos.fecha_de(recibo.id)
    try:
        async with repos.cajas.sesion.begin_nested():
            await repos.cuentas.crear_movimiento(
                pago.cc_id, tipo="ajuste", monto=-pago.monto,
                concepto=f"Anulación del recibo {recibo.numero}", motivo=motivo,
                presupuesto_id=pago.presupuesto_id, recibo_id=recibo.id, anula_a_id=pago.id,
                creado_por=actor.usuario_id,
            )
            await repos.cajas.crear_movimiento(
                caja_id=caja.id, recibo_id=recibo.id, medio=recibo.medio, monto=-recibo.monto,
                motivo=motivo, creado_por=actor.usuario_id,
            )
            await repos.recibos.actualizar(
                recibo, anulado=True, motivo_anulacion=motivo, anulado_por=actor.usuario_id,
                anulado_at=_ahora(),
            )
            if presupuesto is not None and presupuesto.estado == "cobrado":
                await repos.presupuestos.actualizar(
                    presupuesto, estado="aceptado", updated_at=_ahora()
                )
    except IntegrityError:
        raise ConflictoError("el recibo ya está anulado") from None
    return await _a_recibo_out(repos, recibo, fecha=fecha_original)


# --- lecturas ----------------------------------------------------------------------------------

async def obtener_caja(
    repos: CajaRepos, actor: Actor, fecha: date | None = None, hoy: date | None = None,
) -> EstadoCajaOut:
    """Estado de la caja de `fecha` (o la pendiente / la de hoy); consultar no crea filas."""
    _exigir_rol(actor, "secretaria", "admin")
    hoy = hoy or hoy_operativo()
    pendiente = await repos.cajas.pendiente_anterior(hoy)
    caja_hoy = await repos.cajas.por_fecha(hoy)
    if fecha is not None:
        fecha_res, caja = fecha, await repos.cajas.por_fecha(fecha)
    elif pendiente is not None:
        fecha_res, caja = pendiente.fecha, pendiente
    else:
        fecha_res, caja = hoy, caja_hoy
    if pendiente is not None:
        bloqueo = "caja_pendiente"
    elif caja_hoy is not None and caja_hoy.estado == "cerrada":
        bloqueo = "caja_cerrada"
    else:
        bloqueo = None
    desglose: list[DesgloseMedioOut] = []
    ingresos: list[IngresoLiquidacionOut] = []
    caja_out = None
    if caja is not None:
        ingresos = [
            IngresoLiquidacionOut(
                liquidacion_id=lid, obra_social=nombre, periodo=periodo, medio=medio,
                monto=monto, created_at=creado,
            )
            for lid, nombre, periodo, medio, monto, creado
            in await repos.cajas.movimientos_de_liquidacion(caja.id)
        ]
        caja_out = await _a_caja_out(repos, caja)
        desglose = [
            DesgloseMedioOut(medio=medio, subtotal=subtotal)
            for medio, subtotal in (await repos.cajas.desglose(caja.id)).items()
        ]
    return EstadoCajaOut(
        fecha=fecha_res, hoy=hoy, operable=bloqueo is None, bloqueo=bloqueo,
        caja=caja_out, desglose=desglose, ingresos_liquidacion=ingresos,
    )


async def listar_recibos(repos: CajaRepos, actor: Actor, fecha: date) -> list[ReciboOut]:
    _exigir_rol(actor, "secretaria", "admin")
    filas = await repos.recibos.listar_por_fecha(fecha)
    return [await _a_recibo_out(repos, f.recibo, f.paciente_nombre, f.fecha) for f in filas]
