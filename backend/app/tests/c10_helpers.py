"""Helpers C-10: caja, recibos y presupuestos aceptados sobre PG real.

Todo es ficticio. Las fixtures usan `create_all` (no la migración), por eso los
recibos de prueba se crean acá con una `clave_idempotencia` válida (D-25).
"""
import itertools
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from c09_helpers import sembrar_c09

_numeros = itertools.count(1)


def clave_nueva() -> str:
    """UUID v4 en minúsculas, como lo genera el cliente."""
    return str(uuid.uuid4())


async def sembrar_c10(sesion) -> SimpleNamespace:
    """Mundo C-09 (HC, hallazgos, tratamientos, usuarios) listo para cobrar."""
    return await sembrar_c09(sesion)


async def crear_caja(sesion, m, fecha: date, *, estado: str = "abierta", **extra):
    """Caja de prueba; una cerrada necesita totales completos."""
    from app.modelos import Caja

    datos = {"fecha": fecha, "abierta_por": m.secretaria.id, "estado": estado}
    if estado == "cerrada":
        datos.update(
            total_sistema=Decimal("0.00"), total_contado=Decimal("0.00"),
            diferencia=Decimal("0.00"), cerrada_por=m.secretaria.id,
            cerrada_at=extra.pop("cerrada_at", None) or _ahora(),
        )
    datos.update(extra)
    caja = Caja(**datos)
    sesion.add(caja)
    await sesion.flush()
    return caja


def _ahora():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


async def crear_recibo(sesion, m, *, numero: int | None = None, monto="100.00",
                       medio: str = "efectivo", paciente=None, clave: str | None = None,
                       **extra):
    """Recibo de prueba con número único y clave válida."""
    from app.modelos import Recibo

    recibo = Recibo(
        numero=numero if numero is not None else next(_numeros),
        paciente_id=(paciente or m.ana).id, monto=Decimal(str(monto)), medio=medio,
        emitido_por=m.secretaria.id, clave_idempotencia=clave or clave_nueva(), **extra,
    )
    sesion.add(recibo)
    await sesion.flush()
    return recibo


async def crear_cuenta(sesion, paciente):
    from app.modelos import CuentaCorriente

    cuenta = CuentaCorriente(paciente_id=paciente.id)
    sesion.add(cuenta)
    await sesion.flush()
    return cuenta


async def crear_presupuesto_aceptado(sesion, m, *, total="1000.00", paciente=None,
                                      con_cargo: bool = True, estado: str = "aceptado"):
    """Presupuesto sin ítems (no hacen falta para cobrar) con su cargo; devuelve (presupuesto, cuenta)."""
    from app.modelos import Movimiento, Presupuesto
    from app.repos.cuenta_repo import CuentaRepository

    paciente = paciente or m.ana
    extra = {"motivo_rechazo": "x"} if estado == "rechazado" else {}
    presupuesto = Presupuesto(
        paciente_id=paciente.id, profesional_id=m.prof_a.id, estado=estado,
        total=Decimal(str(total)), **extra,
    )
    sesion.add(presupuesto)
    await sesion.flush()
    cuenta = await CuentaRepository(sesion).asegurar(paciente.id)
    if con_cargo:
        sesion.add(Movimiento(
            cc_id=cuenta.id, tipo="cargo", monto=Decimal(str(total)),
            concepto=f"Presupuesto {presupuesto.id}", presupuesto_id=presupuesto.id,
            creado_por=m.odo_a.id,
        ))
        await sesion.flush()
    return presupuesto, cuenta


async def escenario_caja(sesion):
    """Mundo C-09 + servicio de caja + actores; devuelve (cs, repos, m, actores)."""
    from app.servicios import caja_servicio as cs
    from app.servicios.clinica_servicio import Actor

    m = await sembrar_c10(sesion)
    repos = cs.CajaRepos.de_sesion(sesion)
    actores = {
        "sec": Actor(usuario_id=m.secretaria.id, rol="secretaria", profesional_id=None),
        "admin": Actor(usuario_id=m.admin.id, rol="admin", profesional_id=None),
        "odo": Actor(usuario_id=m.odo_a.id, rol="odontologo", profesional_id=m.prof_a.id),
    }
    return cs, repos, m, actores


def cobro_in(presupuesto, monto="100.00", medio="efectivo", clave=None):
    from app.esquemas.caja import CobroIn

    return CobroIn(
        presupuesto_id=presupuesto.id, monto=Decimal(str(monto)), medio=medio,
        clave_idempotencia=clave or clave_nueva(),
    )


async def contar(sesion, tabla: str) -> int:
    import sqlalchemy as sa

    return await sesion.scalar(sa.text(f"SELECT count(*) FROM {tabla}"))
