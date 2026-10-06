"""Router stub C-01: auth (JWT real en C-03)."""
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("")
def auth_stub() -> dict[str, str]:
    return {"recurso": "auth", "status": "stub C-01"}
