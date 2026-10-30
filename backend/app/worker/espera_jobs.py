"""Job de vencimientos de lista de espera (C-07, D-05).

`barrido_vencidas()` marca las `ofrecidas` con `oferta_expira_en <= ahora`
como `vencida 'expirada'` y ofrece el mismo hueco al siguiente compatible.

Anti-doble-cascada: lock Redis `espera:cascada:{prof}:{sillon}:{inicio}`
con `SET NX EX 900` (TTL > duración del job), liberado en `finally` solo si
sigue siendo nuestro (verifica el token). Sin Redis degrada a barrido DB
idempotente: una entry ya `vencida` no vuelve a procesarse y
`intentar_ofrecer` excluye las `ofrecidas`, así que dos ticks no duplican.
Un fallo en una entry se cuenta, se hace rollback y el barrido sigue.
"""
import logging
import uuid
from datetime import datetime, timezone

from app.servicios import lista_espera_servicio as svc

_logger = logging.getLogger("worker.c07")

LOCK_TTL_SEG = 900  # 15 minutos (> duración de un barrido)


def _clave_lock(entry) -> str | None:
    hueco = entry.oferta_hueco or {}
    if not hueco.get("inicio"):
        return None
    return (
        f"espera:cascada:{hueco.get('profesional_id', entry.profesional_id)}:"
        f"{hueco.get('sillon_id', 1)}:{hueco['inicio']}"
    )


async def _tomar_lock(tienda, clave: str, token: str) -> bool | None:
    """True=tomado, False=ya lo tiene otro proceso, None=Redis caído (degrada)."""
    try:
        return bool(await tienda.set(clave, token, ex=LOCK_TTL_SEG, nx=True))
    except Exception as exc:  # noqa: BLE001 - Redis caído degrada, nunca tumba
        _logger.warning("redis no disponible, barrido degradado: %s", type(exc).__name__)
        return None


async def _soltar_lock(tienda, clave: str, token: str) -> None:
    """Libera solo si el lock sigue siendo nuestro (no pisa el de otro proceso)."""
    try:
        if await tienda.get(clave) == token:
            await tienda.delete(clave)
    except Exception:  # noqa: BLE001 - expira solo por TTL
        pass


async def barrido_vencidas(
    espera_repo,
    turnos_repo,
    profesionales_repo,
    sillones_repo,
    pacientes_repo,
    notif_repo,
    tienda,
    cliente,
    ahora: datetime | None = None,
    commit=None,
    rollback=None,
) -> dict[str, int]:
    """Barre ofertas vencidas: `vencida 'expirada'` + cascada al siguiente.

    `commit`/`rollback` son corrutinas opcionales de la sesión del worker
    (el servicio solo hace flush); se invocan por entry para que un fallo no
    descarte lo ya resuelto. Stats: vencidas, cascadas, skips, degradadas,
    errores.
    """
    momento = ahora or datetime.now(timezone.utc)
    stats = {"vencidas": 0, "cascadas": 0, "skips": 0, "degradadas": 0, "errores": 0}

    # Por id y recargando: tras un rollback las instancias previas quedan
    # expiradas (carga perezosa prohibida en async) y otro proceso pudo
    # resolver la entry mientras tanto.
    ids = [e.id for e in await espera_repo.ofrecidas_vencidas(momento)]
    for entry_id in ids:
        entry = await espera_repo.get(entry_id)
        if entry is None or entry.estado != "ofrecida":
            continue
        clave = _clave_lock(entry)
        token = uuid.uuid4().hex
        tomado = await _tomar_lock(tienda, clave, token) if clave else None
        if tomado is False:
            stats["skips"] += 1
            continue
        if tomado is None:
            stats["degradadas"] += 1
        try:
            siguiente = await svc.expirar_y_cascada(
                espera_repo=espera_repo, turnos_repo=turnos_repo,
                profesionales_repo=profesionales_repo, sillones_repo=sillones_repo,
                pacientes_repo=pacientes_repo, notif_repo=notif_repo,
                tienda=tienda, cliente=cliente, entry=entry, ahora=momento,
            )
            if commit is not None:
                await commit()
            stats["vencidas"] += 1
            if siguiente is not None:
                stats["cascadas"] += 1
        except Exception as exc:  # noqa: BLE001 - una entry rota no frena el barrido
            stats["errores"] += 1
            _logger.warning(
                "barrido espera entry %s falló: %s", getattr(entry, "id", "?"),
                type(exc).__name__,
            )
            if rollback is not None:
                await rollback()
        finally:
            if clave and tomado:
                await _soltar_lock(tienda, clave, token)

    return stats


__all__ = ["barrido_vencidas", "LOCK_TTL_SEG"]
