"""Router tratamientos: catálogo de solo lectura (C-08, D-10).

Cualquier rol autenticado lee; no hay escritura por API (C-12 trae el ABM).
"""
from fastapi import APIRouter, Depends
from typing import Annotated

from app.core.deps import CurrentUserDep, DbDep
from app.esquemas.clinica import TratamientoOut
from app.repos.tratamiento_repo import TratamientoRepository

router = APIRouter(prefix="/tratamientos", tags=["tratamientos"])


def get_tratamiento_repo(db: DbDep) -> TratamientoRepository:
    return TratamientoRepository(db)


TratamientoRepoDep = Annotated[TratamientoRepository, Depends(get_tratamiento_repo)]


@router.get("")
async def listar_tratamientos(
    _usuario: CurrentUserDep, repo: TratamientoRepoDep
) -> list[TratamientoOut]:
    return [
        TratamientoOut.model_validate(t, from_attributes=True)
        for t in await repo.listar()
    ]


__all__ = ["router"]
