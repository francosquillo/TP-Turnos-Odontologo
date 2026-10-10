"""Router turnos real (C-04): CRUD + estado + reprogramacion, RBAC D-07.

admin|secretaria: escritura completa. odontologo: lectura + estado
(asistido/ausente) de turnos propios. Sin DELETE de negocio (RN-GL-01).
Colision -> 409 {"detail", "alternativas"} con re-oferta (Flujo 1, D-06).
"""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.core.deps import DbDep, require_role
from app.esquemas.turno import EstadoPatch, ReprogramarIn, TurnoIn, TurnoOut
from app.modelos import Usuario
from app.repos.paciente_repo import PacienteRepository
from app.repos.profesional_repo import ProfesionalRepository
from app.repos.sillon_repo import SillonRepository
from app.repos.turno_repo import TurnoRepository
from app.servicios import agenda_servicio as svc

router = APIRouter(prefix="/turnos", tags=["turnos"])

EscrituraDep = Annotated[Usuario, Depends(require_role("admin", "secretaria"))]
LecturaDep = Annotated[Usuario, Depends(require_role("admin", "secretaria", "odontologo"))]


def get_turno_repo(db: DbDep) -> TurnoRepository:
    return TurnoRepository(db)


def get_paciente_repo(db: DbDep) -> PacienteRepository:
    return PacienteRepository(db)


def get_profesional_repo(db: DbDep) -> ProfesionalRepository:
    return ProfesionalRepository(db)


def get_sillon_repo(db: DbDep) -> SillonRepository:
    return SillonRepository(db)


TurnoRepoDep = Annotated[TurnoRepository, Depends(get_turno_repo)]
PacienteRepoDep = Annotated[PacienteRepository, Depends(get_paciente_repo)]
ProfesionalRepoDep = Annotated[ProfesionalRepository, Depends(get_profesional_repo)]
SillonRepoDep = Annotated[SillonRepository, Depends(get_sillon_repo)]


def _es_admin(usuario: Usuario) -> bool:
    return getattr(getattr(usuario, "rol", None), "nombre", None) == "admin"


def _es_odontologo(usuario: Usuario) -> bool:
    return getattr(getattr(usuario, "rol", None), "nombre", None) == "odontologo"


def _a_out(turno) -> TurnoOut:
    return TurnoOut(
        id=turno.id,
        paciente_id=turno.paciente_id,
        profesional_id=turno.profesional_id,
        sillon_id=turno.sillon_id,
        inicio=turno.inicio,
        fin=turno.fin,
        estado=turno.estado,
        origen=turno.origen,
        sobre_turno=turno.sobre_turno,
        motivo_sobreturno=turno.motivo_sobreturno,
        motivo_cancelacion=turno.motivo_cancelacion,
        creado_por=turno.creado_por,
        created_at=turno.created_at,
    )


def _conflicto(error: svc.HuecoOcupadoError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "detail": "hueco ocupado",
            "alternativas": [
                {"inicio": ini.isoformat(), "fin": fin.isoformat()}
                for ini, fin in error.alternativas
            ],
        },
    )


async def _profesional_propio_id(profesionales_repo, usuario: Usuario) -> int | None:
    profesional = await profesionales_repo.por_usuario_id(usuario.id)
    return None if profesional is None else profesional.id


@router.post("", status_code=201)
async def crear_turno(
    datos: TurnoIn,
    usuario: EscrituraDep,
    db: DbDep,
    turnos: TurnoRepoDep,
    pacientes: PacienteRepoDep,
    profesionales: ProfesionalRepoDep,
    sillones: SillonRepoDep,
) -> TurnoOut:
    """Crea un turno (staff nace confirmado, online/lista_espera pendiente)."""
    try:
        turno = await svc.crear_turno(
            turnos,
            pacientes,
            profesionales,
            sillones,
            paciente_id=datos.paciente_id,
            profesional_id=datos.profesional_id,
            sillon_id=datos.sillon_id,
            inicio=datos.inicio,
            fin=datos.fin,
            origen=datos.origen,
            sobre_turno=datos.sobre_turno,
            motivo_sobreturno=datos.motivo_sobreturno,
            creado_por=usuario.id,
            es_admin=_es_admin(usuario),
        )
    except svc.HuecoOcupadoError as exc:
        await db.rollback()
        return _conflicto(exc)  # type: ignore[return-value]
    except svc.EntidadNoEncontradaError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except (svc.MotivoRequeridoError, svc.PasadoNoPermitidoError, ValueError) as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from None
    await db.commit()
    return _a_out(turno)


