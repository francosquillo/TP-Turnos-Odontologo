"""Task 2.2 GREEN: configuracion solo por env (D-03), fail-fast sin secretos en codigo.

Reglas: pydantic-settings, JWT_EXPIRE_MIN=30, WHATSAPP_MOCK=true, TZ por defecto,
fail-fast si falta JWT_SECRET o DATABASE_URL (sin defaults inseguros).
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Solo environ (D-03 "config solo env"): Docker Compose inyecta .env via
    # env_file:/environment:. Sin env_file aca para que el fail-fast no quede
    # enmascarado por el fallback a .env (JWT_SECRET/DATABASE_URL obligatorios).
    model_config = SettingsConfigDict(extra="forbid")

    database_url: str = Field(min_length=1)
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = Field(min_length=1)
    jwt_expire_min: int = 30
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    whatsapp_webhook_secret: str = ""
    whatsapp_mock: bool = True
    gcal_client_id: str = ""
    gcal_secret: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = ""
    tz: str = "America/Argentina/Buenos_Aires"


def get_settings() -> Settings:
    """Fabrica sin cache: cada llamada relee el entorno (testeable con monkeypatch)."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
