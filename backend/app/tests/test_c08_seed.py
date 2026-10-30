"""C-08 grupo 6: seed demo de tratamientos y usuarios odontólogo/secretaria (D-10, D-11).

PG real. Idempotente, sin pisar datos existentes, contraseña desde env (Argon2).
Todo ficticio.
"""
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: E402, F401

PASSWORD = "demo-ficticia-123"


async def _contar(sesion, modelo):
    return await sesion.scalar(select(func.count()).select_from(modelo))


async def _base(sesion):
    from app.db.seed import seed_demo, seed_roles

    await seed_roles(sesion)
    return await seed_demo(sesion)


# --- 6.1 tratamientos -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_tratamientos_idempotente(sesion_pg):
    from app.db.seed import seed_tratamientos
    from app.modelos import Tratamiento

    await seed_tratamientos(sesion_pg)
    primera = await _contar(sesion_pg, Tratamiento)
    await seed_tratamientos(sesion_pg)
    assert primera == 6 and await _contar(sesion_pg, Tratamiento) == 6


@pytest.mark.asyncio
async def test_seed_tratamientos_datos_validos(sesion_pg):
    from app.db.seed import seed_tratamientos
    from app.modelos import Tratamiento

    await seed_tratamientos(sesion_pg)
    filas = (await sesion_pg.execute(select(Tratamiento))).scalars().all()
    assert len({t.codigo for t in filas}) == 6
    assert all(t.precio_base > 0 and t.nombre for t in filas)


@pytest.mark.asyncio
async def test_seed_no_pisa_precio_existente(sesion_pg):
    from app.db.seed import seed_tratamientos
    from app.modelos import Tratamiento

    await seed_tratamientos(sesion_pg)
    fila = (await sesion_pg.execute(select(Tratamiento).order_by(Tratamiento.codigo).limit(1))).scalar_one()
    fila_id = fila.id
    fila.precio_base = Decimal("12345.67")
    fila.nombre = "Editado a mano"
    await sesion_pg.flush()
    await seed_tratamientos(sesion_pg)
    sesion_pg.expire_all()
    despues = await sesion_pg.get(Tratamiento, fila_id)
    assert despues.precio_base == Decimal("12345.67") and despues.nombre == "Editado a mano"


# --- 6.2 usuarios demo -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_usuarios_demo_idempotente(sesion_pg):
    from app.db.seed import seed_usuarios_demo
    from app.modelos import Usuario

    await _base(sesion_pg)
    await seed_usuarios_demo(sesion_pg, PASSWORD)
    primera = await _contar(sesion_pg, Usuario)
    await seed_usuarios_demo(sesion_pg, PASSWORD)
    assert primera == 2 and await _contar(sesion_pg, Usuario) == 2


@pytest.mark.asyncio
async def test_seed_usuarios_demo_roles_emails_y_argon2(sesion_pg):
    from app.core.security import verificar_password
    from app.db.seed import seed_usuarios_demo
    from app.modelos import Rol, Usuario

    await _base(sesion_pg)
    await seed_usuarios_demo(sesion_pg, PASSWORD)
    filas = (await sesion_pg.execute(select(Usuario.email, Rol.nombre, Usuario.password_hash).join(Rol))).all()
    por_email = {e: (r, h) for e, r, h in filas}
    assert por_email["odontologo.demo@example.com"][0] == "odontologo"
    assert por_email["secretaria.demo@example.com"][0] == "secretaria"
    for _rol, hash_ in por_email.values():
        assert hash_.startswith("$argon2id$") and verificar_password(PASSWORD, hash_)


@pytest.mark.asyncio
async def test_seed_vincula_profesional_demo(sesion_pg):
    from app.db.seed import seed_usuarios_demo
    from app.modelos import Usuario

    _, profesional = await _base(sesion_pg)
    assert profesional.usuario_id is None
    await seed_usuarios_demo(sesion_pg, PASSWORD)
    odo = await sesion_pg.scalar(select(Usuario).where(Usuario.email == "odontologo.demo@example.com"))
    await sesion_pg.refresh(profesional)
    assert profesional.usuario_id == odo.id


@pytest.mark.asyncio
async def test_seed_respeta_vinculo_existente(sesion_pg):
    from app.db.seed import seed_usuarios_demo
    from app.modelos import Rol, Usuario

    _, profesional = await _base(sesion_pg)
    rol = await sesion_pg.scalar(select(Rol).where(Rol.nombre == "odontologo"))
    otro = Usuario(nombre="Otro Odonto", email="otro@demo.test", password_hash="x", rol_id=rol.id)
    sesion_pg.add(otro)
    await sesion_pg.flush()
    profesional.usuario_id = otro.id
    await sesion_pg.flush()
    await seed_usuarios_demo(sesion_pg, PASSWORD)
    await sesion_pg.refresh(profesional)
    assert profesional.usuario_id == otro.id


@pytest.mark.asyncio
@pytest.mark.parametrize("password", ["", None])
async def test_seed_sin_password_falla(sesion_pg, password):
    from app.db.seed import seed_usuarios_demo
    from app.modelos import Usuario

    await _base(sesion_pg)
    with pytest.raises(RuntimeError):
        await seed_usuarios_demo(sesion_pg, password)
    assert await _contar(sesion_pg, Usuario) == 0


@pytest.mark.asyncio
async def test_run_seed_incluye_lo_clinico_y_sigue_idempotente(sesion_pg, monkeypatch):
    from app.db.seed import run_seed
    from app.modelos import Tratamiento, Usuario

    monkeypatch.setenv("SEED_ADMIN_EMAIL", "admin@demo.test")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", PASSWORD)
    await run_seed(sesion_pg)
    primera = (await _contar(sesion_pg, Usuario), await _contar(sesion_pg, Tratamiento))
    await run_seed(sesion_pg)
    assert primera == (3, 6)
    assert (await _contar(sesion_pg, Usuario), await _contar(sesion_pg, Tratamiento)) == primera
