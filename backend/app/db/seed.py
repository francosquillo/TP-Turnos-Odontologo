"""Seed idempotente C-02/C-03: roles + admin + demo ficticia (D-04).

Guardas por clave natural (rol.nombre, usuario.email, sillon.nombre,
profesional.matricula) + transaccion ordenada: re-ejecutar no duplica
ni falla en uniques. Datos 100% ficticios (prefijo Demo).

Ademas carga datos demo ricos (ver `seed_demo`): ~29 pacientes, turnos relativos a hoy en todos
los estados, historias clinicas con odontograma, presupuestos y cobros con cajas pasadas cerradas
(sin notificaciones). Todo idempotente: re-ejecutar no duplica ni falla, tambien sobre una base ya
poblada (los huecos ocupados y los pacientes ya sembrados se respetan).

Admin inicial desde SEED_ADMIN_* con fail-fast (coherente con C-01 D-03).
Desde C-03 el hash es Argon2 (`hashear_password`); si el admin ya existe
con placeholder/bcrypt heredado se re-hashea una vez (idempotente).
"""
import asyncio
import os
import sys
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from typing import NamedTuple
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.seed_demo import seed_clinica_y_cobros, seed_turnos_demo
from app.modelos import (
    Arancel, Caja, CuentaCorriente, HallazgoOdontograma, HistoriaClinica, ItemPresupuesto,
    Movimiento, MovimientoCaja, ObraSocial, Paciente, Plan, Presupuesto, Profesional, Recibo,
    Rol, Sillon, Tratamiento, Turno, Usuario,
)

SILLON_DEMO_NOMBRE = "Sillón Demo 1"
PROFESIONAL_DEMO_MATRICULA = "DEMO-0001"
ODONTOLOGO_DEMO_EMAIL = "odontologo.demo@example.com"
SECRETARIA_DEMO_EMAIL = "secretaria.demo@example.com"
# (codigo, nombre, precio_base): catalogo de tratamientos ficticio (C-08, D-10/D-11).
TRATAMIENTOS_DEMO = (
    ("CON-001", "Consulta y diagnóstico", Decimal("8000.00")),
    ("PRO-001", "Limpieza y profilaxis", Decimal("12000.00")),
    ("OBT-001", "Obturación simple", Decimal("18000.00")),
    ("END-001", "Endodoncia unirradicular", Decimal("65000.00")),
    ("COR-001", "Corona de porcelana", Decimal("120000.00")),
    ("EXT-001", "Extracción simple", Decimal("15000.00")),
)
# C-11 (D-21): obra social ficticia con dos planes. EXT-001 queda SIN arancel a propósito, para
# mostrar la revisión manual; OBT-001 de Plan Base tiene una versión anterior cerrada (RN-OS-03);
# Plan Plus cubre PRO-001 al 100 % para mostrar `cobrado` sin recibo.
OBRA_SOCIAL_DEMO = "OS Ficticia Demo"
PLANES_DEMO = ("Plan Base", "Plan Plus")
NOMENCLADOR_DEMO = {
    "CON-001": "N-001", "PRO-001": "N-002", "OBT-001": "N-003",
    "END-001": "N-004", "COR-001": "N-005", "EXT-001": "N-006",
}
_INICIO_DEMO = date(2026, 1, 1)
# (plan, codigo del tratamiento, precio del arancel, vigencia_desde, vigencia_hasta)
ARANCELES_DEMO = (
    ("Plan Base", "CON-001", Decimal("5600.00"), _INICIO_DEMO, None),
    ("Plan Base", "PRO-001", Decimal("8400.00"), _INICIO_DEMO, None),
    ("Plan Base", "OBT-001", Decimal("9000.00"), _INICIO_DEMO, date(2026, 9, 30)),
    ("Plan Base", "OBT-001", Decimal("12600.00"), date(2026, 10, 1), None),
    ("Plan Base", "END-001", Decimal("45500.00"), _INICIO_DEMO, None),
    ("Plan Base", "COR-001", Decimal("84000.00"), _INICIO_DEMO, None),
    ("Plan Plus", "CON-001", Decimal("6800.00"), _INICIO_DEMO, None),
    ("Plan Plus", "PRO-001", Decimal("12000.00"), _INICIO_DEMO, None),
    ("Plan Plus", "OBT-001", Decimal("15300.00"), _INICIO_DEMO, None),
    ("Plan Plus", "END-001", Decimal("55250.00"), _INICIO_DEMO, None),
    ("Plan Plus", "COR-001", Decimal("102000.00"), _INICIO_DEMO, None),
)


