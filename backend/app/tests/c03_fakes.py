"""Fakes C-03: store Redis en memoria + repo usuarios en memoria.

Los tests HTTP usan `dependency_overrides` con estos fakes (corren sin
Docker); los tests de integracion contra PG/Redis reales viven en los
archivos test_c03_* con sufijo `_integracion` y skipean sin servicios.
"""
import time
from types import SimpleNamespace


class FakeStore:
    """SesionStore en memoria con expiracion (ex en segundos)."""

    def __init__(self) -> None:
        self._datos: dict[str, tuple[str, float | None]] = {}
        self.roto = False

    def _expirado(self, key: str) -> bool:
        _, exp = self._datos[key]
        if exp is not None and exp <= time.monotonic():
            del self._datos[key]
            return True
        return False

    async def ping(self) -> bool:
        if self.roto:
            raise ConnectionError("redis roto (fake)")
        return True

    async def get(self, key: str) -> str | None:
        if self.roto:
            raise ConnectionError("redis roto (fake)")
        if key not in self._datos or self._expirado(key):
            return None
        return self._datos[key][0]

    async def getdel(self, key: str) -> str | None:
        valor = await self.get(key)
        self._datos.pop(key, None)
        return valor

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        if self.roto:
            raise ConnectionError("redis roto (fake)")
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


class FakeRepo:
    """Repo usuarios en memoria (respeta la interfaz usada por servicios)."""

    def __init__(self, usuarios: list[SimpleNamespace] | None = None) -> None:
        self._usuarios: dict[int, SimpleNamespace] = {}
        for usuario in usuarios or []:
            self._usuarios[usuario.id] = usuario

    def _con_rol(self, usuario: SimpleNamespace | None):
        return usuario

    async def get(self, id: int):
        return self._con_rol(self._usuarios.get(id))

    async def obtener_por_email(self, email: str):
        for usuario in self._usuarios.values():
            if usuario.email.lower() == email.lower():
                return self._con_rol(usuario)
        return None

    async def obtener_con_rol(self, usuario_id: int):
        return self._con_rol(self._usuarios.get(usuario_id))

    async def listar_todos_con_rol(self):
        return [self._con_rol(u) for u in sorted(self._usuarios.values(), key=lambda u: u.id)]

    async def listar_admins_activos(self):
        return [
            u for u in self._usuarios.values()
            if u.activo is True and u.rol.nombre == "admin"
        ]

    async def actualizar(self, entidad, **cambios):
        for campo, valor in cambios.items():
            setattr(entidad, campo, valor)
        return entidad

    async def eliminar(self, entidad) -> None:
        self._usuarios.pop(entidad.id, None)


def fabricar_usuario(
    id: int = 1,
    rol: str = "secretaria",
    activo: bool = True,
    email: str = "secre@demo.test",
    password_plana: str = "Secreta-123",
) -> SimpleNamespace:
    from app.core.security import hashear_password

    return SimpleNamespace(
        id=id,
        nombre=f"Usuaria {id}",
        email=email,
        password_hash=hashear_password(password_plana),
        rol=SimpleNamespace(nombre=rol),
        activo=activo,
    )
