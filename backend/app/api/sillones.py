"""Router stub C-01: sillones (CRUD real en C-02)."""
from fastapi import APIRouter

router = APIRouter(prefix="/sillones", tags=["sillones"])


@router.get("")
def sillones_stub() -> dict[str, str]:
    return {"recurso": "sillones", "status": "stub C-01"}
