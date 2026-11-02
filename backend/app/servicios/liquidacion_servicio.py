"""Servicio de liquidaciones a obras sociales (C-11, D-02, D-09..D-13, D-16).

Reglas:
- `admin` opera todo (generar, presentar, descartar, cobrar, revertir, exportar). `odontologo`
  solo lista y consulta, y ve unicamente las filas de sus propios presupuestos. `secretaria`
  no accede (D-16).
- Una prestacion es un item de presupuesto aceptado (D-02). La fila copia los valores
  congelados al aceptar: plan, arancel y `cubierto`. Un item sin arancel es de revision
  manual, vale 0 y nunca se vuelve liquidable (D-11).
- `item_presupuesto_id` es UNIQUE: una colision concurrente cae en el indice y responde 409,
  sin locks (D-09). El savepoint deja todo sin tocar.
- Cobro y reversion pasan por `caja_para_movimiento` (D-12): orden de locks caja ->
  liquidacion, apertura implicita de la caja de hoy y 409 si hay caja pendiente o cerrada.
  Sin `clave_idempotencia`: el estado, con la fila bloqueada, cumple ese papel.

Solo hace `flush` (el router es dueno del commit). NO loguea nada: los motivos son datos
sensibles. Mensajes de error fijos, sin datos del paciente. Sin subclases de error.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.esquemas.liquidacion import (
    GenerarLiquidacionIn, ItemLiquidacionOut, LiquidacionDetalleOut, LiquidacionOut,
    PlanLiquidacionOut,
)
from app.modelos import Liquidacion
from app.repos.caja_repo import CajaRepository
from app.repos.liquidacion_repo import FilaDetalle, LiquidacionRepository
from app.servicios import caja_servicio as caja
from app.servicios.caja_servicio import (  # noqa: F401  (reexportados al router y a los tests)
    AccesoDenegadoError, Actor, ClinicaError, ConflictoError, NoEncontradoError,
    ValidacionClinicaError, construir_actor, hoy_operativo,
)

_CENTAVOS = Decimal("0.01")
_MSG_COLISION = "no se pudo registrar la operación, reintente"


@dataclass
class LiquidacionRepos:
    caja: caja.CajaRepos
    liquidaciones: LiquidacionRepository

    @property
    def clinica(self):
        return self.caja.clinica

    @property
    def cajas(self) -> CajaRepository:
        return self.caja.cajas

    @classmethod
    def de_sesion(cls, sesion) -> "LiquidacionRepos":
        return cls(caja=caja.CajaRepos.de_sesion(sesion), liquidaciones=LiquidacionRepository(sesion))


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().tz)


def limites_periodo(periodo: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[inicio, fin) del mes de `periodo` en la zona `tz`, como instantes con zona."""
    inicio = datetime(periodo.year, periodo.month, 1, tzinfo=tz)
    siguiente = (
        date(periodo.year + 1, 1, 1) if periodo.month == 12
        else date(periodo.year, periodo.month + 1, 1)
    )
    return inicio, datetime(siguiente.year, siguiente.month, 1, tzinfo=tz)


def monto_de_fila(arancel_id: int | None, cubierto: Decimal | None) -> Decimal:
    """Monto a presentar: lo congelado como cubierto; sin arancel, 0 (revision manual)."""
    if arancel_id is None or cubierto is None:
        return Decimal("0.00")
    return cubierto.quantize(_CENTAVOS)


def armar_planes(filas: list[FilaDetalle]) -> list[PlanLiquidacionOut]:
    """Agrupa por plan, con subtotal; las filas en revision no suman."""
    grupos: dict[int, PlanLiquidacionOut] = {}
    for fila in filas:
        grupo = grupos.get(fila.plan_id)
        if grupo is None:
            grupo = PlanLiquidacionOut(
                plan_id=fila.plan_id, plan_nombre=fila.plan_nombre,
                subtotal=Decimal("0.00"), items=[],
            )
            grupos[fila.plan_id] = grupo
        grupo.items.append(ItemLiquidacionOut(
            id=fila.item_id, item_presupuesto_id=fila.item_presupuesto_id,
            fecha_prestacion=fila.fecha_prestacion, paciente_nombre=fila.paciente_nombre,
            codigo=fila.codigo, descripcion=fila.descripcion, cantidad=fila.cantidad,
            monto=fila.monto, revision=fila.arancel_id is None,
        ))
        grupo.subtotal = (grupo.subtotal + fila.monto).quantize(_CENTAVOS)
    return list(grupos.values())


# --- acceso ------------------------------------------------------------------------------------

def _exigir_admin(actor: Actor) -> None:
    if actor.rol != "admin":
        raise AccesoDenegadoError("solo el administrador opera las liquidaciones")


