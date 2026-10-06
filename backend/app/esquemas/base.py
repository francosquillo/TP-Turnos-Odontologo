"""Esquemas base: estrictos por defecto (extra='forbid', regla dura)."""
from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
