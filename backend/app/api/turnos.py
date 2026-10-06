"""Router stub C-01: turnos (agenda real en C-04)."""
from fastapi import APIRouter

router = APIRouter(prefix="/turnos", tags=["turnos"])


@router.get("")
def turnos_stub() -> dict[str, str]:
    return {"recurso": "turnos", "status": "stub C-01"}