AGENDA_DEMO = {
    "duracion_slot_min": 30,
    "horario": {
        "lunes": [["09:00", "13:00"], ["14:00", "18:00"]],
        "martes": [["09:00", "13:00"], ["14:00", "18:00"]],
        "miercoles": [["09:00", "13:00"], ["14:00", "18:00"]],
        "jueves": [["09:00", "13:00"], ["14:00", "18:00"]],
        "viernes": [["09:00", "13:00"], ["14:00", "18:00"]],
        "sabado": [["10:00", "13:00"]],
    },
}


class PacienteDemo(NamedTuple):
    nombre: str
    apellido: str
    dni: str
    telefono: str  # ya normalizado (solo digitos): la reserva online busca por este valor
    email: str
    plan: str | None


# C-12 (D-06): pacientes 100 % ficticios. DNI con prefijo de prueba 9000, telefonos
# `+54 9 11 0000-00xx` en digitos y emails @example.com. Dos con plan de la OS demo para
# recorrer la liquidacion; dos particulares. Desde el seed rico se suman ~25 mas (mezcla de planes y
# particulares). Los turnos, la clinica y los cobros/cajas los crea `seed_demo`.
_PACIENTES_BASE = (
    PacienteDemo("Lucía", "Demo Base", "90000001", "5491100000011", "lucia.demo@example.com", "Plan Base"),
    PacienteDemo("Mateo", "Demo Plus", "90000002", "5491100000012", "mateo.demo@example.com", "Plan Plus"),
    PacienteDemo("Sofía", "Demo Particular", "90000003", "5491100000013", "sofia.demo@example.com", None),
    PacienteDemo("Tomás", "Demo Particular", "90000004", "5491100000014", "tomas.demo@example.com", None),
)
# (nombre, apellido): ficticios; el plan rota Base / particular / Plus / particular / particular.
_NOMBRES_EXTRA = (
    ("Valentina", "Demo Gómez"), ("Santiago", "Demo Fernández"), ("Camila", "Demo Rodríguez"),
    ("Joaquín", "Demo López"), ("Martina", "Demo Díaz"), ("Benjamín", "Demo Martínez"),
    ("Julieta", "Demo Pérez"), ("Facundo", "Demo Romero"), ("Agustina", "Demo Sosa"),
    ("Nicolás", "Demo Álvarez"), ("Florencia", "Demo Torres"), ("Lautaro", "Demo Ruiz"),
    ("Carolina", "Demo Benítez"), ("Emiliano", "Demo Acosta"), ("Rocío", "Demo Medina"),
    ("Franco", "Demo Herrera"), ("Milagros", "Demo Suárez"), ("Ignacio", "Demo Aguirre"),
    ("Brenda", "Demo Giménez"), ("Matías", "Demo Molina"), ("Daniela", "Demo Castro"),
    ("Lucas", "Demo Ortiz"), ("Paula", "Demo Silva"), ("Gonzalo", "Demo Rojas"),
    ("Antonella", "Demo Núñez"),
)
_PLANES_EXTRA = ("Plan Base", None, "Plan Plus", None, None)