@router.get("")
async def listar_turnos(
    usuario: LecturaDep,
    turnos: TurnoRepoDep,
    profesionales: ProfesionalRepoDep,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    profesional_id: int | None = None,
    sillon_id: int | None = None,
) -> list[TurnoOut]:
    """Lista turnos (odontologo: solo los propios vinculados)."""
    if _es_odontologo(usuario):
        profesional_id = await _profesional_propio_id(profesionales, usuario)
        if profesional_id is None:
            return []
    if desde is not None and hasta is not None:
        filas = await turnos.listar_periodo(
            desde, hasta, profesional_id=profesional_id, sillon_id=sillon_id,
            solo_activos=False,
        )
    else:
        filas = await turnos.list(limit=100)
        if profesional_id is not None:
            filas = [t for t in filas if t.profesional_id == profesional_id]
        if sillon_id is not None:
            filas = [t for t in filas if t.sillon_id == sillon_id]
    return [_a_out(t) for t in filas]


@router.get("/{turno_id}")
async def obtener_turno(
    turno_id: int,
    usuario: LecturaDep,
    turnos: TurnoRepoDep,
    profesionales: ProfesionalRepoDep,
) -> TurnoOut:
    """Detalle (odontologo: solo propios, resto 403)."""
    turno = await turnos.get(turno_id)
    if turno is None:
        raise HTTPException(status_code=404, detail="turno inexistente")
    if _es_odontologo(usuario):
        propio = await _profesional_propio_id(profesionales, usuario)
        if propio is None or turno.profesional_id != propio:
            raise HTTPException(status_code=403, detail="sin permiso")
    return _a_out(turno)


@router.patch("/{turno_id}/estado")
async def cambiar_estado(
    turno_id: int,
    datos: EstadoPatch,
    usuario: LecturaDep,
    db: DbDep,
    turnos: TurnoRepoDep,
    profesionales: ProfesionalRepoDep,
) -> TurnoOut:
    """Avanza la maquina D-03 (odontologo: asistido/ausente propios)."""
    if _es_odontologo(usuario):
        if datos.estado not in ("asistido", "ausente"):
            raise HTTPException(status_code=403, detail="sin permiso")
        turno_actual = await turnos.get(turno_id)
        if turno_actual is None:
            raise HTTPException(status_code=404, detail="turno inexistente")
        propio = await _profesional_propio_id(profesionales, usuario)
        if propio is None or turno_actual.profesional_id != propio:
            raise HTTPException(status_code=403, detail="sin permiso")
    try:
        turno = await svc.cambiar_estado(
            turnos, turno_id, datos.estado,
            motivo=datos.motivo, es_admin=_es_admin(usuario),
        )
    except svc.EntidadNoEncontradaError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except (svc.TransicionInvalidaError, svc.MotivoRequeridoError, ValueError) as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from None
    await db.commit()
    return _a_out(turno)


@router.patch("/{turno_id}")
async def reprogramar_turno(
    turno_id: int,
    datos: ReprogramarIn,
    _usuario: EscrituraDep,
    db: DbDep,
    turnos: TurnoRepoDep,
    profesionales: ProfesionalRepoDep,
) -> TurnoOut:
    """Mueve un turno (revalida como creacion; 409 conserva horario, D-06)."""
    try:
        turno = await svc.reprogramar(
            turnos, profesionales, turno_id,
            nuevo_inicio=datos.inicio, nuevo_fin=datos.fin,
            sobre_turno=datos.sobre_turno, motivo_sobreturno=datos.motivo_sobreturno,
        )
    except svc.HuecoOcupadoError as exc:
        await db.rollback()
        return _conflicto(exc)  # type: ignore[return-value]
    except svc.EntidadNoEncontradaError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except (svc.MotivoRequeridoError, ValueError) as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from None
    await db.commit()
    return _a_out(turno)


__all__ = [
    "router",
    "get_turno_repo",
    "get_paciente_repo",
    "get_profesional_repo",
    "get_sillon_repo",
]
