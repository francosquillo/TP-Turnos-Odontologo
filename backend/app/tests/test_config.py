"""Task 2.2: core/config.py con pydantic-settings, fail-fast, defaults.

Orden-independientes: cada test fuerza re-ejecucion del modulo con su propio
entorno (pop de sys.modules + import dentro del try), sin depender de que otro
test haya importado antes.
"""
import importlib
import sys
from pathlib import Path

from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _importar_config_fresco():
    sys.modules.pop("app.core.config", None)
    return importlib.import_module("app.core.config")


def test_config_falla_sin_jwt_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/t")
    try:
        _importar_config_fresco()
    except ValidationError as exc:
        assert "JWT_SECRET" in str(exc).upper()
    else:
        raise AssertionError("debió fallar sin JWT_SECRET")


def test_config_falla_sin_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    try:
        _importar_config_fresco()
    except ValidationError as exc:
        assert "DATABASE_URL" in str(exc).upper()
    else:
        raise AssertionError("debió fallar sin DATABASE_URL")


def test_config_defaults(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "s" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/t")
    config_mod = _importar_config_fresco()
    settings = config_mod.get_settings()
    assert settings.jwt_expire_min == 30
    assert settings.whatsapp_mock is True
    assert settings.tz == "America/Argentina/Buenos_Aires"
    assert settings.cors_origins == ["http://localhost:5173"]
