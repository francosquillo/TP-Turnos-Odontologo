"""Router pacientes: stub GET de C-01 + plan de obra social (C-11, D-07).

No hay CRUD de pacientes: se suman solo GET/PUT /pacientes/:id/plan, para secretaria y
admin. El servicio solo hace flush; este router es dueno del commit.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.clinica_comun import a_http
from app.api.obras_sociales import OsReposDep
from app.api.turnos import PacienteRepoDep
from app.core.deps import AuditoriaDep, DbDep, require_role
from app.esquemas.importacion import ImportacionOut
from app.esquemas.obra_social import PlanPacienteIn, PlanPacienteOut
from app.modelos import Usuario
from app.servicios import obra_social_servicio as svc
from app.servicios.auditoria_servicio import auditar
from app.servicios.importacion_servicio import MAX_BYTES, ArchivoInvalidoError, importar_pacientes

router = APIRouter(prefix="/pacientes", tags=["pacientes"])

CoberturaPacienteDep = Annotated[Usuario, Depends(require_role("secretaria", "admin"))]


@router.get("")
def pacientes_stub() -> dict[str, str]:
    return {"recurso": "pacientes", "status": "stub C-01"}


@router.post("/import")
async def importar(
    archivo: Annotated[UploadFile, File()],
    usuario: CoberturaPacienteDep,
    pacientes: PacienteRepoDep,
    auditoria: AuditoriaDep,
    db: DbDep,
) -> ImportacionOut:
    """Importa pacientes de un CSV o XLSX (C-12, D-11): crea las filas validas y reporta el resto.

    Un archivo ilegible, sin columnas obligatorias o fuera de limite responde 422 sin crear nada.
    """
    contenido = await archivo.read(MAX_BYTES + 1)
    try:
        reporte = await importar_pacientes(pacientes, archivo.filename or "", contenido)
    except ArchivoInvalidoError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from None
    # Solo conteos: ni filas ni datos de pacientes entran a la auditoria (RN-CL-04).
    await auditar(
        auditoria, usuario.id, "pacientes_importacion", "importacion",
        detalle={"creados": reporte.creados, "rechazados": reporte.rechazados},
    )
    await db.commit()
    return reporte


@router.get("/{paciente_id}/plan")
async def obtener_plan(
    paciente_id: int, usuario: CoberturaPacienteDep, repos: OsReposDep, db: DbDep
) -> PlanPacienteOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        return await svc.obtener_plan_paciente(repos, actor, paciente_id)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None


@router.put("/{paciente_id}/plan")
async def asignar_plan(
    paciente_id: int, datos: PlanPacienteIn, usuario: CoberturaPacienteDep, repos: OsReposDep,
    db: DbDep,
) -> PlanPacienteOut:
    try:
        actor = await svc.construir_actor(repos.clinica, usuario)
        salida = await svc.asignar_plan(repos, actor, paciente_id, datos.plan_id)
    except svc.ClinicaError as exc:
        raise await a_http(db, exc) from None
    await db.commit()
    return salida


__all__ = ["router"]
