"""Servicio clínico: historia clínica y odontograma (C-08, D-04..D-08, D-12).

Reglas de acceso (D-07):
- secretaria: lee historias y hallazgos de cualquier paciente, nunca escribe.
- odontologo: necesita un `Profesional` vinculado y al menos un turno NO
  cancelado con el paciente (cualquier fecha); la HC es compartida, pero solo
  el autor corrige o da de baja un hallazgo.
- admin (y el alias Dueño): sin acceso a datos clínicos.

Solo hace `flush`: el router es dueño del commit/rollback (patrón C-07).
NO loguea nada: antecedentes, alergias, motivos y hallazgos son PHI (D-12);
los errores de dominio llevan mensajes fijos, sin datos del paciente.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.esquemas.clinica import cara_compatible_con_pieza
from app.modelos import (
    EstadoHallazgoCatalogo, HallazgoOdontograma, HistoriaClinica, Usuario,
)
from app.repos.hallazgo_repo import HallazgoRepository
from app.repos.historia_repo import HistoriaRepository
from app.repos.paciente_repo import PacienteRepository
from app.repos.profesional_repo import ProfesionalRepository
from app.repos.turno_repo import TurnoRepository


class ClinicaError(Exception):
    """Base de los errores de dominio clínico (el router los mapea a HTTP)."""


class AccesoDenegadoError(ClinicaError):
    """403: rol, vínculo o autoría insuficientes."""


class NoEncontradoError(ClinicaError):
    """404: inexistente, dada de baja o de otra historia."""


class ConflictoError(ClinicaError):
    """409: duplicado o ya dado de baja."""


class ValidacionClinicaError(ClinicaError):
    """422: dato incoherente con el catálogo de estados."""


@dataclass(frozen=True)
class Actor:
    usuario_id: int
    rol: str
    profesional_id: int | None


@dataclass
class ClinicaRepos:
    historias: HistoriaRepository
    hallazgos: HallazgoRepository
    pacientes: PacienteRepository
    profesionales: ProfesionalRepository
    turnos: TurnoRepository

    @classmethod
    def de_sesion(cls, sesion) -> "ClinicaRepos":
        return cls(
            historias=HistoriaRepository(sesion),
            hallazgos=HallazgoRepository(sesion),
            pacientes=PacienteRepository(sesion),
            profesionales=ProfesionalRepository(sesion),
            turnos=TurnoRepository(sesion),
        )


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


async def construir_actor(repos: ClinicaRepos, usuario: Usuario) -> Actor:
    """Actor con el `Profesional` vinculado al usuario (solo importa al odontólogo)."""
    profesional_id = None
    if usuario.rol.nombre == "odontologo":
        profesional = await repos.profesionales.por_usuario_id(usuario.id)
        profesional_id = None if profesional is None else profesional.id
    return Actor(usuario_id=usuario.id, rol=usuario.rol.nombre, profesional_id=profesional_id)


# --- acceso --------------------------------------------------------------------------

async def _exigir_vinculo(repos: ClinicaRepos, actor: Actor, paciente_id: int) -> None:
    if actor.profesional_id is None:
        raise AccesoDenegadoError("el usuario no tiene un profesional vinculado")
    if not await repos.turnos.existe_vinculo(actor.profesional_id, paciente_id):
        raise AccesoDenegadoError("sin turno vigente con el paciente")


async def exigir_lectura(repos: ClinicaRepos, actor: Actor, paciente_id: int) -> None:
    if actor.rol == "secretaria":
        return
    if actor.rol != "odontologo":
        raise AccesoDenegadoError("sin permiso para datos clínicos")
    await _exigir_vinculo(repos, actor, paciente_id)


async def exigir_escritura(repos: ClinicaRepos, actor: Actor, paciente_id: int) -> None:
    if actor.rol != "odontologo":
        raise AccesoDenegadoError("sin permiso de escritura clínica")
    await _exigir_vinculo(repos, actor, paciente_id)


# --- historia clínica -------------------------------------------------------------------

async def _historia_activa(repos: ClinicaRepos, hc_id: int) -> HistoriaClinica:
    hc = await repos.historias.activa_por_id(hc_id)
    if hc is None:
        raise NoEncontradoError("historia clínica inexistente")
    return hc


async def obtener_historia(repos: ClinicaRepos, actor: Actor, hc_id: int) -> HistoriaClinica:
    hc = await _historia_activa(repos, hc_id)
    await exigir_lectura(repos, actor, hc.paciente_id)
    return hc


async def buscar_historias(
    repos: ClinicaRepos, actor: Actor, paciente_id: int
) -> list[HistoriaClinica]:
    """Lista de 0 o 1 historia activa del paciente (sin listado masivo de PHI)."""
    await exigir_lectura(repos, actor, paciente_id)
    hc = await repos.historias.por_paciente(paciente_id)
    return [hc] if hc is not None and hc.deleted_at is None else []


async def crear_historia(
    repos: ClinicaRepos, actor: Actor, paciente_id: int,
    antecedentes: str | None, alergias: str | None, ahora: datetime | None = None,
) -> HistoriaClinica:
    ahora = ahora or _ahora()
    if actor.rol != "odontologo" or actor.profesional_id is None:
        raise AccesoDenegadoError("sin permiso de escritura clínica")
    paciente = await repos.pacientes.get(paciente_id)
    if paciente is None or paciente.deleted_at is not None:
        raise NoEncontradoError("paciente inexistente")
    await _exigir_vinculo(repos, actor, paciente_id)
    existente = await repos.historias.por_paciente(paciente_id)
    if existente is not None:
        raise ConflictoError(
            "la historia clínica del paciente está dada de baja"
            if existente.deleted_at is not None
            else "el paciente ya tiene historia clínica"
        )
    try:
        async with repos.historias.sesion.begin_nested():
            return await repos.historias.crear(
                paciente_id=paciente_id, antecedentes=antecedentes,
                alergias=alergias, created_at=ahora, updated_at=ahora,
            )
    except IntegrityError:
        raise ConflictoError("el paciente ya tiene historia clínica") from None


async def actualizar_historia(
    repos: ClinicaRepos, actor: Actor, hc_id: int, cambios: dict[str, Any],
    ahora: datetime | None = None,
) -> HistoriaClinica:
    """Aplica solo los campos enviados (`cambios` viene de `exclude_unset`)."""
    hc = await _historia_activa(repos, hc_id)
    await exigir_escritura(repos, actor, hc.paciente_id)
    return await repos.historias.actualizar(hc, **cambios, updated_at=ahora or _ahora())


async def dar_de_baja_historia(
    repos: ClinicaRepos, actor: Actor, hc_id: int, motivo: str,
    ahora: datetime | None = None,
) -> HistoriaClinica:
    hc = await _historia_activa(repos, hc_id)
    await exigir_escritura(repos, actor, hc.paciente_id)
    return await repos.historias.soft_delete(hc, motivo, ahora or _ahora())


# --- catálogo -----------------------------------------------------------------------------

async def catalogo_vigente(
    repos: ClinicaRepos,
) -> tuple[int | None, list[EstadoHallazgoCatalogo]]:
    return await repos.hallazgos.estados_vigentes()


async def _validar_hallazgo(
    repos: ClinicaRepos, pieza: int, cara: str, estado: str
) -> int:
    """Devuelve la versión vigente si estado/cara son coherentes (422 si no)."""
    version, estados = await repos.hallazgos.estados_vigentes()
    por_codigo = {e.codigo: e for e in estados}
    fila = por_codigo.get(estado)
    if fila is None:
        raise ValidacionClinicaError("estado fuera del catálogo vigente")
    if not cara_compatible_con_pieza(pieza, cara):
        raise ValidacionClinicaError("cara inexistente en esa pieza")
    if fila.alcance == "pieza" and cara != "pieza_completa":
        raise ValidacionClinicaError("el estado aplica a la pieza completa")
    assert version is not None
    return version


# --- hallazgos ------------------------------------------------------------------------------

async def listar_hallazgos(
    repos: ClinicaRepos, actor: Actor, hc_id: int,
    pieza: int | None = None, incluir_anulados: bool = False,
) -> tuple[HistoriaClinica, list[HallazgoOdontograma]]:
    hc = await obtener_historia(repos, actor, hc_id)
    return hc, await repos.hallazgos.listar(hc.id, pieza, incluir_anulados)


async def obtener_hallazgo(
    repos: ClinicaRepos, actor: Actor, hc_id: int, hallazgo_id: int
) -> tuple[HistoriaClinica, HallazgoOdontograma]:
    hc = await obtener_historia(repos, actor, hc_id)
    hallazgo = await repos.hallazgos.get_en_hc(hc.id, hallazgo_id)
    if hallazgo is None:
        raise NoEncontradoError("hallazgo inexistente")
    return hc, hallazgo


async def registrar_hallazgo(
    repos: ClinicaRepos, actor: Actor, hc_id: int, pieza: int, cara: str,
    estado: str, ahora: datetime | None = None,
) -> HallazgoOdontograma:
    """Autor del usuario, fecha del reloj y versión vigente: nada viene del cliente."""
    hc = await _historia_activa(repos, hc_id)
    await exigir_escritura(repos, actor, hc.paciente_id)
    version = await _validar_hallazgo(repos, pieza, cara, estado)
    return await repos.hallazgos.crear(
        hc_id=hc.id, pieza_fdi=pieza, cara=cara, estado=estado,
        catalogo_version=version, fecha=ahora or _ahora(),
        profesional_id=actor.profesional_id,
    )


async def _hallazgo_propio_activo(
    repos: ClinicaRepos, actor: Actor, hc_id: int, hallazgo_id: int
) -> tuple[HistoriaClinica, HallazgoOdontograma]:
    hc = await _historia_activa(repos, hc_id)
    await exigir_escritura(repos, actor, hc.paciente_id)
    hallazgo = await repos.hallazgos.get_en_hc(hc.id, hallazgo_id)
    if hallazgo is None:
        raise NoEncontradoError("hallazgo inexistente")
    if hallazgo.profesional_id != actor.profesional_id:
        raise AccesoDenegadoError("solo el autor puede modificar el hallazgo")
    if hallazgo.deleted_at is not None:
        raise ConflictoError("el hallazgo ya está dado de baja")
    return hc, hallazgo


async def corregir_hallazgo(
    repos: ClinicaRepos, actor: Actor, hc_id: int, hallazgo_id: int, pieza: int,
    cara: str, estado: str, motivo: str, ahora: datetime | None = None,
) -> HallazgoOdontograma:
    """Baja el original con motivo y crea otro con `corrige_a_id`, en una transacción."""
    ahora = ahora or _ahora()
    hc, original = await _hallazgo_propio_activo(repos, actor, hc_id, hallazgo_id)
    version = await _validar_hallazgo(repos, pieza, cara, estado)
    try:
        async with repos.hallazgos.sesion.begin_nested():
            original.deleted_at = ahora
            original.motivo_baja = motivo
            return await repos.hallazgos.crear(
                hc_id=hc.id, pieza_fdi=pieza, cara=cara, estado=estado,
                catalogo_version=version, fecha=ahora,
                profesional_id=actor.profesional_id, corrige_a_id=original.id,
            )
    except IntegrityError:
        # El savepoint revierte el INSERT, pero el original en memoria quedó
        # marcado: se descarta ese estado para no persistir la baja a medias.
        repos.hallazgos.sesion.expire(original)
        raise ConflictoError("el hallazgo ya fue corregido") from None


async def dar_de_baja_hallazgo(
    repos: ClinicaRepos, actor: Actor, hc_id: int, hallazgo_id: int, motivo: str,
    ahora: datetime | None = None,
) -> HallazgoOdontograma:
    _, hallazgo = await _hallazgo_propio_activo(repos, actor, hc_id, hallazgo_id)
    hallazgo.deleted_at = ahora or _ahora()
    hallazgo.motivo_baja = motivo
    await repos.hallazgos.sesion.flush()
    return hallazgo
