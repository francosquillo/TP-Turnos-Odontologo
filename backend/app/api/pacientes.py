"""Router stub C-01: pacientes (CRUD real en C-02)."""
from fastapi import APIRouter

router = APIRouter(prefix="/pacientes", tags=["pacientes"])


@router.get("")
def pacientes_stub() -> dict[str, str]:
    return {"recurso": "pacientes", "status": "stub C-01"}
