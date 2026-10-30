"""C-08 grupo 5: routers /historias, /odontograma y /tratamientos (HTTP real sobre PG real).

El token lo firma `crear_access_token`; usuarios y roles son filas reales.
Cubre la matriz de roles de D-07, los códigos de D-09 y `alergias` en la raíz de
cada respuesta clínica (D-08). Datos ficticios.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente, crear_turno, sembrar_mundo  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

HALLAZGO = {"pieza_fdi": 16, "cara": "oclusal", "estado": "caries"}


async def _entorno(sesion, *, con_turno=True, tratamientos=()):
    m = await sembrar_mundo(sesion)
    if con_turno:
        await crear_turno(sesion, m.ana, m.prof_a, m.sillon)
    for t in tratamientos:
        sesion.add(t)
    cli, bearer, app = await armar_cliente(sesion)
    h = {
        "a": bearer(m.odo_a, "odontologo"), "b": bearer(m.odo_b, "odontologo"),
        "sec": bearer(m.secretaria, "secretaria"), "admin": bearer(m.admin, "admin"),
        "sin_prof": bearer(m.odo_sin_prof, "odontologo"),
    }
    # Los routers hacen rollback ante un error de dominio y eso expira las
    # entidades de la sesión compartida: los tests solo necesitan los ids.
    m = SimpleNamespace(**{k: SimpleNamespace(id=v.id) for k, v in vars(m).items()})
    return m, cli, h, app


async def _abrir_hc(cli, h, m, **cuerpo):
    resp = await cli.post("/historias", json={"paciente_id": m.ana.id, **cuerpo}, headers=h["a"])
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- 5.1 catálogos ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_catalogo_y_tratamientos_responden_a_los_tres_roles(sesion_pg):
    from app.modelos import Tratamiento

    m, cli, h, _ = await _entorno(
        sesion_pg, tratamientos=[Tratamiento(codigo="OBT", nombre="Obturación", precio_base="1500.50")])
    async with cli:
        for quien in ("admin", "sec", "a"):
            cat = await cli.get("/odontograma/catalogo", headers=h[quien])
            assert cat.status_code == 200, quien
            assert cat.json()["version"] == 1
            estados = {e["codigo"]: e["alcance"] for e in cat.json()["estados"]}
            assert estados["ausente"] == "pieza" and estados["caries"] == "cualquiera" and len(estados) == 7
            trat = await cli.get("/tratamientos", headers=h[quien])
            assert trat.status_code == 200, quien
            assert trat.json() == [{"id": trat.json()[0]["id"], "codigo": "OBT",
                                    "codigo_nomenclador": None, "nombre": "Obturación",
                                    "precio_base": "1500.50"}]


@pytest.mark.asyncio
async def test_catalogos_sin_bearer_401_y_sin_escritura(sesion_pg):
    m, cli, h, _ = await _entorno(sesion_pg)
    async with cli:
        assert (await cli.get("/odontograma/catalogo")).status_code == 401
        assert (await cli.get("/tratamientos")).status_code == 401
        assert (await cli.post("/tratamientos", json={"codigo": "X"}, headers=h["admin"])).status_code == 405
        assert (await cli.post("/odontograma/catalogo", json={}, headers=h["admin"])).status_code == 405
        assert (await cli.delete("/tratamientos/1", headers=h["admin"])).status_code in (404, 405)


@pytest.mark.asyncio
async def test_catalogo_ordenado_por_codigo_en_tratamientos(sesion_pg):
    from app.modelos import Tratamiento

    m, cli, h, _ = await _entorno(sesion_pg, tratamientos=[
        Tratamiento(codigo="B", nombre="b", precio_base=1), Tratamiento(codigo="A", nombre="a", precio_base=2)])
    async with cli:
        resp = await cli.get("/tratamientos", headers=h["sec"])
    assert [t["codigo"] for t in resp.json()] == ["A", "B"]


# --- 5.2 historias -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_historias_matriz_de_roles(sesion_pg):
    m, cli, h, _ = await _entorno(sesion_pg)
    async with cli:
        hc = await _abrir_hc(cli, h, m, alergias="Penicilina", antecedentes="Asma")
        assert hc["alergias"] == "Penicilina" and hc["paciente_id"] == m.ana.id
        # lectura: secretaria y odontólogo vinculado; admin, sin vínculo y sin perfil no
        for quien, esperado in (("sec", 200), ("a", 200), ("admin", 403), ("b", 403), ("sin_prof", 403)):
            r = await cli.get(f"/historias/{hc['id']}", headers=h[quien])
            assert r.status_code == esperado, (quien, r.text)
            r = await cli.get(f"/historias?paciente_id={m.ana.id}", headers=h[quien])
            assert r.status_code == esperado, (quien, r.text)
        # escritura: solo el odontólogo vinculado
        for quien, esperado in (("sec", 403), ("admin", 403), ("b", 403), ("sin_prof", 403)):
            assert (await cli.patch(f"/historias/{hc['id']}", json={"alergias": "x"}, headers=h[quien])).status_code == esperado, quien
            assert (await cli.post(f"/historias/{hc['id']}/baja", json={"motivo_baja": "x"}, headers=h[quien])).status_code == esperado, quien
            assert (await cli.post("/historias", json={"paciente_id": m.beto.id}, headers=h[quien])).status_code == esperado, quien


@pytest.mark.asyncio
async def test_historias_sin_bearer_401(sesion_pg):
    m, cli, h, _ = await _entorno(sesion_pg)
    async with cli:
        assert (await cli.get("/historias?paciente_id=1")).status_code == 401
        assert (await cli.get("/historias/1")).status_code == 401
        assert (await cli.post("/historias", json={"paciente_id": 1})).status_code == 401
        assert (await cli.patch("/historias/1", json={})).status_code == 401
        assert (await cli.post("/historias/1/baja", json={"motivo_baja": "x"})).status_code == 401


@pytest.mark.asyncio
async def test_historias_busqueda_requiere_paciente_y_lista_vacia(sesion_pg):
    m, cli, h, _ = await _entorno(sesion_pg)
    async with cli:
        assert (await cli.get("/historias", headers=h["sec"])).status_code == 422
        vacia = await cli.get(f"/historias?paciente_id={m.beto.id}", headers=h["sec"])
        assert vacia.status_code == 200 and vacia.json() == []
        hc = await _abrir_hc(cli, h, m)
        lista = await cli.get(f"/historias?paciente_id={m.ana.id}", headers=h["a"])
        assert [x["id"] for x in lista.json()] == [hc["id"]]


@pytest.mark.asyncio
async def test_historias_alta_duplicada_409_y_paciente_inexistente_404(sesion_pg):
    m, cli, h, _ = await _entorno(sesion_pg)
    async with cli:
        await _abrir_hc(cli, h, m)
        dup = await cli.post("/historias", json={"paciente_id": m.ana.id}, headers=h["a"])
        assert dup.status_code == 409
        assert (await cli.post("/historias", json={"paciente_id": 99999}, headers=h["a"])).status_code == 404
        assert (await cli.get("/historias/99999", headers=h["a"])).status_code == 404


@pytest.mark.asyncio
async def test_historias_patch_parcial_normaliza_vacio_y_campo_extra_422(sesion_pg):
    m, cli, h, _ = await _entorno(sesion_pg)
    async with cli:
        hc = await _abrir_hc(cli, h, m, alergias="Látex", antecedentes="Asma")
        r = await cli.patch(f"/historias/{hc['id']}", json={"alergias": "   "}, headers=h["a"])
        assert r.status_code == 200
        assert r.json()["alergias"] is None and r.json()["antecedentes"] == "Asma"
        assert r.json()["updated_at"] >= hc["updated_at"]
        assert (await cli.patch(f"/historias/{hc['id']}", json={"nombre": "x"}, headers=h["a"])).status_code == 422
        assert (await cli.post("/historias", json={"paciente_id": m.beto.id, "x": 1}, headers=h["a"])).status_code == 422


@pytest.mark.asyncio
async def test_historias_baja_404_posterior_409_alta_y_delete_405(sesion_pg):
    m, cli, h, _ = await _entorno(sesion_pg)
    async with cli:
        hc = await _abrir_hc(cli, h, m)
        assert (await cli.post(f"/historias/{hc['id']}/baja", json={}, headers=h["a"])).status_code == 422
        baja = await cli.post(f"/historias/{hc['id']}/baja", json={"motivo_baja": "duplicada"}, headers=h["a"])
        assert baja.status_code == 200 and baja.json()["deleted_at"] is not None
        assert baja.json()["motivo_baja"] == "duplicada"
        for quien in ("a", "sec"):
            assert (await cli.get(f"/historias/{hc['id']}", headers=h[quien])).status_code == 404
            assert (await cli.get(f"/odontograma/{hc['id']}/hallazgos", headers=h[quien])).status_code == 404
        assert (await cli.get(f"/historias?paciente_id={m.ana.id}", headers=h["a"])).json() == []
        assert (await cli.post("/historias", json={"paciente_id": m.ana.id}, headers=h["a"])).status_code == 409
        assert (await cli.delete(f"/historias/{hc['id']}", headers=h["a"])).status_code == 405


# --- 5.3 odontograma --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hallazgos_alergias_en_la_raiz_de_las_cinco_respuestas(sesion_pg):
    m, cli, h, _ = await _entorno(sesion_pg)
    async with cli:
        hc = await _abrir_hc(cli, h, m, alergias="Penicilina")
        base = f"/odontograma/{hc['id']}/hallazgos"
        alta = await cli.post(base, json=HALLAZGO, headers=h["a"])
        assert alta.status_code == 201
        hid = alta.json()["hallazgo"]["id"]
        lista = await cli.get(base, headers=h["sec"])
        detalle = await cli.get(f"{base}/{hid}", headers=h["sec"])
        correc = await cli.put(f"{base}/{hid}", json={**HALLAZGO, "estado": "obturacion", "motivo": "evolucionó"}, headers=h["a"])
        baja = await cli.post(f"{base}/{correc.json()['hallazgo']['id']}/baja", json={"motivo_baja": "error"}, headers=h["a"])
        for r in (alta, lista, detalle, correc, baja):
            assert r.status_code in (200, 201), r.text
            assert r.json()["alergias"] == "Penicilina"
        assert "hallazgos" in lista.json() and all("hallazgo" in r.json() for r in (alta, detalle, correc, baja))


@pytest.mark.asyncio
async def test_alergias_null_presente_en_historias_y_hallazgos(sesion_pg):
    """`null` = no relevadas: la clave siempre viaja (no se omite) en cada respuesta clínica."""
    m, cli, h, _ = await _entorno(sesion_pg)
    async with cli:
        hc = await _abrir_hc(cli, h, m)  # sin alergias
        assert "alergias" in hc and hc["alergias"] is None
        base = f"/odontograma/{hc['id']}/hallazgos"
        alta = await cli.post(base, json=HALLAZGO, headers=h["a"])
        hid = alta.json()["hallazgo"]["id"]
        respuestas = [
            alta, await cli.get(base, headers=h["sec"]), await cli.get(f"{base}/{hid}", headers=h["sec"]),
            await cli.get(f"/historias/{hc['id']}", headers=h["sec"]),
        ]
        for r in respuestas:
            assert r.status_code in (200, 201) and "alergias" in r.json() and r.json()["alergias"] is None
        lista = await cli.get(f"/historias?paciente_id={m.ana.id}", headers=h["sec"])
        assert lista.json()[0]["alergias"] is None


@pytest.mark.asyncio
async def test_hallazgos_alta_sella_servidor_y_rechaza_campos_del_cliente(sesion_pg):
    m, cli, h, _ = await _entorno(sesion_pg)
    async with cli:
        hc = await _abrir_hc(cli, h, m)
        base = f"/odontograma/{hc['id']}/hallazgos"
        ok = (await cli.post(base, json=HALLAZGO, headers=h["a"])).json()["hallazgo"]
        assert ok["profesional_id"] == m.prof_a.id and ok["catalogo_version"] == 1
        assert ok["corrige_a_id"] is None and ok["deleted_at"] is None and ok["fecha"]
        for extra in ({"profesional_id": 9}, {"fecha": "2026-01-01T00:00:00Z"}, {"catalogo_version": 1}):
            assert (await cli.post(base, json={**HALLAZGO, **extra}, headers=h["a"])).status_code == 422, extra
        for malo in ({"pieza_fdi": 19}, {"pieza_fdi": 51}, {"cara": "incisal"}, {"cara": "lingual"},
                     {"estado": "desconocido"}, {"estado": "ausente", "cara": "mesial"}):
            assert (await cli.post(base, json={**HALLAZGO, **malo}, headers=h["a"])).status_code == 422, malo
        sin_cara = {k: v for k, v in HALLAZGO.items() if k != "cara"}
        assert (await cli.post(base, json=sin_cara, headers=h["a"])).status_code == 422


@pytest.mark.asyncio
async def test_hallazgos_filtro_pieza_invalida_422_y_historial_con_anulados(sesion_pg):
    m, cli, h, _ = await _entorno(sesion_pg)
    async with cli:
        hc = await _abrir_hc(cli, h, m)
        base = f"/odontograma/{hc['id']}/hallazgos"
        assert (await cli.get(f"{base}?pieza=30", headers=h["a"])).status_code == 422
        primero = (await cli.post(base, json=HALLAZGO, headers=h["a"])).json()["hallazgo"]
        await cli.post(base, json={**HALLAZGO, "pieza_fdi": 26}, headers=h["a"])
        corregido = (await cli.put(f"{base}/{primero['id']}", json={**HALLAZGO, "estado": "obturacion", "motivo": "evolución"}, headers=h["a"])).json()["hallazgo"]
        activos = (await cli.get(f"{base}?pieza=16", headers=h["a"])).json()["hallazgos"]
        assert [x["id"] for x in activos] == [corregido["id"]]
        todos = (await cli.get(f"{base}?pieza=16&incluir_anulados=true", headers=h["a"])).json()["hallazgos"]
        assert [x["id"] for x in todos] == [corregido["id"], primero["id"]]
        assert todos[1]["deleted_at"] and todos[1]["motivo_baja"] == "evolución"


@pytest.mark.asyncio
async def test_hallazgos_correccion_devuelve_id_nuevo_y_enlaza_al_original(sesion_pg):
    m, cli, h, _ = await _entorno(sesion_pg)
    async with cli:
        hc = await _abrir_hc(cli, h, m)
        base = f"/odontograma/{hc['id']}/hallazgos"
        original = (await cli.post(base, json=HALLAZGO, headers=h["a"])).json()["hallazgo"]
        r = await cli.put(f"{base}/{original['id']}", json={**HALLAZGO, "pieza_fdi": 17, "motivo": "pieza equivocada"}, headers=h["a"])
        assert r.status_code == 200
        nuevo = r.json()["hallazgo"]
        assert nuevo["id"] != original["id"] and nuevo["corrige_a_id"] == original["id"] and nuevo["pieza_fdi"] == 17
        viejo = (await cli.get(f"{base}/{original['id']}", headers=h["a"])).json()["hallazgo"]
        assert viejo["deleted_at"] and viejo["motivo_baja"] == "pieza equivocada"
        assert (await cli.put(f"{base}/{original['id']}", json={**HALLAZGO, "motivo": "otra"}, headers=h["a"])).status_code == 409
        assert (await cli.put(f"{base}/{nuevo['id']}", json=HALLAZGO, headers=h["a"])).status_code == 422  # sin motivo


@pytest.mark.asyncio
async def test_hallazgos_roles_y_autoria(sesion_pg):
    m, cli, h, _ = await _entorno(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_b, m.sillon)  # B también atiende a Ana
    await sesion_pg.commit()
    async with cli:
        hc = await _abrir_hc(cli, h, m)
        base = f"/odontograma/{hc['id']}/hallazgos"
        hid = (await cli.post(base, json=HALLAZGO, headers=h["a"])).json()["hallazgo"]["id"]
        for quien in ("admin",):
            assert (await cli.get(base, headers=h[quien])).status_code == 403
            assert (await cli.get(f"{base}/{hid}", headers=h[quien])).status_code == 403
        for quien in ("sec", "admin", "sin_prof"):
            assert (await cli.post(base, json=HALLAZGO, headers=h[quien])).status_code == 403, quien
            assert (await cli.put(f"{base}/{hid}", json={**HALLAZGO, "motivo": "x"}, headers=h[quien])).status_code == 403, quien
            assert (await cli.post(f"{base}/{hid}/baja", json={"motivo_baja": "x"}, headers=h[quien])).status_code == 403, quien
        # B ve la HC compartida pero no corrige lo de A
        assert (await cli.get(base, headers=h["b"])).status_code == 200
        assert (await cli.put(f"{base}/{hid}", json={**HALLAZGO, "motivo": "x"}, headers=h["b"])).status_code == 403
        assert (await cli.post(f"{base}/{hid}/baja", json={"motivo_baja": "x"}, headers=h["b"])).status_code == 403
        assert (await cli.get(f"{base}/{hid}", headers=h["a"])).json()["hallazgo"]["deleted_at"] is None


@pytest.mark.asyncio
async def test_hallazgo_es_propio_segun_quien_consulta(sesion_pg):
    """El front no conoce su profesional_id: el servidor marca `es_propio` (solo el autor corrige)."""
    m, cli, h, _ = await _entorno(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_b, m.sillon)
    await sesion_pg.commit()
    async with cli:
        hc = await _abrir_hc(cli, h, m)
        base = f"/odontograma/{hc['id']}/hallazgos"
        alta = (await cli.post(base, json=HALLAZGO, headers=h["a"])).json()["hallazgo"]
        assert alta["es_propio"] is True
        for quien, esperado in (("a", True), ("b", False), ("sec", False)):
            lista = (await cli.get(base, headers=h[quien])).json()["hallazgos"]
            assert [x["es_propio"] for x in lista] == [esperado], quien
            detalle = (await cli.get(f"{base}/{alta['id']}", headers=h[quien])).json()["hallazgo"]
            assert detalle["es_propio"] is esperado, quien
        corr = (await cli.put(f"{base}/{alta['id']}", json={**HALLAZGO, "motivo": "x"}, headers=h["a"])).json()["hallazgo"]
        assert corr["es_propio"] is True


@pytest.mark.asyncio
async def test_hallazgos_baja_repetida_409_y_hallazgo_de_otra_hc_404(sesion_pg):
    m, cli, h, _ = await _entorno(sesion_pg)
    await crear_turno(sesion_pg, m.beto, m.prof_a, m.sillon)
    await sesion_pg.commit()
    async with cli:
        hc = await _abrir_hc(cli, h, m)
        otra = (await cli.post("/historias", json={"paciente_id": m.beto.id}, headers=h["a"])).json()
        hid = (await cli.post(f"/odontograma/{hc['id']}/hallazgos", json=HALLAZGO, headers=h["a"])).json()["hallazgo"]["id"]
        base = f"/odontograma/{otra['id']}/hallazgos"
        assert (await cli.get(f"{base}/{hid}", headers=h["a"])).status_code == 404
        assert (await cli.post(f"{base}/{hid}/baja", json={"motivo_baja": "x"}, headers=h["a"])).status_code == 404
        propio = f"/odontograma/{hc['id']}/hallazgos/{hid}/baja"
        assert (await cli.post(propio, json={}, headers=h["a"])).status_code == 422
        assert (await cli.post(propio, json={"motivo_baja": "error"}, headers=h["a"])).status_code == 200
        assert (await cli.post(propio, json={"motivo_baja": "otra vez"}, headers=h["a"])).status_code == 409
        assert (await cli.get(f"/odontograma/{hc['id']}/hallazgos/99999", headers=h["a"])).status_code == 404


@pytest.mark.asyncio
async def test_odontograma_sin_bearer_401_y_sin_delete(sesion_pg):
    m, cli, h, _ = await _entorno(sesion_pg)
    async with cli:
        hc = await _abrir_hc(cli, h, m)
        base = f"/odontograma/{hc['id']}/hallazgos"
        assert (await cli.get(base)).status_code == 401
        assert (await cli.post(base, json=HALLAZGO)).status_code == 401
        assert (await cli.put(f"{base}/1", json=HALLAZGO)).status_code == 401
        assert (await cli.delete(f"{base}/1", headers=h["a"])).status_code == 405


# --- 5.4 openapi ----------------------------------------------------------------------------------

def test_c08_openapi_sin_delete_ni_escrituras_de_catalogo():
    from app.main import app

    paths = app.openapi()["paths"]
    clinicos = {p: ops for p, ops in paths.items()
                if p.startswith(("/historias", "/odontograma", "/tratamientos"))}
    assert clinicos, "faltan los routers clínicos"
    for ruta, ops in clinicos.items():
        assert "delete" not in ops, f"DELETE en {ruta}"
    assert set(paths["/odontograma/catalogo"]) == {"get"}
    assert set(paths["/tratamientos"]) == {"get"}
    assert set(paths["/historias"]) == {"get", "post"}
