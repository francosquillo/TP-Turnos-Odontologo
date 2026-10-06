"""Router stub C-01: admin (panel real post C-03)."""
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("")
def admin_stub() -> dict[str, str]:
    return {"recurso": "admin", "status": "stub C-01"}
