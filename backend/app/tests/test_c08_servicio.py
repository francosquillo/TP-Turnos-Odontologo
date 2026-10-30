"""C-08 grupo 4: servicio clínico (acceso, historia, hallazgos) sobre PG real.

El servicio solo hace flush; los tests verifican reglas y errores de dominio.
`freezegun` fija el reloj de `fecha` y `updated_at`. Datos ficticios.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from freezegun import freeze_time

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import crear_turno, sembrar_mundo  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

AHORA = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


async def _escenario(sesion, con_turno=True):
    """Mundo + Ana atendida por A; devuelve (svc, repos, m, actores)."""
    from app.servicios import clinica_servicio as svc

    m = await sembrar_mundo(sesion)
    if con_turno:
        await crear_turno(sesion, m.ana, m.prof_a, m.sillon, estado="asistido")
    repos = svc.ClinicaRepos.de_sesion(sesion)
    actores = {
        "a": svc.Actor(usuario_id=m.odo_a.id, rol="odontologo", profesional_id=m.prof_a.id),
        "b": svc.Actor(usuario_id=m.odo_b.id, rol="odontologo", profesional_id=m.prof_b.id),
        "sec": svc.Actor(usuario_id=m.secretaria.id, rol="secretaria", profesional_id=None),
        "admin": svc.Actor(usuario_id=m.admin.id, rol="admin", profesional_id=None),
        "sin_prof": svc.Actor(usuario_id=m.odo_sin_prof.id, rol="odontologo", profesional_id=None),
    }
    return svc, repos, m, actores


async def _con_hc(sesion):
    svc, repos, m, a = await _escenario(sesion)
    hc = await svc.crear_historia(repos, a["a"], m.ana.id, None, None, AHORA)
    return svc, repos, m, a, hc


# --- 4.1 acceso ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_secretaria_lee_cualquier_paciente(sesion_pg):
    svc, repos, m, a = await _escenario(sesion_pg, con_turno=False)
    await svc.exigir_lectura(repos, a["sec"], m.ana.id)  # no levanta


@pytest.mark.asyncio
async def test_secretaria_no_escribe(sesion_pg):
    svc, repos, m, a = await _escenario(sesion_pg)
    with pytest.raises(svc.AccesoDenegadoError):
        await svc.exigir_escritura(repos, a["sec"], m.ana.id)


@pytest.mark.asyncio
async def test_odontologo_vinculado_lee_y_escribe(sesion_pg):
    svc, repos, m, a = await _escenario(sesion_pg)
    await svc.exigir_lectura(repos, a["a"], m.ana.id)
    await svc.exigir_escritura(repos, a["a"], m.ana.id)


@pytest.mark.asyncio
async def test_odontologo_sin_vinculo_denegado(sesion_pg):
    svc, repos, m, a = await _escenario(sesion_pg)  # Ana solo tiene turno con A
    for fn in (svc.exigir_lectura, svc.exigir_escritura):
        with pytest.raises(svc.AccesoDenegadoError):
            await fn(repos, a["b"], m.ana.id)


@pytest.mark.asyncio
async def test_odontologo_solo_turnos_cancelados_denegado(sesion_pg):
    svc, repos, m, a = await _escenario(sesion_pg, con_turno=False)
    await crear_turno(sesion_pg, m.ana, m.prof_a, m.sillon, estado="cancelado")
    with pytest.raises(svc.AccesoDenegadoError):
        await svc.exigir_lectura(repos, a["a"], m.ana.id)


@pytest.mark.asyncio
async def test_odontologo_sin_profesional_vinculado_denegado_incluso_en_lectura(sesion_pg):
    svc, repos, m, a = await _escenario(sesion_pg)
    for fn in (svc.exigir_lectura, svc.exigir_escritura):
        with pytest.raises(svc.AccesoDenegadoError):
            await fn(repos, a["sin_prof"], m.ana.id)


@pytest.mark.asyncio
async def test_admin_denegado_en_lectura_y_escritura(sesion_pg):
    svc, repos, m, a = await _escenario(sesion_pg)
    for fn in (svc.exigir_lectura, svc.exigir_escritura):
        with pytest.raises(svc.AccesoDenegadoError):
            await fn(repos, a["admin"], m.ana.id)


@pytest.mark.asyncio
async def test_construir_actor_resuelve_profesional_del_usuario(sesion_pg):
    from types import SimpleNamespace

    svc, repos, m, a = await _escenario(sesion_pg)
    usuario = SimpleNamespace(id=m.odo_a.id, rol=SimpleNamespace(nombre="odontologo"))
    actor = await svc.construir_actor(repos, usuario)
    assert actor.profesional_id == m.prof_a.id and actor.rol == "odontologo"
    sec = await svc.construir_actor(repos, SimpleNamespace(id=m.secretaria.id, rol=SimpleNamespace(nombre="secretaria")))
    assert sec.profesional_id is None


# --- 4.2 historia -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_crear_hc_ok_con_textos(sesion_pg):
    svc, repos, m, a = await _escenario(sesion_pg)
    hc = await svc.crear_historia(repos, a["a"], m.ana.id, "Hipertensión", "Penicilina", AHORA)
    assert hc.paciente_id == m.ana.id and hc.alergias == "Penicilina" and hc.deleted_at is None


@pytest.mark.asyncio
async def test_crear_hc_paciente_inexistente(sesion_pg):
    svc, repos, m, a = await _escenario(sesion_pg)
    with pytest.raises(svc.NoEncontradoError):
        await svc.crear_historia(repos, a["a"], 99999, None, None, AHORA)


@pytest.mark.asyncio
async def test_crear_hc_paciente_eliminado(sesion_pg):
    svc, repos, m, a = await _escenario(sesion_pg)
    m.ana.deleted_at = AHORA
    await sesion_pg.flush()
    with pytest.raises(svc.NoEncontradoError):
        await svc.crear_historia(repos, a["a"], m.ana.id, None, None, AHORA)


@pytest.mark.asyncio
async def test_crear_hc_duplicada_conflicto(sesion_pg):
    svc, repos, m, a, _ = await _con_hc(sesion_pg)
    with pytest.raises(svc.ConflictoError) as exc:
        await svc.crear_historia(repos, a["a"], m.ana.id, None, None, AHORA)
    assert "baja" not in str(exc.value)


@pytest.mark.asyncio
async def test_crear_hc_con_baja_conflicto_distinto(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    await svc.dar_de_baja_historia(repos, a["a"], hc.id, "cargada por error", AHORA)
    with pytest.raises(svc.ConflictoError) as exc:
        await svc.crear_historia(repos, a["a"], m.ana.id, None, None, AHORA)
    assert "baja" in str(exc.value)


@pytest.mark.asyncio
async def test_crear_hc_sin_vinculo_prohibido(sesion_pg):
    svc, repos, m, a = await _escenario(sesion_pg)
    with pytest.raises(svc.AccesoDenegadoError):
        await svc.crear_historia(repos, a["b"], m.ana.id, None, None, AHORA)


@pytest.mark.asyncio
async def test_patch_solo_campos_enviados_y_avanza_updated_at(sesion_pg):
    svc, repos, m, a = await _escenario(sesion_pg)
    hc = await svc.crear_historia(repos, a["a"], m.ana.id, "Asma", "Látex", AHORA)
    antes = hc.updated_at
    with freeze_time("2026-10-31 09:00:00"):
        hc = await svc.actualizar_historia(repos, a["a"], hc.id, {"alergias": "Penicilina"})
    assert hc.alergias == "Penicilina" and hc.antecedentes == "Asma"
    assert hc.updated_at == datetime(2026, 10, 31, 9, 0, tzinfo=timezone.utc)
    assert hc.updated_at != antes


@pytest.mark.asyncio
async def test_patch_con_null_borra_ese_campo_y_deja_el_otro(sesion_pg):
    svc, repos, m, a = await _escenario(sesion_pg)
    hc = await svc.crear_historia(repos, a["a"], m.ana.id, "Asma", "Látex", AHORA)
    hc = await svc.actualizar_historia(repos, a["a"], hc.id, {"alergias": None})
    assert hc.alergias is None and hc.antecedentes == "Asma"


@pytest.mark.asyncio
async def test_patch_secretaria_prohibido_y_hc_de_baja_no_encontrada(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    with pytest.raises(svc.AccesoDenegadoError):
        await svc.actualizar_historia(repos, a["sec"], hc.id, {"alergias": "x"})
    await svc.dar_de_baja_historia(repos, a["a"], hc.id, "motivo", AHORA)
    with pytest.raises(svc.NoEncontradoError):
        await svc.actualizar_historia(repos, a["a"], hc.id, {"alergias": "x"})


@pytest.mark.asyncio
async def test_baja_hc_conserva_hallazgos(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    h = await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "oclusal", "caries", AHORA)
    baja = await svc.dar_de_baja_historia(repos, a["a"], hc.id, "paciente duplicado", AHORA)
    assert baja.deleted_at == AHORA and baja.motivo_baja == "paciente duplicado"
    fila = await sesion_pg.scalar(sa.text("SELECT deleted_at FROM hallazgo_odontograma WHERE id=:i"), {"i": h.id})
    assert fila is None  # el hallazgo sigue intacto y activo en la DB
    for fn in (svc.obtener_historia, ):
        with pytest.raises(svc.NoEncontradoError):
            await fn(repos, a["a"], hc.id)


@pytest.mark.asyncio
async def test_baja_hc_repetida_es_no_encontrada(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    await svc.dar_de_baja_historia(repos, a["a"], hc.id, "motivo", AHORA)
    with pytest.raises(svc.NoEncontradoError):
        await svc.dar_de_baja_historia(repos, a["a"], hc.id, "otra vez", AHORA)


@pytest.mark.asyncio
async def test_buscar_historias_devuelve_cero_o_una(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    assert [h.id for h in await svc.buscar_historias(repos, a["a"], m.ana.id)] == [hc.id]
    assert await svc.buscar_historias(repos, a["sec"], m.beto.id) == []
    await svc.dar_de_baja_historia(repos, a["a"], hc.id, "motivo", AHORA)
    assert await svc.buscar_historias(repos, a["sec"], m.ana.id) == []


# --- 4.3 registrar hallazgo ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ausente_en_mesial_invalido(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    with pytest.raises(svc.ValidacionClinicaError):
        await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "mesial", "ausente", AHORA)


@pytest.mark.asyncio
@pytest.mark.parametrize("estado", ["ausente", "corona", "implante", "endodoncia"])
async def test_estado_de_pieza_completa_ok(sesion_pg, estado):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    h = await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "pieza_completa", estado, AHORA)
    assert h.estado == estado and h.cara == "pieza_completa"


@pytest.mark.asyncio
@pytest.mark.parametrize("estado,cara", [("caries", "oclusal"), ("obturacion", "mesial"), ("sano", "raiz"), ("caries", "pieza_completa")])
async def test_estado_de_cualquier_cara_ok(sesion_pg, estado, cara):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    h = await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, cara, estado, AHORA)
    assert (h.estado, h.cara) == (estado, cara)


@pytest.mark.asyncio
async def test_estado_desconocido_invalido(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    with pytest.raises(svc.ValidacionClinicaError):
        await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "oclusal", "desconocido", AHORA)


@pytest.mark.asyncio
async def test_estado_de_version_no_vigente_invalido(sesion_pg):
    from app.modelos import EstadoHallazgoCatalogo

    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    # V2 vigente sin "implante": solo existe en la V1 (ya no vigente).
    await sesion_pg.execute(sa.text("UPDATE estado_hallazgo_catalogo SET vigente=false"))
    sesion_pg.add_all([EstadoHallazgoCatalogo(codigo=c, version=2, nombre=c, alcance="cualquiera", vigente=True)
                       for c in ("caries", "fractura")])
    await sesion_pg.flush()
    with pytest.raises(svc.ValidacionClinicaError):
        await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "pieza_completa", "implante", AHORA)


@pytest.mark.asyncio
async def test_hallazgo_sella_autor_fecha_y_version(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    with freeze_time("2026-10-30 15:30:00"):
        h = await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "oclusal", "caries")
    assert h.profesional_id == m.prof_a.id
    assert h.fecha == datetime(2026, 10, 30, 15, 30, tzinfo=timezone.utc)
    assert h.catalogo_version == 1 and h.hc_id == hc.id and h.corrige_a_id is None


@pytest.mark.asyncio
async def test_version_nueva_conserva_hallazgos_v1(sesion_pg):
    from app.modelos import EstadoHallazgoCatalogo

    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    viejo = await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "oclusal", "caries", AHORA)
    await sesion_pg.execute(sa.text("UPDATE estado_hallazgo_catalogo SET vigente=false"))
    sesion_pg.add(EstadoHallazgoCatalogo(codigo="caries", version=2, nombre="Caries", alcance="cualquiera", vigente=True))
    await sesion_pg.flush()
    nuevo = await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "mesial", "caries", AHORA + timedelta(hours=1))
    assert (viejo.catalogo_version, nuevo.catalogo_version) == (1, 2)
    _, hallazgos = await svc.listar_hallazgos(repos, a["a"], hc.id)
    assert [h.id for h in hallazgos] == [nuevo.id, viejo.id]


@pytest.mark.asyncio
async def test_registrar_hallazgo_permisos(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    for quien in ("sec", "admin", "b", "sin_prof"):
        with pytest.raises(svc.AccesoDenegadoError):
            await svc.registrar_hallazgo(repos, a[quien], hc.id, 16, "oclusal", "caries", AHORA)
    with pytest.raises(svc.NoEncontradoError):
        await svc.registrar_hallazgo(repos, a["a"], 99999, 16, "oclusal", "caries", AHORA)


# --- 4.4 corregir / dar de baja -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_correccion_baja_original_y_crea_con_corrige_a(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    original = await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "oclusal", "caries", AHORA)
    nuevo = await svc.corregir_hallazgo(
        repos, a["a"], hc.id, original.id, 17, "mesial", "caries", "pieza equivocada",
        AHORA + timedelta(minutes=5),
    )
    assert nuevo.id != original.id and nuevo.corrige_a_id == original.id
    assert (nuevo.pieza_fdi, nuevo.cara) == (17, "mesial") and nuevo.deleted_at is None
    assert original.deleted_at == AHORA + timedelta(minutes=5) and original.motivo_baja == "pieza equivocada"
    _, activos = await svc.listar_hallazgos(repos, a["a"], hc.id)
    assert [h.id for h in activos] == [nuevo.id]


@pytest.mark.asyncio
async def test_correccion_de_anulado_conflicto(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    original = await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "oclusal", "caries", AHORA)
    await svc.dar_de_baja_hallazgo(repos, a["a"], hc.id, original.id, "error", AHORA)
    with pytest.raises(svc.ConflictoError):
        await svc.corregir_hallazgo(repos, a["a"], hc.id, original.id, 16, "oclusal", "caries", "x", AHORA)


@pytest.mark.asyncio
async def test_correccion_de_otro_autor_prohibida_y_fila_intacta(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_b, m.sillon)  # B también atiende a Ana (HC compartida)
    original = await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "oclusal", "caries", AHORA)
    with pytest.raises(svc.AccesoDenegadoError):
        await svc.corregir_hallazgo(repos, a["b"], hc.id, original.id, 16, "oclusal", "sano", "x", AHORA)
    with pytest.raises(svc.AccesoDenegadoError):
        await svc.dar_de_baja_hallazgo(repos, a["b"], hc.id, original.id, "x", AHORA)
    await sesion_pg.refresh(original)
    assert original.deleted_at is None and original.estado == "caries"


@pytest.mark.asyncio
async def test_hc_compartida_otro_odontologo_ve_todo(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_b, m.sillon)
    h = await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "oclusal", "caries", AHORA)
    _, vistos = await svc.listar_hallazgos(repos, a["b"], hc.id)
    assert [x.id for x in vistos] == [h.id]


@pytest.mark.asyncio
async def test_correccion_concurrente_conflicto(sesion_pg):
    """El UNIQUE parcial atrapa la carrera: ya existe una corrección de esa fila."""
    from app.modelos import HallazgoOdontograma

    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    original = await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "oclusal", "caries", AHORA)
    sesion_pg.add(HallazgoOdontograma(
        hc_id=hc.id, pieza_fdi=16, cara="oclusal", estado="sano", catalogo_version=1,
        fecha=AHORA, profesional_id=m.prof_a.id, corrige_a_id=original.id))
    await sesion_pg.flush()
    with pytest.raises(svc.ConflictoError):
        await svc.corregir_hallazgo(repos, a["a"], hc.id, original.id, 16, "oclusal", "obturacion", "x", AHORA)
    # La sesión sigue usable y el original no quedó dado de baja.
    await sesion_pg.refresh(original)
    assert original.deleted_at is None


@pytest.mark.asyncio
async def test_correccion_con_estado_invalido_no_toca_el_original(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    original = await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "oclusal", "caries", AHORA)
    with pytest.raises(svc.ValidacionClinicaError):
        await svc.corregir_hallazgo(repos, a["a"], hc.id, original.id, 16, "mesial", "ausente", "x", AHORA)
    assert original.deleted_at is None


@pytest.mark.asyncio
async def test_baja_hallazgo_ok_y_repetida_conflicto(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    h = await svc.registrar_hallazgo(repos, a["a"], hc.id, 16, "oclusal", "caries", AHORA)
    baja = await svc.dar_de_baja_hallazgo(repos, a["a"], hc.id, h.id, "cargado por error", AHORA)
    assert baja.deleted_at == AHORA and baja.motivo_baja == "cargado por error" and baja.estado == "caries"
    with pytest.raises(svc.ConflictoError):
        await svc.dar_de_baja_hallazgo(repos, a["a"], hc.id, h.id, "otra vez", AHORA)


@pytest.mark.asyncio
async def test_hallazgo_de_otra_hc_no_encontrado(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    await crear_turno(sesion_pg, m.beto, m.prof_a, m.sillon)
    hc_beto = await svc.crear_historia(repos, a["a"], m.beto.id, None, None, AHORA)
    h_beto = await svc.registrar_hallazgo(repos, a["a"], hc_beto.id, 16, "oclusal", "caries", AHORA)
    with pytest.raises(svc.NoEncontradoError):
        await svc.obtener_hallazgo(repos, a["a"], hc.id, h_beto.id)
    with pytest.raises(svc.NoEncontradoError):
        await svc.corregir_hallazgo(repos, a["a"], hc.id, h_beto.id, 16, "oclusal", "caries", "x", AHORA)
    with pytest.raises(svc.NoEncontradoError):
        await svc.dar_de_baja_hallazgo(repos, a["a"], hc.id, h_beto.id, "x", AHORA)


@pytest.mark.asyncio
async def test_catalogo_vigente_expone_version_y_estados(sesion_pg):
    svc, repos, m, a, hc = await _con_hc(sesion_pg)
    version, estados = await svc.catalogo_vigente(repos)
    assert version == 1 and {e.codigo for e in estados} >= {"caries", "ausente"}
