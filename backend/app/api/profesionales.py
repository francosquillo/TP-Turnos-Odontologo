"""Router stub C-01: profesionales (CRUD real en C-02)."""
from fastapi import APIRouter

router = APIRouter(prefix="/profesionales", tags=["profesionales"])


@router.get("")
def profesionales_stub() -> dict[str, str]:
    return {"recurso": "profesionales", "status": "stub C-01"}