def _filtro_profesional(actor: Actor) -> int | None:
    """None ve todo (admin); el odontologo solo sus presupuestos; el resto, 403."""
    if actor.rol == "admin":
        return None
    if actor.rol == "odontologo" and actor.profesional_id is not None:
        return actor.profesional_id
    raise AccesoDenegadoError("sin permiso sobre las liquidaciones")


# --- salidas ------------------------------------------------------------------------------------

def _resumen(liq: Liquidacion, os_nombre: str, filas: list[FilaDetalle], filtrada: bool) -> dict:
    total = sum((f.monto for f in filas), Decimal("0.00")) if filtrada else liq.total
    return dict(
        id=liq.id, os_id=liq.os_id, obra_social=os_nombre, periodo=liq.periodo,
        estado=liq.estado, total=Decimal(total).quantize(_CENTAVOS),
        cantidad_items=len(filas), cantidad_revision=sum(1 for f in filas if f.arancel_id is None),
        creada_por=liq.creada_por, presentada_at=liq.presentada_at, cobrada_at=liq.cobrada_at,
        cobro_revertido_at=liq.cobro_revertido_at, created_at=liq.created_at,
    )


async def _detalle(
    repos: LiquidacionRepos, liq: Liquidacion, os_nombre: str, profesional_id: int | None = None
) -> LiquidacionDetalleOut:
    filas = await repos.liquidaciones.filas(liq.id, profesional_id)
    return LiquidacionDetalleOut(
        **_resumen(liq, os_nombre, filas, profesional_id is not None),
        planes=armar_planes(filas), revertida=liq.cobro_revertido_at is not None,
    )


async def _cargar(repos: LiquidacionRepos, liquidacion_id: int) -> tuple[Liquidacion, str]:
    fila = await repos.liquidaciones.con_obra(liquidacion_id)
    if fila is None:
        raise NoEncontradoError("liquidación inexistente")
    return fila


# --- lecturas -------------------------------------------------------------------------------------

async def listar(repos: LiquidacionRepos, actor: Actor) -> list[LiquidacionOut]:
    profesional_id = _filtro_profesional(actor)
    salida: list[LiquidacionOut] = []
    for liq, os_nombre in await repos.liquidaciones.listar():
        filas = await repos.liquidaciones.filas(liq.id, profesional_id)
        if profesional_id is not None and not filas:
            continue
        salida.append(LiquidacionOut(**_resumen(liq, os_nombre, filas, profesional_id is not None)))
    return salida


async def obtener(repos: LiquidacionRepos, actor: Actor, liquidacion_id: int) -> LiquidacionDetalleOut:
    profesional_id = _filtro_profesional(actor)
    liq, os_nombre = await _cargar(repos, liquidacion_id)
    detalle = await _detalle(repos, liq, os_nombre, profesional_id)
    if profesional_id is not None and detalle.cantidad_items == 0:
        raise NoEncontradoError("liquidación inexistente")
    return detalle


# --- generacion -----------------------------------------------------------------------------------

async def generar(
    repos: LiquidacionRepos, actor: Actor, datos: GenerarLiquidacionIn
) -> LiquidacionDetalleOut:
    """Borrador con las prestaciones del periodo todavia no liquidadas; sin ellas, 409."""
    _exigir_admin(actor)
    obra = await repos.liquidaciones.obra_social_de(datos.os_id)
    if obra is None:
        raise NoEncontradoError("obra social inexistente")
    tz = _tz()
    inicio, fin = limites_periodo(datos.periodo, tz)
    candidatas = await repos.liquidaciones.candidatas(obra.id, inicio, fin)
    if not candidatas:
        raise ConflictoError("no hay prestaciones para liquidar en el período")
    try:
        async with repos.liquidaciones.sesion.begin_nested():
            liq = await repos.liquidaciones.crear(
                os_id=obra.id, periodo=datos.periodo, estado="borrador",
                total=Decimal("0.00"), creada_por=actor.usuario_id,
            )
            filas = [
                dict(
                    liquidacion_id=liq.id, item_presupuesto_id=c.item_presupuesto_id,
                    plan_id=c.plan_id, arancel_id=c.arancel_id,
                    fecha_prestacion=c.decidido_at.astimezone(tz).date(),
                    monto=monto_de_fila(c.arancel_id, c.cubierto),
                )
                for c in candidatas
            ]
            await repos.liquidaciones.agregar_items(filas)
            await repos.liquidaciones.actualizar(
                liq, total=sum((f["monto"] for f in filas), Decimal("0.00")).quantize(_CENTAVOS)
            )
    except IntegrityError:
        raise ConflictoError("una prestación ya fue liquidada") from None
    return await _detalle(repos, liq, obra.nombre)


# --- estados ----------------------------------------------------------------------------------------

