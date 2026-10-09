"""C-03: hash Argon2id + JWT HS256 (reemplaza el stub C-01).

D-02: `pwdlib` Argon2id para hashes nuevos; verificacion acepta `$argon2*`
y `$2b$`/`$2y$` heredados (bcrypt solo lectura). NUNCA secreto en codigo:
firma y expiracion salen de env via `get_settings()`.
"""
import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

_hasher = PasswordHash((Argon2Hasher(), BcryptHasher()))

_LEEWAY_SEG = 30


class TokenError(Exception):
    """Access JWT ausente o ilegible (se mapea a 401)."""


class TokenExpiradoError(TokenError):
    """El `exp` quedo atras incluso con leeway (se mapea a 401)."""


class TokenInvalidoError(TokenError):
    """Firma incorrecta, claims rotos o formato ilegible (se mapea a 401)."""


def hashear_password(password_plana: str) -> str:
    """Hashea con Argon2id (todo hash nuevo sale `$argon2id$`)."""
    return _hasher.hash(password_plana)


def verificar_password(password_plana: str, hash_guardado: str) -> bool:
    """Verifica contra Argon2 o bcrypt heredado; basura/incorrecta -> False."""
    try:
        return _hasher.verify(password_plana, hash_guardado)
    except (PwdlibError, ValueError, AttributeError):
        return False


def crear_access_token(usuario_id: int, rol: str) -> str:
    """Firma HS256 con claims sub/rol/iat/exp (UTC, exp=+JWT_EXPIRE_MIN)."""
    from datetime import datetime, timedelta, timezone

    from app.core.config import get_settings

    ahora = datetime.now(timezone.utc)
    claims = {
        "sub": str(usuario_id),
        "rol": rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=get_settings().jwt_expire_min),
    }
    return jwt.encode(claims, get_settings().jwt_secret, algorithm="HS256")


def verificar_access_token(token: str) -> dict[str, object]:
    """Verifica firma + exp (leeway 30 s); expirado -> TokenExpiradoError."""
    from app.core.config import get_settings

    try:
        datos = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=["HS256"],
            leeway=_LEEWAY_SEG,
            options={"require": ["sub", "rol", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiradoError("access expirado") from exc
    except jwt.PyJWTError as exc:
        raise TokenInvalidoError("access invalido") from exc
    try:
        datos["sub"] = int(datos["sub"])
    except (ValueError, TypeError) as exc:
        raise TokenInvalidoError("claim sub no entero") from exc
    return datos
