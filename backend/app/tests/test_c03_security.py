"""C-03 task 1.1 RED: dependencias de auth en requirements.txt."""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_requirements_trae_auth_deps():
    """Task 1.1 RED: pyjwt + pwdlib[argon2] + freezegun declarados."""
    texto = (BACKEND_DIR / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "pyjwt" in texto
    assert "pwdlib[argon2]" in texto
    assert "freezegun" in texto


def test_imports_auth_disponibles():
    """Task 1.1: los imports que usa security.py existen en el entorno."""
    import jwt  # noqa: F401
    from pwdlib import PasswordHash  # noqa: F401


def test_hashear_nuevo_usa_argon2():
    """Task 1.2 RED: hash nuevo es Argon2id y verifica (ok y mala)."""
    from app.core.security import hashear_password, verificar_password

    obtenido = hashear_password("Secreta-123")
    assert obtenido.startswith("$argon2id$")
    assert verificar_password("Secreta-123", obtenido) is True
    assert verificar_password("otra-999", obtenido) is False


def test_verificar_acepta_bcrypt_heredado_y_rechaza_mala():
    """Task 1.2 RED: acepta $2b$ heredado, rechaza mala y basura sin excepcion."""
    import bcrypt

    from app.core.security import verificar_password

    heredado = bcrypt.hashpw("vieja-123".encode(), bcrypt.gensalt()).decode()
    assert heredado.startswith("$2b$")
    assert verificar_password("vieja-123", heredado) is True
    assert verificar_password("otra-999", heredado) is False
    assert verificar_password("x", "no-es-un-hash") is False


def test_access_ok_contiene_claims():
    """Task 1.3 RED: crear/verificar roundtrip con sub/rol y exp=+30min."""
    import jwt as pyjwt

    from app.core.security import crear_access_token, verificar_access_token

    token = crear_access_token(7, "secretaria")
    datos = verificar_access_token(token)
    assert datos["sub"] == 7
    assert datos["rol"] == "secretaria"
    crudo = pyjwt.decode(token, options={"verify_signature": False})
    assert crudo["exp"] - crudo["iat"] == 30 * 60
    assert crudo["sub"] == "7"


def test_access_expirado_rechazado_con_freezegun():
    """Task 1.3 RED: reloj avanzado >30min (+leeway) -> TokenExpiradoError."""
    from freezegun import freeze_time

    from app.core.security import (
        TokenError,
        TokenExpiradoError,
        crear_access_token,
        verificar_access_token,
    )

    assert issubclass(TokenExpiradoError, TokenError)
    with freeze_time("2026-10-01 12:00:00"):
        token = crear_access_token(3, "admin")
        verificar_access_token(token)
    with freeze_time("2026-10-01 12:30:20"):
        verificar_access_token(token)
    with freeze_time("2026-10-01 12:31:00"):
        with pytest.raises(TokenExpiradoError):
            verificar_access_token(token)


def test_access_firma_invalida_rechazado(monkeypatch):
    """Task 1.3 RED: firma con otro secret o basura -> TokenInvalidoError."""
    from app.core.security import (
        TokenInvalidoError,
        crear_access_token,
        verificar_access_token,
    )

    monkeypatch.setenv("JWT_SECRET", "a" * 32)
    token = crear_access_token(1, "admin")
    monkeypatch.setenv("JWT_SECRET", "b" * 32)
    with pytest.raises(TokenInvalidoError):
        verificar_access_token(token)
    with pytest.raises(TokenInvalidoError):
        verificar_access_token("basura.no-es-jwt")
