"""Router stub C-01: cobros (caja real en C-09/C-10)."""
from fastapi import APIRouter

router = APIRouter(prefix="/cobros", tags=["cobros"])


@router.get("")
def cobros_stub() -> dict[str, str]:
    return {"recurso": "cobros", "status": "stub C-01"}
