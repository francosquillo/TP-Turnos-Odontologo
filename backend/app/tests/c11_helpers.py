"""Helpers C-11: obras sociales, aranceles y presupuestos con cobertura sobre PG real.

Todo es ficticio. Las fixtures usan `create_all` (no la migración). El mundo se apoya en
`c10_helpers.sembrar_c10` (HC, hallazgos, tratamientos, usuarios).
"""
import itertools
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from c10_helpers import sembrar_c10

DESDE = date(2026, 1, 1)
# Códigos de nomenclador ficticios por tratamiento de c09_helpers.
NOMENCLADOR = {"CON-001": "N-001", "PRO-001": "N-002", "OBT-001": "N-003", "GRATIS": "N-004"}
_nombres = itertools.count(1)


async def crear_os(sesion, nombre: str | None = None, activa: bool = True):
    from app.modelos import ObraSocial

    os_ = ObraSocial(nombre=nombre or f"OS Ficticia {next(_nombres)}", activa=activa)
    sesion.add(os_)
    await sesion.flush()
    return os_


async def crear_plan(sesion, os_, nombre: str | None = None, activo: bool = True):
    from app.modelos import Plan

    plan = Plan(obra_social_id=os_.id, nombre=nombre or f"Plan {next(_nombres)}", activo=activo)
    sesion.add(plan)
    await sesion.flush()
    return plan


async def crear_arancel(sesion, plan, codigo: str, precio, *, desde: date = DESDE,
                        hasta: date | None = None, creado_por: int | None = None):
    from app.modelos import Arancel

    arancel = Arancel(
        plan_id=plan.id, codigo_nomenclador=codigo, descripcion=f"Prestación {codigo}",
        precio=Decimal(str(precio)), vigencia_desde=desde, vigencia_hasta=hasta,
        creado_por=creado_por,
    )
    sesion.add(arancel)
    await sesion.flush()
    return arancel


async def sembrar_c11(sesion) -> SimpleNamespace:
    """Mundo C-10 + nomenclador en los tratamientos + OS con dos planes y aranceles.

    Plan base: OBT-001 (precio 15000.00) con arancel 10500.00 (70 %); CON-001 (1000.50) con
    arancel 5000.00 (mayor al precio); PRO-001 sin arancel (revisión manual).
    """
    m = await sembrar_c10(sesion)
    for codigo, nomenclador in NOMENCLADOR.items():
        m.trat[codigo].codigo_nomenclador = nomenclador
    await sesion.flush()
    m.os = await crear_os(sesion, "OS Ficticia Demo")
    m.plan_base = await crear_plan(sesion, m.os, "Plan Base")
    m.plan_plus = await crear_plan(sesion, m.os, "Plan Plus")
    m.ar_obt = await crear_arancel(sesion, m.plan_base, "N-003", "10500.00",
                                   creado_por=m.admin.id)
    m.ar_con = await crear_arancel(sesion, m.plan_base, "N-001", "5000.00",
                                   creado_por=m.admin.id)
    m.ar_obt_plus = await crear_arancel(sesion, m.plan_plus, "N-003", "15000.00",
                                        creado_por=m.admin.id)
    return m


async def asignar_plan(sesion, paciente, plan) -> None:
    paciente.plan_id = plan.id if plan is not None else None
    await sesion.flush()




async def aceptar_presupuesto(sesion, m, items, *, plan=None, paciente=None, ahora=None):
    """Crea, presenta y acepta un presupuesto del odontólogo A y devuelve (presupuesto, repos).

    `items` es una lista de (hallazgo, codigo_tratamiento, cantidad). Si se pasa `plan`, se
    asigna al paciente antes de aceptar (el plan queda congelado en el presupuesto).
    """
    from datetime import datetime, timezone

    from app.esquemas.presupuesto import ItemIn
    from app.servicios import clinica_servicio as cs
    from app.servicios import presupuesto_servicio as ps

    ahora = ahora or datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)
    paciente = paciente or m.ana
    if plan is not None:
        await asignar_plan(sesion, paciente, plan)
    repos = ps.PresupuestoRepos.de_sesion(sesion)
    odo = cs.Actor(usuario_id=m.odo_a.id, rol="odontologo", profesional_id=m.prof_a.id)
    p = await ps.crear(repos, odo, paciente.id, [
        ItemIn(hallazgo_id=h.id, tratamiento_id=m.trat[codigo].id, cantidad=cant)
        for h, codigo, cant in items], ahora)
    await ps.presentar(repos, odo, p.id, ahora)
    p = await ps.aceptar(repos, odo, p.id, ahora)
    return p, repos


def actor_admin(m):
    from app.servicios.clinica_servicio import Actor

    return Actor(usuario_id=m.admin.id, rol="admin", profesional_id=None)


def actor_odontologo(m, *, b: bool = False):
    from app.servicios.clinica_servicio import Actor

    usuario, prof = (m.odo_b, m.prof_b) if b else (m.odo_a, m.prof_a)
    return Actor(usuario_id=usuario.id, rol="odontologo", profesional_id=prof.id)


def actor_secretaria(m):
    from app.servicios.clinica_servicio import Actor

    return Actor(usuario_id=m.secretaria.id, rol="secretaria", profesional_id=None)
