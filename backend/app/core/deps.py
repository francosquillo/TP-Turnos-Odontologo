"""Dependencias reutilizables con Annotated (nunca `...` como default)."""
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]