def _ascii(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "".join(c for c in sin_tildes.lower() if c.isalnum())


def _pacientes_extra() -> tuple[PacienteDemo, ...]:
    """DNI 90000005.., telefono 54911000000xx (digitos) y email @example.com, todo determinista."""
    return tuple(
        PacienteDemo(
            nombre, apellido, f"{90000005 + i}", f"54911000000{15 + i}",
            f"{_ascii(nombre)}.{_ascii(apellido)}@example.com", _PLANES_EXTRA[i % len(_PLANES_EXTRA)],
        )
        for i, (nombre, apellido) in enumerate(_NOMBRES_EXTRA)
    )


PACIENTES_DEMO = _PACIENTES_BASE + _pacientes_extra()


def _necesita_rehash(hash_guardado: str) -> bool:
    """True si el hash no es Argon2 (placeholder o bcrypt heredado, C-03)."""
    return not hash_guardado.startswith("$argon2")


async def seed_roles(sesion: AsyncSession) -> list[Rol]:
    """Crea los 3 roles fijos si faltan (Dueño=alias de Admin, sin tabla extra)."""
    roles: list[Rol] = []
    for nombre in ("admin", "odontologo", "secretaria"):
        existente = await sesion.scalar(select(Rol).where(Rol.nombre == nombre))
        if existente is None:
            existente = Rol(nombre=nombre)
            sesion.add(existente)
            await sesion.flush()
        roles.append(existente)
    return roles


async def seed_admin(sesion: AsyncSession, email: str, password_plano: str) -> Usuario:
    """Crea el admin inicial si falta; re-hashea a Argon2 si es heredado."""
    from app.core.security import hashear_password

    existente = await sesion.scalar(
        select(Usuario).where(func.lower(Usuario.email) == email.lower())
    )
    if existente is not None:
        if _necesita_rehash(existente.password_hash):
            existente.password_hash = hashear_password(password_plano)
            await sesion.flush()
        return existente
    rol_admin = await sesion.scalar(select(Rol).where(Rol.nombre == "admin"))
    if rol_admin is None:
        raise RuntimeError("seed_admin requiere seed_roles primero (falta rol admin)")
    admin = Usuario(
        nombre="Admin Demo",
        email=email,
        password_hash=hashear_password(password_plano),
        rol_id=rol_admin.id,
        activo=True,
    )
    sesion.add(admin)
    await sesion.flush()
    return admin


async def seed_demo(sesion: AsyncSession) -> tuple[Sillon, Profesional]:
    """Sillon + profesional demo con agenda_config semanal valida."""
    sillon = await sesion.scalar(
        select(Sillon).where(Sillon.nombre == SILLON_DEMO_NOMBRE)
    )
    if sillon is None:
        sillon = Sillon(nombre=SILLON_DEMO_NOMBRE)
        sesion.add(sillon)
        await sesion.flush()
    profesional = await sesion.scalar(
        select(Profesional).where(
            Profesional.matricula == PROFESIONAL_DEMO_MATRICULA
        )
    )
    if profesional is None:
        profesional = Profesional(
            matricula=PROFESIONAL_DEMO_MATRICULA,
            especialidades="Odontología general",
            usuario_id=None,
            agenda_config=AGENDA_DEMO,
        )
        sesion.add(profesional)
        await sesion.flush()
    elif profesional.agenda_config != AGENDA_DEMO:
        profesional.agenda_config = AGENDA_DEMO
        await sesion.flush()
    return sillon, profesional


async def seed_tratamientos(sesion: AsyncSession) -> int:
    """6 tratamientos ficticios; idempotente por `codigo` y sin pisar filas existentes."""
    for codigo, nombre, precio in TRATAMIENTOS_DEMO:
        if await sesion.scalar(select(Tratamiento.id).where(Tratamiento.codigo == codigo)) is None:
            sesion.add(Tratamiento(codigo=codigo, nombre=nombre, precio_base=precio))
    await sesion.flush()
    return await sesion.scalar(select(func.count()).select_from(Tratamiento))


async def seed_obras_sociales(sesion: AsyncSession, creado_por: int | None = None) -> int:
    """OS demo, planes y aranceles; idempotente por clave natural y sin pisar datos (D-21).

    Completa `codigo_nomenclador` solo si es NULL. Devuelve la cantidad de aranceles.
    """
    for codigo, nomenclador in NOMENCLADOR_DEMO.items():
        tratamiento = await sesion.scalar(select(Tratamiento).where(Tratamiento.codigo == codigo))
        if tratamiento is not None and tratamiento.codigo_nomenclador is None:
            tratamiento.codigo_nomenclador = nomenclador
    await sesion.flush()
    obra = await sesion.scalar(select(ObraSocial).where(ObraSocial.nombre == OBRA_SOCIAL_DEMO))
    if obra is None:
        obra = ObraSocial(nombre=OBRA_SOCIAL_DEMO)
        sesion.add(obra)
        await sesion.flush()
    planes: dict[str, Plan] = {}
    for nombre in PLANES_DEMO:
        plan = await sesion.scalar(
            select(Plan).where(Plan.obra_social_id == obra.id, Plan.nombre == nombre)
        )
        if plan is None:
            plan = Plan(obra_social_id=obra.id, nombre=nombre)
            sesion.add(plan)
            await sesion.flush()
        planes[nombre] = plan
    for plan_nombre, codigo, precio, desde, hasta in ARANCELES_DEMO:
        plan = planes[plan_nombre]
        # El código del arancel es el del tratamiento (si ya tenía otro, se respeta).
        tratamiento = await sesion.scalar(select(Tratamiento).where(Tratamiento.codigo == codigo))
        nomenclador = (
            tratamiento.codigo_nomenclador
            if tratamiento is not None and tratamiento.codigo_nomenclador is not None
            else NOMENCLADOR_DEMO[codigo]
        )
        existe = await sesion.scalar(select(Arancel.id).where(
            Arancel.plan_id == plan.id, Arancel.codigo_nomenclador == nomenclador,
            Arancel.vigencia_desde == desde,
        ))
        if existe is None:
            sesion.add(Arancel(
                plan_id=plan.id, codigo_nomenclador=nomenclador,
                descripcion=f"Arancel demo {codigo}", precio=precio, vigencia_desde=desde,
                vigencia_hasta=hasta, creado_por=creado_por,
                cerrado_por=creado_por if hasta is not None else None,
            ))
    await sesion.flush()
    return await sesion.scalar(select(func.count()).select_from(Arancel))


async def seed_pacientes_demo(sesion: AsyncSession) -> int:
    """Pacientes demo idempotentes por DNI; un paciente existente no se modifica (C-12, D-06).

    Requiere `seed_obras_sociales` antes (los planes). Devuelve el total de pacientes.
    """
    for demo in PACIENTES_DEMO:
        if await sesion.scalar(select(Paciente.id).where(Paciente.dni == demo.dni)) is not None:
            continue
        plan_id = None
        if demo.plan is not None:
            plan_id = await sesion.scalar(
                select(Plan.id)
                .join(ObraSocial, Plan.obra_social_id == ObraSocial.id)
                .where(ObraSocial.nombre == OBRA_SOCIAL_DEMO, Plan.nombre == demo.plan)
            )
            if plan_id is None:
                raise RuntimeError("seed_pacientes_demo requiere seed_obras_sociales primero")
        sesion.add(Paciente(
            nombre=demo.nombre, apellido=demo.apellido, dni=demo.dni, telefono=demo.telefono,
            email=demo.email, plan_id=plan_id,
        ))
    await sesion.flush()
    return await sesion.scalar(select(func.count()).select_from(Paciente))


async def _usuario_demo(sesion: AsyncSession, email: str, nombre: str, rol: str, password: str) -> Usuario:
    from app.core.security import hashear_password

    existente = await sesion.scalar(select(Usuario).where(func.lower(Usuario.email) == email))
    if existente is not None:
        return existente
    rol_fila = await sesion.scalar(select(Rol).where(Rol.nombre == rol))
    if rol_fila is None:
        raise RuntimeError(f"seed_usuarios_demo requiere seed_roles primero (falta rol {rol})")
    usuario = Usuario(
        nombre=nombre, email=email, password_hash=hashear_password(password),
        rol_id=rol_fila.id, activo=True,
    )
    sesion.add(usuario)
    await sesion.flush()
    return usuario


async def seed_usuarios_demo(sesion: AsyncSession, password: str | None) -> tuple[Usuario, Usuario]:
    """Odontologo y secretaria demo (D-11); vincula al profesional demo si no tiene usuario.

    La contrasena viene de SEED_ADMIN_PASSWORD (sin secreto nuevo ni literal en codigo).
    """
    if not password:
        raise RuntimeError("SEED_ADMIN_PASSWORD vacio: definir en .env (fail-fast, D-04)")
    odontologo = await _usuario_demo(
        sesion, ODONTOLOGO_DEMO_EMAIL, "Odontólogo Demo", "odontologo", password
    )
    secretaria = await _usuario_demo(
        sesion, SECRETARIA_DEMO_EMAIL, "Secretaria Demo", "secretaria", password
    )
    profesional = await sesion.scalar(
        select(Profesional).where(Profesional.matricula == PROFESIONAL_DEMO_MATRICULA)
    )
    if profesional is not None and profesional.usuario_id is None:
        profesional.usuario_id = odontologo.id
        await sesion.flush()
    return odontologo, secretaria


async def run_seed(sesion: AsyncSession, ahora: datetime | None = None) -> dict[str, int]:
    """Orden roles -> admin -> demo -> catalogos -> pacientes -> turnos -> clinica/cobros; commit unico.

    `ahora` (inyectable en tests) fija el "hoy" de las fechas relativas. Fail-fast sin password.
    """
    from zoneinfo import ZoneInfo

    from app.core.config import get_settings
    settings = get_settings()
    email = settings.seed_admin_email
    password = settings.seed_admin_password
    if not password:
        raise RuntimeError(
            "SEED_ADMIN_PASSWORD vacio: definir en .env (fail-fast, D-04)"
        )
    ahora = ahora or datetime.now(ZoneInfo(settings.tz))
    await seed_roles(sesion)
    await seed_admin(sesion, email=email, password_plano=password)
    sillon, profesional = await seed_demo(sesion)
    odontologo, secretaria = await seed_usuarios_demo(sesion, password)
    await seed_tratamientos(sesion)
    admin = await sesion.scalar(select(Usuario).where(func.lower(Usuario.email) == email.lower()))
    await seed_obras_sociales(sesion, None if admin is None else admin.id)
    await seed_pacientes_demo(sesion)
    await seed_turnos_demo(sesion, profesional, sillon, AGENDA_DEMO, ahora, secretaria.id)
    await seed_clinica_y_cobros(sesion, odontologo, secretaria, admin, profesional, ahora)
    await sesion.commit()

    async def contar(modelo) -> int:
        return await sesion.scalar(select(func.count()).select_from(modelo))

    return {
        "roles": await contar(Rol),
        "usuarios": await contar(Usuario),
        "sillones": await contar(Sillon),
        "profesionales": await contar(Profesional),
        "obras_sociales": await contar(ObraSocial),
        "planes": await contar(Plan),
        "aranceles": await contar(Arancel),
        "pacientes": await contar(Paciente),
        "turnos": await contar(Turno),
        "historias_clinicas": await contar(HistoriaClinica),
        "hallazgos": await contar(HallazgoOdontograma),
        "presupuestos": await contar(Presupuesto),
        "items_presupuesto": await contar(ItemPresupuesto),
        "cuentas_corrientes": await contar(CuentaCorriente),
        "movimientos_cuenta": await contar(Movimiento),
        "recibos": await contar(Recibo),
        "cajas": await contar(Caja),
        "movimientos_caja": await contar(MovimientoCaja),
    }


async def main() -> None:
    """Entry CLI: python -m app.db.seed (cwd=backend)."""
    from app.core.config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as sesion:
        conteos = await run_seed(sesion)
    await engine.dispose()
    print(f"seed ok: {conteos}")


if __name__ == "__main__":
    asyncio.run(main())


__all__ = [
    "seed_roles", "seed_admin", "seed_demo", "seed_usuarios_demo",
    "seed_tratamientos", "seed_obras_sociales", "seed_pacientes_demo", "PACIENTES_DEMO",
    "seed_turnos_demo", "seed_clinica_y_cobros", "run_seed", "main",
]
