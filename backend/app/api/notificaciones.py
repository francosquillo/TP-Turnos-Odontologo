"""Router stub C-01: notificaciones (worker real en C-06)."""
from fastapi import APIRouter

router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])


@router.get("")
def notificaciones_stub() -> dict[str, str]:
    return {"recurso": "notificaciones", "status": "stub C-01"}
