"""Worker C-06: heartbeat (C-01) + scheduler de notificaciones (D-04).

Misma imagen/contenedor que la API (decision C-01): sin servicio compose
nuevo. Al arranque corre el barrido de recuperacion (ventana extendida) y
luego heartbeat + bucle_notif en paralelo. Redis caido: los jobs degradan a
encolada y reintentan en el proximo tick (nunca tumban el worker).
"""
import asyncio
import logging

logger = logging.getLogger("worker.c06")


async def heartbeat(interval_s: float = 30.0) -> None:
    logger.info("worker heartbeat cada %ss", interval_s)
    while True:
        logger.info("worker alive")
        await asyncio.sleep(interval_s)


def _componentes():
    """Fabrica real: sesion DB + Redis + cliente WhatsApp desde env."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import redis.asyncio as aioredis

    from app.core.config import get_settings
    from app.repos.notificacion_repo import NotificacionRepository
    from app.repos.paciente_repo import PacienteRepository
    from app.repos.turno_repo import TurnoRepository
    from app.servicios.whatsapp_cliente import crear_cliente

    settings = get_settings()
    motor = create_async_engine(settings.database_url)
    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    tienda = aioredis.from_url(settings.redis_url, decode_responses=True)
    cliente = crear_cliente(
        settings.whatsapp_mock,
        token=settings.whatsapp_token,
        phone_id=settings.whatsapp_phone_id,
    )
    return fabrica, tienda, cliente, TurnoRepository, PacienteRepository, NotificacionRepository


async def bucle_notif(intervalo_s: float = 3600.0) -> None:
    """Tick horario: barrido 48/24 h + reintento de fallidas (D-03/D-04)."""
    from app.worker import notif_jobs as jobs

    fabrica, tienda, cliente, TurnoRepo, PacienteRepo, NotifRepo = _componentes()
    while True:
        try:
            async with fabrica() as sesion:
                await jobs.barrido_recordatorios(
                    TurnoRepo(sesion), NotifRepo(sesion),
                    PacienteRepo(sesion), tienda, cliente,
                )
                await jobs.reintentar_fallidas(
                    NotifRepo(sesion), TurnoRepo(sesion),
                    PacienteRepo(sesion), tienda, cliente,
                )
        except Exception as exc:  # noqa: BLE001 - el worker nunca se cae
            logger.warning("tick notif fallo (reintenta en 1 h): %s", type(exc).__name__)
        await asyncio.sleep(intervalo_s)


async def main() -> None:
    """Arranque: recuperacion con ventana extendida + loops en paralelo."""
    from app.worker import notif_jobs as jobs

    logger.info("worker C-06 iniciado (heartbeat + notificaciones)")
    try:
        fabrica, tienda, cliente, TurnoRepo, PacienteRepo, NotifRepo = _componentes()
        async with fabrica() as sesion:
            stats = await jobs.barrido_recuperacion(
                TurnoRepo(sesion), NotifRepo(sesion),
                PacienteRepo(sesion), tienda, cliente,
            )
            logger.info("barrido recuperacion al arranque: %s", stats)
    except Exception as exc:  # noqa: BLE001 - sin DB/Redis el worker late igual
        logger.warning("recuperacion inicial omitida: %s", type(exc).__name__)
    await asyncio.gather(heartbeat(), bucle_notif())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
