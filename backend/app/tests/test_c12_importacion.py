"""C-12 8.2 y 8.3: importacion de pacientes CSV/XLSX con reporte por fila (D-11).

Servicio y endpoint sobre un repo falso (corre sin Postgres); la inserccion real
`INSERT ... ON CONFLICT DO NOTHING` y la unicidad del DNI se prueban aparte en Postgres real
(`test_pg_*`; sin Postgres se saltean y deben reportarse como NO EJECUTADAS).
"""
import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c12_fakes import FakeDb, override_auditoria  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401

ENCABEZADO = "nombre,apellido,dni,telefono,email"


class FakePacientes:
    """Repo en memoria: DNI unico entre todos (como `uq_paciente_dni`)."""

    def __init__(self, existentes=(), carrera=()):
        self.filas: list[dict] = [dict(f) for f in existentes]
        self.carrera = set(carrera)  # DNI que "otra transaccion" inserta justo antes

    async def dnis_activos(self, dnis):
        return {f["dni"] for f in self.filas if f.get("dni") in dnis and f.get("deleted_at") is None}

    async def insertar_si_no_existe(self, **datos):
        dni = datos.get("dni")
        if dni is not None and (dni in self.carrera or any(f.get("dni") == dni for f in self.filas)):
            return None
        self.filas.append(dict(datos))
        return len(self.filas)


def _csv(*filas: str, encabezado: str = ENCABEZADO, sep: str = ",") -> bytes:
    return ("\n".join([encabezado, *filas]) + "\n").encode("utf-8").replace(b",", sep.encode())


def _xlsx(filas: list[list[object]], encabezado: list[str] | None = None) -> bytes:
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.append(encabezado or ENCABEZADO.split(","))
    for fila in filas:
        hoja.append(fila)
    memoria = io.BytesIO()
    libro.save(memoria)
    return memoria.getvalue()


VALIDAS = (
    "Ana,Ficticia,30111001,11 4000-0001,ana@example.com",
    "Beto,Inventado,30111002,+54 9 11 4000-0002,",
    "Cora,Imaginaria,,,cora@example.com",
)


# --- 8.2 servicio ----------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csv_con_3_validas_una_sin_apellido_y_un_dni_repetido_crea_3_y_reporta_2_con_fila():
    from app.servicios.importacion_servicio import importar_pacientes

    repo = FakePacientes()
    contenido = _csv(*VALIDAS, "Dani,,30111004,,", "Eli,Repetida,30111001,,")
    r = await importar_pacientes(repo, "pacientes.csv", contenido)
    assert (r.creados, r.rechazados) == (3, 2)
    assert [(e.fila, "apellido" in e.motivo.lower()) for e in r.errores][0] == (5, True)
    assert r.errores[1].fila == 6 and "repetido" in r.errores[1].motivo.lower()
    assert len(repo.filas) == 3


@pytest.mark.asyncio
async def test_dni_existente_activo_rechaza_la_fila_y_no_toca_al_paciente():
    from app.servicios.importacion_servicio import importar_pacientes

    repo = FakePacientes(existentes=[{"nombre": "Original", "apellido": "Intacto", "dni": "30111001"}])
    r = await importar_pacientes(repo, "p.csv", _csv("Otro,Nombre,30111001,,", "Nueva,Persona,30111009,,"))
    assert (r.creados, r.rechazados) == (1, 1)
    assert r.errores[0].fila == 2 and "existe" in r.errores[0].motivo.lower()
    assert repo.filas[0] == {"nombre": "Original", "apellido": "Intacto", "dni": "30111001"}