async def presentar(
    repos: LiquidacionRepos, actor: Actor, liquidacion_id: int
) -> LiquidacionDetalleOut:
    _exigir_admin(actor)
    liq = await repos.liquidaciones.get_para_actualizar(liquidacion_id)
    if liq is None:
        raise NoEncontradoError("liquidación inexistente")
    if liq.estado != "borrador":
        raise ConflictoError("la liquidación no está en borrador")
    await repos.liquidaciones.actualizar(
        liq, estado="presentada", presentada_por=actor.usuario_id, presentada_at=_ahora()
    )
    _, os_nombre = await _cargar(repos, liq.id)
    return await _detalle(repos, liq, os_nombre)


async def descartar(repos: LiquidacionRepos, actor: Actor, liquidacion_id: int) -> None:
    """Borra un borrador y libera sus prestaciones (D-10)."""
    _exigir_admin(actor)
    liq = await repos.liquidaciones.get_para_actualizar(liquidacion_id)
    if liq is None:
        raise NoEncontradoError("liquidación inexistente")
    if liq.estado != "borrador":
        raise ConflictoError("solo se descarta una liquidación en borrador")
    await repos.liquidaciones.eliminar_con_items(liq)


# --- caja -----------------------------------------------------------------------------------------------

async def cobrar(
    repos: LiquidacionRepos, actor: Actor, liquidacion_id: int, medio: str,
    hoy: date | None = None,
) -> LiquidacionDetalleOut:
    """Ingreso por el total en la caja de hoy y paso a `cobrada`, en una transaccion (D-12)."""
    _exigir_admin(actor)
    hoy = hoy or hoy_operativo()
    caja_hoy = await caja.caja_para_movimiento(repos.caja, hoy, actor.usuario_id)
    liq = await repos.liquidaciones.get_para_actualizar(liquidacion_id)
    if liq is None:
        raise NoEncontradoError("liquidación inexistente")
    if liq.estado != "presentada" or liq.cobro_revertido_at is not None:
        raise ConflictoError("la liquidación no se puede cobrar")
    if liq.total <= 0:
        raise ConflictoError("la liquidación no tiene importe para cobrar")
    try:
        async with repos.liquidaciones.sesion.begin_nested():
            await repos.cajas.crear_movimiento(
                caja_id=caja_hoy.id, liquidacion_id=liq.id, medio=medio, monto=liq.total,
                creado_por=actor.usuario_id,
            )
            await repos.liquidaciones.actualizar(
                liq, estado="cobrada", cobrada_por=actor.usuario_id, cobrada_at=_ahora()
            )
    except IntegrityError:
        raise ConflictoError(_MSG_COLISION) from None
    _, os_nombre = await _cargar(repos, liq.id)
    return await _detalle(repos, liq, os_nombre)


async def revertir_cobro(
    repos: LiquidacionRepos, actor: Actor, liquidacion_id: int, motivo: str,
    hoy: date | None = None,
) -> LiquidacionDetalleOut:
    """Movimiento negativo en la caja de HOY con el medio original; una caja cerrada no se toca."""
    _exigir_admin(actor)
    hoy = hoy or hoy_operativo()
    caja_hoy = await caja.caja_para_movimiento(repos.caja, hoy, actor.usuario_id)
    liq = await repos.liquidaciones.get_para_actualizar(liquidacion_id)
    if liq is None:
        raise NoEncontradoError("liquidación inexistente")
    if liq.estado != "cobrada":
        raise ConflictoError("la liquidación no está cobrada")
    ingreso = await repos.cajas.ingreso_de_liquidacion(liq.id)
    if ingreso is None:
        raise ConflictoError("la liquidación no tiene un ingreso para revertir")
    try:
        async with repos.liquidaciones.sesion.begin_nested():
            await repos.cajas.crear_movimiento(
                caja_id=caja_hoy.id, liquidacion_id=liq.id, medio=ingreso.medio,
                monto=-ingreso.monto, motivo=motivo, creado_por=actor.usuario_id,
            )
            await repos.liquidaciones.actualizar(
                liq, estado="presentada", cobro_revertido_por=actor.usuario_id,
                cobro_revertido_at=_ahora(),
            )
    except IntegrityError:
        raise ConflictoError(_MSG_COLISION) from None
    _, os_nombre = await _cargar(repos, liq.id)
    return await _detalle(repos, liq, os_nombre)


# --- exportacion ----------------------------------------------------------------------------------------

async def para_exportar(
    repos: LiquidacionRepos, actor: Actor, liquidacion_id: int
) -> LiquidacionDetalleOut:
    """El informe en cualquier estado: solo `admin` (D-16, D-17)."""
    _exigir_admin(actor)
    liq, os_nombre = await _cargar(repos, liquidacion_id)
    return await _detalle(repos, liq, os_nombre)


__all__ = [
    "LiquidacionRepos", "armar_planes", "cobrar", "descartar", "generar", "limites_periodo",
    "listar", "monto_de_fila", "obtener", "para_exportar", "presentar", "revertir_cobro",
]
