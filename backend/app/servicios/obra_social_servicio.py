"""Servicio de obras sociales, planes, aranceles y validador (C-11, D-04, D-07, D-08, D-16).

Reglas:
- Lectura de catálogos: todo el personal autenticado. Escritura: solo `admin`.
- Sin borrado físico: la baja es `activa=False` / `activo=False`.
- El precio de un arancel es inmutable; solo se cierra la vigencia (autor y fecha en la fila).
- `PUT /pacientes/:id/plan` y el validador: `secretaria` y `admin`; el validador no crea filas.

Solo hace `flush` (el router es dueño del commit). NO loguea nada. Mensajes de error fijos.
Sin subclases de error: `a_http` busca el tipo exacto.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.esquemas.obra_social import (
    ArancelIn, ArancelOut, ObraSocialIn, ObraSocialOut, ObraSocialPatch, PlanIn, PlanOut,
    PlanPacienteOut, PlanPatch, ValidadorCoberturaOut,
)
from app.modelos import Arancel, ObraSocial, Plan
from app.repos.obra_social_repo import (
    ArancelRepository, ObraSocialRepository, PlanConObra, PlanRepository,
)
from app.repos.tratamiento_repo import TratamientoRepository
from app.servicios import clinica_servicio as cs
from app.servicios.clinica_servicio import (  # noqa: F401  (reexportados al router y a los tests)
    AccesoDenegadoError, Actor, ClinicaError, ConflictoError, NoEncontradoError,
    ValidacionClinicaError, construir_actor,
)
from app.servicios.cobertura_servicio import calcular_cobertura

_CERO = Decimal("0.00")


@dataclass
class ObraSocialRepos:
    clinica: cs.ClinicaRepos
    obras: ObraSocialRepository
    planes: PlanRepository
    aranceles: ArancelRepository
    tratamientos: TratamientoRepository

    @classmethod
    def de_sesion(cls, sesion) -> "ObraSocialRepos":
        return cls(
            clinica=cs.ClinicaRepos.de_sesion(sesion),
            obras=ObraSocialRepository(sesion),
            planes=PlanRepository(sesion),
            aranceles=ArancelRepository(sesion),
            tratamientos=TratamientoRepository(sesion),
        )


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _exigir_admin(actor: Actor) -> None:
    if actor.rol != "admin":
        raise AccesoDenegadoError("solo el administrador modifica el catálogo")


def _exigir_personal(actor: Actor) -> None:
    if actor.rol not in ("admin", "secretaria", "odontologo"):
        raise AccesoDenegadoError("sin permiso sobre el catálogo")


# --- salidas -------------------------------------------------------------------------------

def _os_out(obra: ObraSocial) -> ObraSocialOut:
    return ObraSocialOut(
        id=obra.id, nombre=obra.nombre, activa=obra.activa, created_at=obra.created_at
    )


def _plan_out(plan: Plan, obra: ObraSocial) -> PlanOut:
    return PlanOut(
        id=plan.id, obra_social_id=plan.obra_social_id, obra_social_nombre=obra.nombre,
        nombre=plan.nombre, activo=plan.activo, created_at=plan.created_at,
    )


def _arancel_out(arancel: Arancel) -> ArancelOut:
    return ArancelOut(
        id=arancel.id, plan_id=arancel.plan_id, codigo_nomenclador=arancel.codigo_nomenclador,
        descripcion=arancel.descripcion, precio=arancel.precio,
        vigencia_desde=arancel.vigencia_desde, vigencia_hasta=arancel.vigencia_hasta,
        creado_por=arancel.creado_por, cerrado_por=arancel.cerrado_por,
        cerrado_at=arancel.cerrado_at, created_at=arancel.created_at,
    )


# --- obras sociales --------------------------------------------------------------------------

async def listar_obras(repos: ObraSocialRepos, actor: Actor) -> list[ObraSocialOut]:
    _exigir_personal(actor)
    return [_os_out(o) for o in await repos.obras.listar()]


async def crear_obra(repos: ObraSocialRepos, actor: Actor, datos: ObraSocialIn) -> ObraSocialOut:
    _exigir_admin(actor)
    try:
        async with repos.obras.sesion.begin_nested():
            obra = await repos.obras.crear(nombre=datos.nombre)
    except IntegrityError:
        raise ConflictoError("ya existe una obra social con ese nombre") from None
    return _os_out(obra)


async def editar_obra(
    repos: ObraSocialRepos, actor: Actor, obra_id: int, datos: ObraSocialPatch
) -> ObraSocialOut:
    _exigir_admin(actor)
    obra = await repos.obras.get(obra_id)
    if obra is None:
        raise NoEncontradoError("obra social inexistente")
    cambios = datos.model_dump(exclude_unset=True, exclude_none=True)
    try:
        async with repos.obras.sesion.begin_nested():
            await repos.obras.actualizar(obra, **cambios)
    except IntegrityError:
        raise ConflictoError("ya existe una obra social con ese nombre") from None
    return _os_out(obra)


# --- planes ------------------------------------------------------------------------------------

async def listar_planes(
    repos: ObraSocialRepos, actor: Actor, obra_social_id: int | None = None
) -> list[PlanOut]:
    _exigir_personal(actor)
    return [_plan_out(f.plan, f.obra_social) for f in await repos.planes.listar(obra_social_id)]


async def crear_plan(repos: ObraSocialRepos, actor: Actor, datos: PlanIn) -> PlanOut:
    _exigir_admin(actor)
    obra = await repos.obras.get(datos.obra_social_id)
    if obra is None:
        raise NoEncontradoError("obra social inexistente")
    try:
        async with repos.planes.sesion.begin_nested():
            plan = await repos.planes.crear(obra_social_id=obra.id, nombre=datos.nombre)
    except IntegrityError:
        raise ConflictoError("ya existe un plan con ese nombre en la obra social") from None
    return _plan_out(plan, obra)


async def editar_plan(
    repos: ObraSocialRepos, actor: Actor, plan_id: int, datos: PlanPatch
) -> PlanOut:
    _exigir_admin(actor)
    fila = await repos.planes.con_obra(plan_id)
    if fila is None:
        raise NoEncontradoError("plan inexistente")
    cambios = datos.model_dump(exclude_unset=True, exclude_none=True)
    try:
        async with repos.planes.sesion.begin_nested():
            await repos.planes.actualizar(fila.plan, **cambios)
    except IntegrityError:
        raise ConflictoError("ya existe un plan con ese nombre en la obra social") from None
    return _plan_out(fila.plan, fila.obra_social)


# --- aranceles ----------------------------------------------------------------------------------

async def listar_aranceles(
    repos: ObraSocialRepos, actor: Actor, plan_id: int | None = None, codigo: str | None = None,
) -> list[ArancelOut]:
    _exigir_personal(actor)
    return [_arancel_out(a) for a in await repos.aranceles.listar(plan_id, codigo)]


async def crear_arancel(repos: ObraSocialRepos, actor: Actor, datos: ArancelIn) -> ArancelOut:
    _exigir_admin(actor)
    if await repos.planes.get(datos.plan_id) is None:
        raise NoEncontradoError("plan inexistente")
    try:
        async with repos.aranceles.sesion.begin_nested():
            arancel = await repos.aranceles.crear(
                plan_id=datos.plan_id, codigo_nomenclador=datos.codigo_nomenclador,
                descripcion=datos.descripcion, precio=datos.precio,
                vigencia_desde=datos.vigencia_desde, vigencia_hasta=datos.vigencia_hasta,
                creado_por=actor.usuario_id,
                cerrado_por=actor.usuario_id if datos.vigencia_hasta is not None else None,
                cerrado_at=_ahora() if datos.vigencia_hasta is not None else None,
            )
    except IntegrityError:
        raise ConflictoError("la vigencia se superpone con otro arancel") from None
    return _arancel_out(arancel)


async def cerrar_arancel(
    repos: ObraSocialRepos, actor: Actor, arancel_id: int, vigencia_hasta: date
) -> ArancelOut:
    """Cierra la vigencia (único cambio permitido) y registra quién y cuándo."""
    _exigir_admin(actor)
    arancel = await repos.aranceles.get_para_actualizar(arancel_id)
    if arancel is None:
        raise NoEncontradoError("arancel inexistente")
    if vigencia_hasta < arancel.vigencia_desde:
        raise ValidacionClinicaError("vigencia_hasta no puede ser anterior a vigencia_desde")
    try:
        async with repos.aranceles.sesion.begin_nested():
            await repos.aranceles.actualizar(
                arancel, vigencia_hasta=vigencia_hasta, cerrado_por=actor.usuario_id,
                cerrado_at=_ahora(),
            )
    except IntegrityError:
        raise ConflictoError("la vigencia se superpone con otro arancel") from None
    return _arancel_out(arancel)


# --- plan del paciente ---------------------------------------------------------------------------

def _exigir_caja_o_admin(actor: Actor) -> None:
    if actor.rol not in ("secretaria", "admin"):
        raise AccesoDenegadoError("sin permiso sobre la cobertura")


async def _paciente_activo(repos: ObraSocialRepos, paciente_id: int):
    paciente = await repos.clinica.pacientes.get(paciente_id)
    if paciente is None or paciente.deleted_at is not None:
        raise NoEncontradoError("paciente inexistente")
    return paciente


async def asignar_plan(
    repos: ObraSocialRepos, actor: Actor, paciente_id: int, plan_id: int | None
) -> PlanPacienteOut:
    """Asigna o quita el plan; un plan inexistente o inactivo es 409 (D-07)."""
    _exigir_caja_o_admin(actor)
    paciente = await _paciente_activo(repos, paciente_id)
    fila: PlanConObra | None = None
    if plan_id is not None:
        fila = await repos.planes.con_obra(plan_id)
        if fila is None or not fila.plan.activo or not fila.obra_social.activa:
            raise ConflictoError("el plan no existe o está inactivo")
    await repos.clinica.pacientes.actualizar(paciente, plan_id=plan_id)
    return PlanPacienteOut(
        paciente_id=paciente.id, plan_id=plan_id,
        plan_nombre=None if fila is None else fila.plan.nombre,
        obra_social_id=None if fila is None else fila.obra_social.id,
        obra_social_nombre=None if fila is None else fila.obra_social.nombre,
    )


async def obtener_plan_paciente(
    repos: ObraSocialRepos, actor: Actor, paciente_id: int
) -> PlanPacienteOut:
    _exigir_caja_o_admin(actor)
    paciente = await _paciente_activo(repos, paciente_id)
    fila = None if paciente.plan_id is None else await repos.planes.con_obra(paciente.plan_id)
    return PlanPacienteOut(
        paciente_id=paciente.id, plan_id=paciente.plan_id,
        plan_nombre=None if fila is None else fila.plan.nombre,
        obra_social_id=None if fila is None else fila.obra_social.id,
        obra_social_nombre=None if fila is None else fila.obra_social.nombre,
    )


# --- validador ------------------------------------------------------------------------------------

async def validar_cobertura(
    repos: ObraSocialRepos, actor: Actor, paciente_id: int, tratamiento_id: int, hoy: date,
) -> ValidadorCoberturaOut:
    """Estado de cobertura de un tratamiento con el arancel de `hoy`; no crea filas."""
    _exigir_caja_o_admin(actor)
    paciente = await _paciente_activo(repos, paciente_id)
    tratamiento = await repos.tratamientos.get(tratamiento_id)
    if tratamiento is None:
        raise NoEncontradoError("tratamiento inexistente")
    precio = tratamiento.precio_base

    def salida(estado, plan_id, arancel, cobertura) -> ValidadorCoberturaOut:
        return ValidadorCoberturaOut(
            estado=estado, paciente_id=paciente.id, tratamiento_id=tratamiento.id,
            plan_id=plan_id, precio=precio, arancel=arancel, cubierto=cobertura.cubierto,
            a_cargo=cobertura.a_cargo, porcentaje=cobertura.porcentaje, fecha=hoy,
        )

    sin_cobertura = calcular_cobertura(None, precio, 1)
    fila = None if paciente.plan_id is None else await repos.planes.con_obra(paciente.plan_id)
    if fila is None or not fila.plan.activo or not fila.obra_social.activa:
        return salida("sin_plan", None, None, sin_cobertura)
    arancel = None
    if tratamiento.codigo_nomenclador is not None:
        arancel = await repos.aranceles.arancel_vigente(
            fila.plan.id, tratamiento.codigo_nomenclador, hoy
        )
    if arancel is None:
        return salida("sin_arancel", fila.plan.id, None, sin_cobertura)
    return salida(
        "cubierto", fila.plan.id, arancel.precio, calcular_cobertura(arancel.precio, precio, 1)
    )


__all__ = [
    "ObraSocialRepos", "asignar_plan", "cerrar_arancel", "crear_arancel", "crear_obra",
    "crear_plan", "editar_obra", "editar_plan", "listar_aranceles", "listar_obras",
    "listar_planes", "obtener_plan_paciente", "validar_cobertura",
]
