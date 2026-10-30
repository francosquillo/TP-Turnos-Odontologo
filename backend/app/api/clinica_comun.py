"""Dependencias y mapeo de errores compartidos por los routers clínicos (C-08, D-09).

Códigos: 401 sin Bearer (lo resuelve `get_current_user`), 403 rol/vínculo/
autoría, 404 inexistente o dada de baja, 409 duplicado o ya dado de baja,
422 validación. Los mensajes de error son fijos: nunca incluyen PHI (D-12).
"""
from typing import Annotated, TypeVar

from fastapi import Depends, HTTPException

from app.core.deps import DbDep, require_role
from app.modelos import Usuario
from app.servicios import clinica_servicio as svc

T = TypeVar("T")

# Lectura: secretaria y odontólogo (el admin y el alias Dueño no ven PHI).
LecturaClinicaDep = Annotated[Usuario, Depends(require_role("secretaria", "odontologo"))]
EscrituraClinicaDep = Annotated[Usuario, Depends(require_role("odontologo"))]

_STATUS: dict[type[svc.ClinicaError], int] = {
    svc.AccesoDenegadoError: 403,
    svc.NoEncontradoError: 404,
    svc.ConflictoError: 409,
    svc.ValidacionClinicaError: 422,
}


def get_clinica_repos(db: DbDep) -> svc.ClinicaRepos:
    return svc.ClinicaRepos.de_sesion(db)


ClinicaReposDep = Annotated[svc.ClinicaRepos, Depends(get_clinica_repos)]


async def a_http(db, error: svc.ClinicaError) -> HTTPException:
    """Revierte lo pendiente y traduce el error de dominio a HTTP."""
    await db.rollback()
    return HTTPException(status_code=_STATUS[type(error)], detail=str(error))
