"""Router del validador de cobertura (C-11, D-04, D-16).

GET /validador-cobertura: secretaria y admin; el odontologo recibe 403. No crea filas, por
lo que no hace commit.
"""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.clinica_comun import a_http
from app.api.obras_sociales import OsReposDep
from app.core.deps import DbDep, require_role
from app.esquemas.obra_social import ValidadorCoberturaOut
from app.modelos import Usuario
from app.servicios import obra_social_servicio as svc
from app.servicios.caja_servicio import hoy_operativo

router = APIRouter(prefix="/validador-cobertura", tags=["cobertura"])

LecturaCoberturaDep = Annotated[Usuario, Depends(require_role("secretaria", "admin"))]


@router.get("")
async def validar_cobertura(
    paciente_id: int, tratamiento_id: int, usuario: LecturaCoberturaDep, repos: OsReposDep,
    db: DbDep,
) -> ValidadorCoberturaOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        return await svc.validar_cobertura(
            repos, actor, paciente_id, tratamiento_id, hoy_operativo()
        )
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None


__all__ = ["router"]
