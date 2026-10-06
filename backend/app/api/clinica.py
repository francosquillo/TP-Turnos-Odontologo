"""Router stub C-01: clinica (historia/odontograma en C-08)."""
from fastapi import APIRouter

router = APIRouter(prefix="/clinica", tags=["clinica"])


@router.get("")
def clinica_stub() -> dict[str, str]:
    return {"recurso": "clinica", "status": "stub C-01"}
