"""C-03 task 3.3: seed admin con Argon2 (unit siempre + PG real con skip)."""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: F401  (fixture PG real con skip sin Docker)


def test_necesita_rehash_solo_si_no_es_argon2():
    """Task 3.3 RED (unit): placeholder/bcrypt -> True, argon2 -> False."""
    import bcrypt

    from app.db.seed import _necesita_rehash
    from app.core.security import hashear_password

    assert _necesita_rehash("sha256-placeholder$abc123") is True
    heredado = bcrypt.hashpw("x".encode(), bcrypt.gensalt()).decode()
    assert _necesita_rehash(heredado) is True
    assert _necesita_rehash(hashear_password("Secreta-123")) is False


@pytest.mark.asyncio
async def test_seed_admin_usa_argon2(sesion_pg, monkeypatch):
    """Task 3.3 RED (PG): doble seed -> hash Argon2 estable que verifica."""
    from sqlalchemy import select

    from app.core.security import verificar_password
    from app.db.seed import run_seed
    from app.modelos import Usuario

    monkeypatch.setenv("SEED_ADMIN_EMAIL", "admin@demo.test")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "demo-ficticia-123")
    await run_seed(sesion_pg)
    primero = await sesion_pg.scalar(
        select(Usuario).where(Usuario.email == "admin@demo.test")
    )
    assert primero.password_hash.startswith("$argon2id$")
    assert verificar_password("demo-ficticia-123", primero.password_hash) is True
    hash_primero = primero.password_hash
    await run_seed(sesion_pg)
    sesion_pg.expire_all()
    segundo = await sesion_pg.scalar(
        select(Usuario).where(Usuario.email == "admin@demo.test")
    )
    assert segundo.password_hash == hash_primero