@pytest.mark.asyncio
async def test_fila_que_pierde_la_carrera_por_el_dni_se_reporta_como_dni_existente():
    from app.servicios.importacion_servicio import importar_pacientes

    repo = FakePacientes(carrera={"30111005"})
    r = await importar_pacientes(repo, "p.csv", _csv("Fran,Carrera,30111005,,", "Gus,Libre,30111006,,"))
    assert (r.creados, r.rechazados) == (1, 1)
    assert r.errores[0].fila == 2 and "existe" in r.errores[0].motivo.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fila", "palabra"),
    [
        ("Ana,Ficticia,30111001,123,", "tel"),          # menos de 8 digitos
        ("Ana,Ficticia,30111001,abc,", "tel"),
        ("Ana,Ficticia,30111001,11 4000-0001,sin-arroba", "email"),
        ("Ana,Ficticia,30 111/001!,,", "dni"),
        (",Ficticia,30111001,,", "nombre"),
        ("A" * 121 + ",Ficticia,,,", "nombre"),
    ],
)
async def test_fila_mal_formada_se_rechaza_con_el_motivo_del_campo(fila, palabra):
    from app.servicios.importacion_servicio import importar_pacientes

    repo = FakePacientes()
    r = await importar_pacientes(repo, "p.csv", _csv(fila))
    assert (r.creados, r.rechazados) == (0, 1)
    assert palabra in r.errores[0].motivo.lower() and r.errores[0].fila == 2
    assert repo.filas == []


@pytest.mark.asyncio
async def test_telefono_se_normaliza_como_la_reserva_y_dni_pierde_puntos():
    from app.servicios.importacion_servicio import importar_pacientes

    repo = FakePacientes()
    await importar_pacientes(repo, "p.csv", _csv('Ana,Ficticia,"30.111.001","+54 9 11 4000-0001",'))
    assert repo.filas[0]["telefono"] == "5491140000001" and repo.filas[0]["dni"] == "30111001"


@pytest.mark.asyncio
async def test_xlsx_equivalente_da_el_mismo_resultado_que_el_csv():
    from app.servicios.importacion_servicio import importar_pacientes

    filas_csv = (*VALIDAS, "Dani,,30111004,,", "Eli,Repetida,30111001,,")
    r_csv = await importar_pacientes(FakePacientes(), "p.csv", _csv(*filas_csv))
    filas_xlsx = [
        ["Ana", "Ficticia", 30111001, "11 4000-0001", "ana@example.com"],   # DNI numerico
        ["Beto", "Inventado", 30111002, "+54 9 11 4000-0002", None],
        ["Cora", "Imaginaria", None, None, "cora@example.com"],
        ["Dani", None, 30111004, None, None],
        ["Eli", "Repetida", 30111001.0, None, None],                        # float entero
    ]
    r_xlsx = await importar_pacientes(FakePacientes(), "p.xlsx", _xlsx(filas_xlsx))
    assert r_xlsx == r_csv


@pytest.mark.asyncio
async def test_csv_con_punto_y_coma_y_bom_se_lee_igual():
    from app.servicios.importacion_servicio import importar_pacientes

    contenido = b"\xef\xbb\xbf" + _csv(*VALIDAS, encabezado="nombre;apellido;dni;telefono;email", sep=";")
    # Los datos tenian comas como separador: el helper las cambio por ';'.
    r = await importar_pacientes(FakePacientes(), "p.csv", contenido)
    assert (r.creados, r.rechazados) == (3, 0)


@pytest.mark.asyncio
async def test_filas_vacias_se_saltean_pero_cuentan_para_la_numeracion():
    from app.servicios.importacion_servicio import importar_pacientes

    r = await importar_pacientes(FakePacientes(), "p.csv", _csv("Ana,Ficticia,,,", ",,,,", "Beto,,,,"))
    assert (r.creados, r.rechazados) == (1, 1) and r.errores[0].fila == 4


