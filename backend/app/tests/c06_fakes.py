"""Fakes C-06: Redis con NX, repos en memoria y clientes WhatsApp de prueba.

Sin PG/Redis: los tests de servicio usan estos fakes. Los tests contra
PG/Redis reales skipean sin Docker (compose down). Datos 100% ficticios;
telefonos de prueba nunca reales.
"""
import time
from types import SimpleNamespace

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c04_fakes import FakeTurnoRepo  # noqa: E402


class FakeRedis:
    """Redis en memoria con SET NX EX (barrera de idempotencia, D-03)."""

    def __init__(self) -> None:
        self._datos: dict[str, tuple[str, float | None]] = {}
        self.roto = False

    def _expirado(self, key: str) -> bool:
        if key not in self._datos:
            return True
        _, exp = self._datos[key]
        if exp is not None and exp <= time.monotonic():
            del self._datos[key]
            return True
        return False

    async def ping(self) -> bool:
        if self.roto:
            raise ConnectionError("redis roto (fake)")
        return True

    async def get(self, key: str):
        if self.roto:
            raise ConnectionError("redis roto (fake)")
        if key not in self._datos or self._expirado(key):
            return None
        return self._datos[key][0]

    async def set(self, key: str, value: str, ex=None, nx: bool = False):
        if self.roto:
            raise ConnectionError("redis roto (fake)")
        if nx and key in self._datos and not self._expirado(key):
            return None  # como redis real: no toma la clave
        exp = time.monotonic() + ex if ex else None
        self._datos[key] = (value, exp)
        return True

    async def delete(self, *keys: str) -> int:
        if self.roto:
            raise ConnectionError("redis roto (fake)")
        borrados = 0
        for key in keys:
            if key in self._datos:
                del self._datos[key]
                borrados += 1
        return borrados


class FakeNotifRepo:
    """NotificacionRepository en memoria con UNIQUE parcial (D-01)."""

    def __init__(self) -> None:
        self._filas: dict[int, SimpleNamespace] = {}
        self._seq = 0

    def _duplica_activa(self, turno_id: int, plantilla: str) -> bool:
        return any(
            f.turno_id == turno_id and f.plantilla == plantilla
            and f.estado != "fallida"
            for f in self._filas.values()
        )

    async def crear(self, **datos):
        from sqlalchemy.exc import IntegrityError

        if self._duplica_activa(datos["turno_id"], datos["plantilla"]):
            raise IntegrityError("insert notificacion", {}, Exception("duplicada"))
        self._seq += 1
        fila = SimpleNamespace(id=self._seq, **datos)
        fila.__dict__.setdefault("estado", "encolada")
        fila.__dict__.setdefault("costo", None)
        fila.__dict__.setdefault("intentos", 0)
        fila.__dict__.setdefault("ultimo_error", None)
        fila.__dict__.setdefault("destinatario_ref", None)
        self._filas[fila.id] = fila
        return fila

    async def actualizar(self, entidad, **cambios):
        for campo, valor in cambios.items():
            setattr(entidad, campo, valor)
        return entidad

    async def activa_de_turno(self, turno_id: int, plantilla: str):
        for fila in self._filas.values():
            if (fila.turno_id == turno_id and fila.plantilla == plantilla
                    and fila.estado != "fallida"):
                return fila
        return None

    async def por_message_id(self, message_id: str):
        for fila in self._filas.values():
            if getattr(fila, "payload", {}).get("message_id") == message_id:
                return fila
        return None

    async def fallida_de_turno(self, turno_id: int, plantilla: str):
        candidatas = [
            f for f in self._filas.values()
            if (f.turno_id == turno_id and f.plantilla == plantilla
                    and f.estado == "fallida")
        ]
        return max(candidatas, key=lambda f: f.id) if candidatas else None

    async def encoladas(self, limit: int = 100):
        return [f for f in sorted(self._filas.values(), key=lambda f: f.id)
                if f.estado == "encolada"][:limit]

    async def fallidas(self, limit: int = 50, offset: int = 0):
        filas = sorted(
            (f for f in self._filas.values() if f.estado == "fallida"),
            key=lambda f: f.id, reverse=True,
        )
        return filas[offset:offset + limit]

    def cantidad_activas(self) -> int:
        return sum(1 for f in self._filas.values() if f.estado != "fallida")


class FakeTurnoRepoC06(FakeTurnoRepo):
    """FakeTurnoRepo + busqueda por hash (C-05) y por estado/rango (C-06)."""

    async def por_token_hash(self, token_hash: str):
        for turno in self._turnos.values():
            if getattr(turno, "token_confirmacion_hash", None) == token_hash:
                return turno
        return None

    async def por_estado_y_rango(self, estados, desde, hasta):
        salida = [
            t for t in self._turnos.values()
            if t.estado in estados and t.inicio >= desde and t.inicio < hasta
        ]
        return sorted(salida, key=lambda t: t.inicio)


class FallaCliente:
    """WhatsApp que siempre falla (prueba reintentos + fallback)."""

    def __init__(self, motivo: str = "timeout demo") -> None:
        self.motivo = motivo
        self.llamados = 0

    async def enviar(self, destinatario, plantilla, variables):
        from app.servicios.whatsapp_cliente import EnvioFallidoError

        self.llamados += 1
        raise EnvioFallidoError(self.motivo)


class CuentaCliente:
    """WhatsApp que cuenta envios y responde enviada (prueba idempotencia)."""

    def __init__(self, costo: float = 0.0) -> None:
        from app.servicios.whatsapp_cliente import ResultadoEnvio

        self._ResultadoEnvio = ResultadoEnvio
        self.costo = costo
        self.envios: list[dict] = []

    async def enviar(self, destinatario, plantilla, variables):
        self.envios.append(
            {"destinatario": destinatario, "plantilla": plantilla,
             "variables": dict(variables)}
        )
        return self._ResultadoEnvio(
            estado="enviada", message_id=f"test-uuid-{len(self.envios)}",
            costo=self.costo,
        )


def fabricar_turno_c06(id: int = 1, **cambios) -> SimpleNamespace:
    from datetime import datetime, timedelta, timezone

    from c04_fakes import fabricar_turno

    base = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
    datos = {"inicio": base, "fin": base + timedelta(minutes=30)}
    datos.update(cambios)
    return fabricar_turno(id, **datos)
