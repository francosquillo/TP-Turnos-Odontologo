"""Jobs de notificaciones del worker (C-06, D-04).

Sin HTTP directo: delegan en `notificacion_servicio` + `whatsapp_cliente`
(mismo orden de repos que el servicio). El scheduler (`main.bucle_notif`)
los llama cada hora; al arranque, main corre `barrido_recuperacion` (ventana
extendida ±60 min = [47h,49h]/[23h,25h]) para cubrir caidas de hasta ~1 h
(huecos mayores: hueco aceptado v1.0, los turnos siguen confirmables por
link C-05).
"""
from datetime import datetime

from app.servicios import notificacion_servicio as servicio

VENTANA_RECUPERACION_MIN = 60


async def barrido_recordatorios(
    turnos_repo,
    notif_repo,
    pacientes_repo,
    tienda,
    cliente,
    ahora: datetime | None = None,
) -> dict[str, int]:
    """Tick horario: delega el barrido 48/24 h (ventana ±30 min)."""
    return await servicio.barrido_recordatorios(
        turnos_repo, notif_repo, pacientes_repo, tienda, cliente, ahora=ahora
    )


async def barrido_recuperacion(
    turnos_repo,
    notif_repo,
    pacientes_repo,
    tienda,
    cliente,
    ahora: datetime | None = None,
) -> dict[str, int]:
    """Barrido unico al arranque con ventana extendida (D-04)."""
    return await servicio.barrido_recordatorios(
        turnos_repo, notif_repo, pacientes_repo, tienda, cliente,
        ahora=ahora, ventana_min=VENTANA_RECUPERACION_MIN,
    )


async def reintentar_fallidas(
    notif_repo,
    turnos_repo,
    pacientes_repo,
    tienda,
    cliente,
    ahora: datetime | None = None,
) -> dict[str, int]:
    """Reintenta encoladas degradadas + fallidas transitorias (D-04)."""
    return await servicio.reintentar_fallidas(
        notif_repo, turnos_repo, pacientes_repo, tienda, cliente, ahora=ahora
    )


__all__ = [
    "VENTANA_RECUPERACION_MIN",
    "barrido_recordatorios",
    "barrido_recuperacion",
    "reintentar_fallidas",
]
