"""Router lista de espera (C-07, D-02/D-04/D-06/D-07).

Staff (secretaria|admin): CRUD /lista-espera (la baja es lógica, RN-GL-01),
POST /:id/ofrecer, POST /:id/convertir. Públicos (sin Bearer, el hash del
token es la auth): GET /oferta/:token, POST /aceptar/:token,
POST /rechazar/:token.

Compone `lista_espera_servicio` SIN modificar agenda_servicio /
reserva_servicio / notificacion_servicio / whatsapp_cliente.
El servicio solo hace flush: este router es dueño del commit/rollback.
El token NUNCA se loguea.
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.api.espera_hook import ClienteEsperaDep, EsperaRepoDep
from app.api.notificaciones import NotifRepoDep
from app.api.turnos import (
    PacienteRepoDep,
    ProfesionalRepoDep,
    SillonRepoDep,
    TurnoRepoDep,
)
from app.core.deps import DbDep, StoreDep, require_role
from app.esquemas.lista_espera import (
    BajaIn,
    EsperaIn,
    EsperaOut,
    EsperaPatch,
    EstadoEspera,
    OfertaPublicaOut,
    OfrecerIn,
)
from app.modelos import Usuario
from app.servicios import lista_espera_servicio as svc
from app.servicios.reserva_servicio import hash_token

router = APIRouter(prefix="/lista-espera", tags=["lista-espera"])

StaffDep = Annotated[Usuario, Depends(require_role("admin", "secretaria"))]


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


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


def _a_out(entrada) -> EsperaOut:
    return EsperaOut(
        id=entrada.id,
        paciente_id=entrada.paciente_id,
        profesional_id=entrada.profesional_id,
        especialidad=entrada.especialidad,
        preferencia_horaria=entrada.preferencia_horaria,
        estado=entrada.estado,
        oferta_expira_en=entrada.oferta_expira_en,
        oferta_hueco=entrada.oferta_hueco,
        motivo_baja=entrada.motivo_baja,
        created_at=entrada.created_at,
    )


async def _entrada_o_404(espera, espera_id: int):
    entrada = await espera.get(espera_id)
    if entrada is None:
        raise HTTPException(status_code=404, detail="entrada de espera inexistente")
    return entrada


def _preferencia(datos) -> dict | None:
    if datos is None:
        return None
    return datos.model_dump(exclude_none=True) or None


# --- CRUD staff --------------------------------------------------------------

@router.post("", status_code=201)
async def crear_espera(
    datos: EsperaIn,
    _usuario: StaffDep,
    db: DbDep,
    espera: EsperaRepoDep,
    pacientes: PacienteRepoDep,
    profesionales: ProfesionalRepoDep,
) -> EsperaOut:
    """Alta en la cola (entra al final: orden FIFO por `created_at`)."""
    if await pacientes.get(datos.paciente_id) is None:
        raise HTTPException(status_code=422, detail="paciente inexistente")
    if datos.profesional_id is not None and await profesionales.get(datos.profesional_id) is None:
        raise HTTPException(status_code=422, detail="profesional inexistente")
    entrada = await espera.crear(
        paciente_id=datos.paciente_id,
        profesional_id=datos.profesional_id,
        especialidad=datos.especialidad,
        preferencia_horaria=_preferencia(datos.preferencia_horaria),
        estado="activa",
    )
    await db.commit()
    return _a_out(entrada)


@router.get("")
async def listar_espera(
    _usuario: StaffDep,
    espera: EsperaRepoDep,
    estado: EstadoEspera | None = None,
) -> list[EsperaOut]:
    """Cola FIFO (created_at ASC), opcionalmente filtrada por estado."""
    return [_a_out(e) for e in await espera.listar_fifo(estado=estado)]


@router.get("/oferta/{token}")
async def ver_oferta_publica(
    token: str,
    espera: EsperaRepoDep,
    pacientes: PacienteRepoDep,
) -> OfertaPublicaOut:
    """Detalle mínimo para la página pública (sin Bearer, sin PHI, sin mutar)."""
    entrada = await espera.get_by_token_hash(hash_token(token))
    if entrada is None:
        raise HTTPException(status_code=404, detail="token inexistente")
    hueco = entrada.oferta_hueco or {}
    if (
        entrada.estado != "ofrecida"
        or entrada.oferta_expira_en is None
        or _ahora() >= entrada.oferta_expira_en
        or not hueco
    ):
        raise HTTPException(status_code=410, detail="oferta no disponible")
    paciente = await pacientes.get(entrada.paciente_id)
    return OfertaPublicaOut(
        nombre_pila=svc.nombre_pila(paciente),
        inicio=datetime.fromisoformat(hueco["inicio"]),
        fin=datetime.fromisoformat(hueco["fin"]),
        oferta_expira_en=entrada.oferta_expira_en,
    )


@router.get("/{espera_id}")
async def obtener_espera(
    espera_id: int,
    _usuario: StaffDep,
    espera: EsperaRepoDep,
) -> EsperaOut:
    return _a_out(await _entrada_o_404(espera, espera_id))


@router.patch("/{espera_id}")
async def actualizar_espera(
    espera_id: int,
    datos: EsperaPatch,
    _usuario: StaffDep,
    db: DbDep,
    espera: EsperaRepoDep,
) -> EsperaOut:
    """Edita destino/preferencia de una entry `activa`."""
    entrada = await _entrada_o_404(espera, espera_id)
    if entrada.estado != "activa":
        raise HTTPException(status_code=409, detail="solo se edita una entrada activa")
    cambios = datos.model_dump(exclude_unset=True)
    if "preferencia_horaria" in cambios:
        cambios["preferencia_horaria"] = _preferencia(datos.preferencia_horaria)
    destino_prof = cambios.get("profesional_id", entrada.profesional_id)
    destino_esp = cambios.get("especialidad", entrada.especialidad)
    if destino_prof is None and not destino_esp:
        raise HTTPException(
            status_code=422, detail="debe quedar profesional_id o especialidad"
        )
    entrada = await espera.actualizar(entrada, **cambios)
    await db.commit()
    return _a_out(entrada)


@router.post("/{espera_id}/baja")
async def dar_de_baja(
    espera_id: int,
    datos: BajaIn,
    _usuario: StaffDep,
    db: DbDep,
    espera: EsperaRepoDep,
) -> EsperaOut:
    """Baja lógica con motivo (RN-GL-01/02): `vencida` + `motivo_baja`, sin DELETE."""
    entrada = await _entrada_o_404(espera, espera_id)
    if entrada.estado in ("convertida", "vencida"):
        raise HTTPException(status_code=409, detail="la entrada ya está resuelta")
    entrada = await espera.actualizar(
        entrada, estado="vencida", motivo_baja=datos.motivo_baja,
    )
    await db.commit()
    return _a_out(entrada)


# --- Ofrecer manual / convertir (staff) --------------------------------------

@router.post("/{espera_id}/ofrecer")
async def ofrecer_manual(
    espera_id: int,
    datos: OfrecerIn,
    _usuario: StaffDep,
    db: DbDep,
    espera: EsperaRepoDep,
    pacientes: PacienteRepoDep,
    notifs: NotifRepoDep,
    cliente: ClienteEsperaDep,
) -> EsperaOut:
    """Ofrece un hueco a una entry puntual (saltea/adelanta la cola)."""
    try:
        entrada = await svc.ofrecer_a_entry(
            espera_repo=espera, notif_repo=notifs, pacientes_repo=pacientes,
            cliente=cliente, entry_id=espera_id, ahora=_ahora(),
            hueco=datos.model_dump(),
        )
    except svc.EntradaNoEncontradaError:
        raise HTTPException(status_code=404, detail="entrada de espera inexistente") from None
    except svc.OfertaYaActivaError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None
    await db.commit()
    return _a_out(entrada)


@router.post("/{espera_id}/convertir")
async def convertir_staff(
    espera_id: int,
    _usuario: StaffDep,
    db: DbDep,
    espera: EsperaRepoDep,
    turnos: TurnoRepoDep,
    profesionales: ProfesionalRepoDep,
    sillones: SillonRepoDep,
    pacientes: PacienteRepoDep,
    notifs: NotifRepoDep,
    tienda: StoreDep,
    cliente: ClienteEsperaDep,
) -> JSONResponse:
    """Convierte una `ofrecida` en turno confirmado (aceptó por teléfono)."""
    entrada = await _entrada_o_404(espera, espera_id)
    if entrada.estado != "ofrecida" or not entrada.token_oferta_hash:
        raise HTTPException(status_code=409, detail="la entrada no tiene una oferta vigente")
    return await _aceptar(
        db, token_hash=entrada.token_oferta_hash, espera=espera, turnos=turnos,
        profesionales=profesionales, sillones=sillones, pacientes=pacientes,
        notifs=notifs, tienda=tienda, cliente=cliente, detalle="convertido",
    )


# --- Públicos (sin Bearer) ---------------------------------------------------

@router.post("/aceptar/{token}")
async def aceptar_publico(
    token: str,
    db: DbDep,
    espera: EsperaRepoDep,
    turnos: TurnoRepoDep,
    profesionales: ProfesionalRepoDep,
    sillones: SillonRepoDep,
    pacientes: PacienteRepoDep,
    notifs: NotifRepoDep,
    tienda: StoreDep,
    cliente: ClienteEsperaDep,
) -> JSONResponse:
    """Acepta la oferta por token: 200 turno confirmado | 404 | 409 | 410."""
    return await _aceptar(
        db, token_hash=hash_token(token), espera=espera, turnos=turnos,
        profesionales=profesionales, sillones=sillones, pacientes=pacientes,
        notifs=notifs, tienda=tienda, cliente=cliente, detalle="aceptado",
    )


async def _aceptar(
    db, *, token_hash, espera, turnos, profesionales, sillones, pacientes,
    notifs, tienda, cliente, detalle: str,
) -> JSONResponse:
    try:
        turno = await svc.aceptar_por_token(
            espera_repo=espera, turnos_repo=turnos,
            profesionales_repo=profesionales, sillones_repo=sillones,
            pacientes_repo=pacientes, notif_repo=notifs, tienda=tienda,
            cliente=cliente, token_hash=token_hash, ahora=_ahora(),
        )
    except svc.TokenDesconocidoError:
        await db.rollback()
        return JSONResponse(status_code=404, content={"detail": "token inexistente"})
    except svc.TokenUsadoError:
        await db.rollback()
        return JSONResponse(status_code=410, content={"detail": "oferta ya resuelta"})
    except svc.TokenExpiradoError:
        # El servicio ya marcó la entry vencida y encadenó: se persiste.
        await db.commit()
        return JSONResponse(status_code=410, content={"detail": "oferta expirada"})
    except svc.HuecoOcupadoError as exc:
        # Idem: entry vencida 'hueco_tomado' + cascada ya hechas.
        await db.commit()
        return _conflicto(exc)
    await db.commit()
    return JSONResponse(status_code=200, content={"detail": detalle, "turno_id": turno.id})


@router.post("/rechazar/{token}")
async def rechazar_publico(
    token: str,
    db: DbDep,
    espera: EsperaRepoDep,
    turnos: TurnoRepoDep,
    profesionales: ProfesionalRepoDep,
    sillones: SillonRepoDep,
    pacientes: PacienteRepoDep,
    notifs: NotifRepoDep,
    tienda: StoreDep,
    cliente: ClienteEsperaDep,
) -> JSONResponse:
    """Rechaza la oferta: entry `vencida` + cascada al siguiente."""
    try:
        await svc.rechazar_por_token(
            espera_repo=espera, turnos_repo=turnos, profesionales_repo=profesionales,
            sillones_repo=sillones, pacientes_repo=pacientes, notif_repo=notifs,
            tienda=tienda, cliente=cliente, token_hash=hash_token(token),
            ahora=_ahora(),
        )
    except svc.TokenDesconocidoError:
        await db.rollback()
        return JSONResponse(status_code=404, content={"detail": "token inexistente"})
    except svc.TokenUsadoError:
        await db.rollback()
        return JSONResponse(status_code=410, content={"detail": "oferta ya resuelta"})
    await db.commit()
    return JSONResponse(status_code=200, content={"detail": "rechazado"})


__all__ = ["router"]
