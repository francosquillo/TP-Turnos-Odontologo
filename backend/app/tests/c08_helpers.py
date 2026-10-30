"""Helpers C-08: mundo clínico ficticio sobre PG real (roles, usuarios, pacientes, catálogo).

Todo es ficticio. Los tests usan `create_all` (no la migración), por eso el
catálogo V1 se carga acá con `cargar_catalogo_estados`.
"""
import itertools
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from db_utils import cargar_catalogo_estados

_BASE_TURNO = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
_contador = itertools.count()


async def sembrar_mundo(sesion) -> SimpleNamespace:
    """Roles, 4 usuarios (admin, secretaria, 2 odontólogos), 2 profesionales, sillón, 2 pacientes."""
    from app.modelos import Paciente, Profesional, Rol, Sillon, Usuario

    await cargar_catalogo_estados(sesion)
    roles = {n: Rol(nombre=n) for n in ("admin", "odontologo", "secretaria")}
    sesion.add_all(roles.values())
    await sesion.flush()

    def usuario(nombre, email, rol):
        return Usuario(nombre=nombre, email=email, password_hash="no-login", rol_id=roles[rol].id)

    admin = usuario("Admin Demo", "admin@demo.test", "admin")
    secretaria = usuario("Secretaria Demo", "secretaria@demo.test", "secretaria")
    odo_a = usuario("Odonto A", "odo.a@demo.test", "odontologo")
    odo_b = usuario("Odonto B", "odo.b@demo.test", "odontologo")
    odo_sin_prof = usuario("Odonto Sin Perfil", "odo.c@demo.test", "odontologo")
    sesion.add_all([admin, secretaria, odo_a, odo_b, odo_sin_prof])
    await sesion.flush()

    prof_a = Profesional(matricula="DEMO-A", especialidades="Odontología general", usuario_id=odo_a.id)
    prof_b = Profesional(matricula="DEMO-B", especialidades="Ortodoncia", usuario_id=odo_b.id)
    sillon = Sillon(nombre="Sillón Demo")
    ana = Paciente(nombre="Ana", apellido="Ficticia", dni="30111222")
    beto = Paciente(nombre="Beto", apellido="Inventado", dni="30111333")
    sesion.add_all([prof_a, prof_b, sillon, ana, beto])
    await sesion.flush()
    return SimpleNamespace(
        admin=admin, secretaria=secretaria, odo_a=odo_a, odo_b=odo_b,
        odo_sin_prof=odo_sin_prof, prof_a=prof_a, prof_b=prof_b, sillon=sillon,
        ana=ana, beto=beto,
    )


async def crear_turno(sesion, paciente, profesional, sillon, estado="asistido"):
    """Turno ficticio en un horario único (los cancelados no entran al EXCLUDE)."""
    from app.modelos import Turno

    n = next(_contador)
    inicio = _BASE_TURNO + timedelta(hours=n)
    turno = Turno(
        paciente_id=paciente.id, profesional_id=profesional.id, sillon_id=sillon.id,
        inicio=inicio, fin=inicio + timedelta(minutes=30), estado=estado,
    )
    sesion.add(turno)
    await sesion.flush()
    return turno


async def armar_cliente(sesion):
    """App FastAPI real con `get_db` sobre la sesión PG del test.

    Confirma lo sembrado antes: los routers hacen `rollback()` ante un error de
    dominio y, sin commit previo, borrarían el mundo de la fixture.
    """
    from httpx import ASGITransport, AsyncClient

    from app.core.deps import get_db
    from app.core.security import crear_access_token
    from app.main import create_app

    await sesion.commit()
    app = create_app()

    async def _db():
        yield sesion

    app.dependency_overrides[get_db] = _db

    def bearer(usuario, rol: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {crear_access_token(usuario.id, rol)}"}

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), bearer, app