@pytest.mark.asyncio
async def test_columnas_se_aceptan_en_otro_orden_y_con_mayusculas():
    from app.servicios.importacion_servicio import importar_pacientes

    contenido = "Apellido,NOMBRE,Email\nFicticia,Ana,ana@example.com\n".encode()
    repo = FakePacientes()
    r = await importar_pacientes(repo, "p.csv", contenido)
    assert (r.creados, repo.filas[0]["nombre"], repo.filas[0]["email"]) == (1, "Ana", "ana@example.com")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("nombre", "contenido"),
    [
        ("p.csv", b"nombre,dni\nAna,30111001\n"),                      # falta apellido
        ("p.xlsx", None),                                              # xlsx sin apellido
        ("p.txt", b"nombre,apellido\nAna,Ficticia\n"),                 # formato no admitido
        ("p.csv", b"\xff\xfe\x00no es utf8"),                          # no UTF-8
        ("p.xlsx", b"esto no es un zip"),                              # xlsx corrupto
        ("p.csv", b""),                                                # vacio
    ],
)
async def test_archivo_invalido_falla_entero_y_no_crea_nada(nombre, contenido):
    from app.servicios.importacion_servicio import ArchivoInvalidoError, importar_pacientes

    if contenido is None:
        contenido = _xlsx([["Ana", "30111001"]], encabezado=["nombre", "dni"])
    repo = FakePacientes()
    with pytest.raises(ArchivoInvalidoError):
        await importar_pacientes(repo, nombre, contenido)
    assert repo.filas == []


@pytest.mark.asyncio
async def test_mas_de_2000_filas_o_mas_de_1_mb_falla_entero_sin_crear_nada():
    from app.servicios.importacion_servicio import (
        ArchivoInvalidoError,
        MAX_BYTES,
        MAX_FILAS,
        importar_pacientes,
    )

    assert (MAX_FILAS, MAX_BYTES) == (2000, 1024 * 1024)
    repo = FakePacientes()
    justo = _csv(*[f"N{i},A{i},,," for i in range(MAX_FILAS)])
    r = await importar_pacientes(repo, "p.csv", justo)
    assert r.creados == MAX_FILAS
    repo = FakePacientes()
    with pytest.raises(ArchivoInvalidoError, match="2000"):
        await importar_pacientes(repo, "p.csv", _csv(*[f"N{i},A{i},,," for i in range(MAX_FILAS + 1)]))
    with pytest.raises(ArchivoInvalidoError, match="MB"):
        await importar_pacientes(repo, "p.csv", b"x" * (MAX_BYTES + 1))
    assert repo.filas == []


# --- 8.3 endpoint ----------------------------------------------------------------------------------

def _cliente(rol: str | None, repo: FakePacientes | None = None):
    from app.api.turnos import get_paciente_repo
    from app.core.deps import get_current_user, get_db
    from app.main import create_app

    app = create_app()
    db = FakeDb()

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    override_auditoria(app)
    app.dependency_overrides[get_paciente_repo] = lambda: repo or FakePacientes()
    if rol is not None:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=1, rol=SimpleNamespace(nombre=rol), activo=True)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), db


def _archivo(nombre: str, contenido: bytes, tipo: str = "text/csv"):
    return {"archivo": (nombre, contenido, tipo)}


@pytest.mark.asyncio
@pytest.mark.parametrize("rol", ["admin", "secretaria"])
async def test_api_admin_y_secretaria_importan_y_reciben_el_reporte(rol):
    repo = FakePacientes()
    cli, db = _cliente(rol, repo)
    async with cli:
        r = await cli.post("/pacientes/import", files=_archivo("p.csv", _csv(*VALIDAS, "Dani,,,,")))
    assert r.status_code == 200, r.text
    assert r.json() == {"creados": 3, "rechazados": 1, "errores": [{"fila": 5, "motivo": r.json()["errores"][0]["motivo"]}]}
    assert "apellido" in r.json()["errores"][0]["motivo"].lower()
    assert len(repo.filas) == 3 and db.commits == 1


@pytest.mark.asyncio
async def test_api_odontologo_403_y_sin_token_401_y_no_crea():
    repo = FakePacientes()
    cli, _ = _cliente("odontologo", repo)
    async with cli:
        r = await cli.post("/pacientes/import", files=_archivo("p.csv", _csv(*VALIDAS)))
    assert r.status_code == 403 and repo.filas == []
    cli, _ = _cliente(None, repo)
    async with cli:
        r = await cli.post("/pacientes/import", files=_archivo("p.csv", _csv(*VALIDAS)))
    assert r.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("nombre", "contenido"),
    [("p.pdf", b"%PDF-1.4"), ("p.csv", b"nombre,dni\nAna,1\n"), ("p.csv", b"x" * (1024 * 1024 + 1))],
    ids=["formato-pdf", "sin-apellido", "mas-de-1-mb"],
)
async def test_api_formato_o_columnas_o_tamano_invalidos_422_sin_crear_y_sin_commit(nombre, contenido):
    repo = FakePacientes()
    cli, db = _cliente("admin", repo)
    async with cli:
        r = await cli.post("/pacientes/import", files=_archivo(nombre, contenido, "application/octet-stream"))
    assert r.status_code == 422 and repo.filas == [] and db.commits == 0 and db.rollbacks == 1


