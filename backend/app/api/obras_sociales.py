"""Router stub C-01: obras sociales (nomenclador en C-09)."""
from fastapi import APIRouter

router = APIRouter(prefix="/os", tags=["os"])


@router.get("")
def os_stub() -> dict[str, str]:
    return {"recurso": "os", "status": "stub C-01"}
