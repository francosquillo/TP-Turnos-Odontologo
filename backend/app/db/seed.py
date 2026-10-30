"""Seed idempotente C-02/C-03: roles + admin + demo ficticia (D-04).

Guardas por clave natural (rol.nombre, usuario.email, sillon.nombre,
profesional.matricula) + transaccion ordenada: re-ejecutar no duplica
ni falla en uniques. Datos 100% ficticios (prefijo Demo).

Admin inicial desde SEED_ADMIN_* con fail-fast (coherente con C-01 D-03).
Desde C-03 el hash es Argon2 (`hashear_password`); si el admin ya existe
con placeholder/bcrypt heredado se re-hashea una vez (idempotente).
"""
import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.modelos import Profesional, Rol, Sillon, Tratamiento, Usuario

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
AGENDA_DEMO = {
    "duracion_slot_min": 30,
    "horario": {
        "lunes": [["09:00", "13:00"], ["14:00", "18:00"]],
        "miercoles": [["09:00", "13:00"]],
        "viernes": [["09:00", "13:00"]],
    },
}


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
    return sillon, profesional


async def seed_tratamientos(sesion: AsyncSession) -> int:
    """6 tratamientos ficticios; idempotente por `codigo` y sin pisar filas existentes."""
    for codigo, nombre, precio in TRATAMIENTOS_DEMO:
        if await sesion.scalar(select(Tratamiento.id).where(Tratamiento.codigo == codigo)) is None:
            sesion.add(Tratamiento(codigo=codigo, nombre=nombre, precio_base=precio))
    await sesion.flush()
    return await sesion.scalar(select(func.count()).select_from(Tratamiento))


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


async def run_seed(sesion: AsyncSession) -> dict[str, int]:
    """Orden roles -> admin -> demo, con commit unico. Fail-fast sin password."""
    from app.core.config import get_settings

    settings = get_settings()
    email = settings.seed_admin_email
    password = settings.seed_admin_password
    if not password:
        raise RuntimeError(
            "SEED_ADMIN_PASSWORD vacio: definir en .env (fail-fast, D-04)"
        )
    await seed_roles(sesion)
    await seed_admin(sesion, email=email, password_plano=password)
    await seed_demo(sesion)
    await seed_usuarios_demo(sesion, password)
    await seed_tratamientos(sesion)
    await sesion.commit()
    return {
        "roles": await sesion.scalar(select(func.count()).select_from(Rol)),
        "usuarios": await sesion.scalar(select(func.count()).select_from(Usuario)),
        "sillones": await sesion.scalar(select(func.count()).select_from(Sillon)),
        "profesionales": await sesion.scalar(
            select(func.count()).select_from(Profesional)
        ),
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
    "seed_tratamientos", "run_seed", "main",
]