@pytest.mark.asyncio
async def test_api_sin_el_campo_archivo_422():
    cli, _ = _cliente("admin")
    async with cli:
        r = await cli.post("/pacientes/import", data={"otro": "x"})
    assert r.status_code == 422


# --- dependencias (8.1) ----------------------------------------------------------------------------

def test_requirements_pina_python_multipart_y_openpyxl_con_version_fija():
    texto = (BACKEND_DIR / "requirements.txt").read_text(encoding="utf-8").lower()
    lineas = [ln.split("#")[0].strip() for ln in texto.splitlines()]
    assert any(ln.startswith("python-multipart==") for ln in lineas)
    assert any(ln.startswith("openpyxl==") for ln in lineas)
    assert not any(ln.startswith("pandas") for ln in lineas)


# --- Postgres real ---------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pg_importa_csv_con_filas_buenas_y_malas_contra_la_base_real(sesion_pg):
    import sqlalchemy as sa
    from app.repos.paciente_repo import PacienteRepository
    from app.servicios.importacion_servicio import importar_pacientes

    repo = PacienteRepository(sesion_pg)
    r = await importar_pacientes(repo, "p.csv", _csv(*VALIDAS, "Dani,,30111004,,", "Eli,Repetida,30111001,,"))
    assert (r.creados, r.rechazados) == (3, 2)
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM paciente")) == 3


@pytest.mark.asyncio
async def test_pg_dni_de_paciente_activo_o_dado_de_baja_rechaza_la_fila_sin_abortar_la_transaccion(sesion_pg):
    import sqlalchemy as sa
    from datetime import datetime, timezone
    from app.modelos import Paciente
    from app.repos.paciente_repo import PacienteRepository
    from app.servicios.importacion_servicio import importar_pacientes

    sesion_pg.add_all([
        Paciente(nombre="Activo", apellido="Existente", dni="30111001"),
        Paciente(nombre="Baja", apellido="Logica", dni="30111002", deleted_at=datetime.now(timezone.utc)),
    ])
    await sesion_pg.flush()
    r = await importar_pacientes(
        PacienteRepository(sesion_pg), "p.csv",
        _csv("X,Activo,30111001,,", "Y,Baja,30111002,,", "Z,Nueva,30111003,,"),
    )
    assert (r.creados, r.rechazados) == (1, 2)
    assert {e.fila for e in r.errores} == {2, 3}
    # La transaccion sigue viva (ON CONFLICT DO NOTHING no la aborta) y el activo no cambio.
    nombre = await sesion_pg.scalar(sa.text("SELECT nombre FROM paciente WHERE dni = '30111001'"))
    assert nombre == "Activo"


@pytest.mark.asyncio
async def test_pg_endpoint_importa_y_confirma(sesion_pg):
    import sqlalchemy as sa
    from c08_helpers import armar_cliente
    from c10_helpers import sembrar_c10

    m = await sembrar_c10(sesion_pg)
    antes = await sesion_pg.scalar(sa.text("SELECT count(*) FROM paciente"))
    cli, bearer, _ = await armar_cliente(sesion_pg)
    async with cli:
        r = await cli.post("/pacientes/import", files=_archivo("p.csv", _csv(*VALIDAS)),
                           headers=bearer(m.secretaria, "secretaria"))
        denegado = await cli.post("/pacientes/import", files=_archivo("p.csv", _csv(*VALIDAS)),
                                  headers=bearer(m.odo_a, "odontologo"))
    assert r.status_code == 200 and r.json()["creados"] == 3 and denegado.status_code == 403
    assert await sesion_pg.scalar(sa.text("SELECT count(*) FROM paciente")) == antes + 3
