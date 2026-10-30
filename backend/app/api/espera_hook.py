"""Gancho aditivo de C-07 (D-02): ofrecer el hueco tras una cancelación.

Lo llaman `PATCH /turnos/:id/estado` y el evento NO del webhook C-06, siempre
DESPUÉS de que `cambiar_estado→cancelado` ya hizo commit. Un fallo de la
oferta NUNCA revierte el cancelado: se hace rollback solo de lo pendiente
(la oferta) y se loguea. `ausente` no pasa por acá (D-02).

Aloja también los providers de dependencias compartidos con el router
`lista-espera` (evita ciclos de import turnos <-> webhooks <-> lista_espera).
"""
import logging
from typing import Annotated

from fastapi import Depends

from app.core.deps import DbDep, SettingsDep
from app.repos.espera_repo import EsperaRepository
from app.servicios import lista_espera_servicio as espera_svc
from app.servicios.whatsapp_cliente import crear_cliente

_log = logging.getLogger(__name__)


def get_espera_repo(db: DbDep) -> EsperaRepository:
    return EsperaRepository(db)


def get_cliente_espera(settings: SettingsDep):
    """Cliente WhatsApp según env (mock por defecto; Meta con fail-fast)."""
    return crear_cliente(
        settings.whatsapp_mock,
        token=settings.whatsapp_token,
        phone_id=settings.whatsapp_phone_id,
    )


EsperaRepoDep = Annotated[EsperaRepository, Depends(get_espera_repo)]
ClienteEsperaDep = Annotated[object, Depends(get_cliente_espera)]


def hueco_de_turno(turno) -> dict:
    """Hueco liberado por un turno cancelado (con su id para el aviso)."""
    return {
        "profesional_id": turno.profesional_id,
        "sillon_id": turno.sillon_id,
        "inicio": turno.inicio,
        "fin": turno.fin,
        "turno_id": turno.id,
    }


async def ofrecer_tras_cancelacion(
    *, db, turno, espera_repo, turnos_repo, profesionales_repo, sillones_repo,
    pacientes_repo, notif_repo, tienda, cliente,
) -> None:
    """Dispara `intentar_ofrecer` sobre el hueco del turno y persiste la oferta."""
    try:
        await espera_svc.intentar_ofrecer(
            espera_repo=espera_repo,
            turnos_repo=turnos_repo,
            profesionales_repo=profesionales_repo,
            sillones_repo=sillones_repo,
            pacientes_repo=pacientes_repo,
            notif_repo=notif_repo,
            tienda=tienda,
            cliente=cliente,
            hueco=hueco_de_turno(turno),
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001 - el cancelado ya está commiteado
        _log.warning(
            "oferta post-cancelado falló turno %s: %s",
            getattr(turno, "id", "?"), type(exc).__name__,
        )
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
