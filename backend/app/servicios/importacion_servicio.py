"""Importacion de pacientes desde CSV o XLSX con reporte por fila (C-12 R4, D-11).

Politica parcial: se crean las filas validas y se reportan las invalidas, en la transaccion del
router. Un archivo que no se puede leer, sin columnas obligatorias o por encima de los limites
(1 MB, 2000 filas) falla entero con `ArchivoInvalidoError` ANTES de crear nada. El DNI repetido
en el archivo o ya existente rechaza solo esa fila; la insercion usa `ON CONFLICT DO NOTHING`
(repo), asi una carrera por el DNI tampoco aborta la transaccion. El telefono se normaliza como
en la reserva online. El parseo es sincrono y corre en un hilo. Sin pandas.
"""
import asyncio
import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime

from app.esquemas.importacion import ErrorFila, ImportacionOut
from app.servicios.reserva_servicio import TelefonoInvalidoError, normalizar_telefono

MAX_BYTES = 1024 * 1024
MAX_FILAS = 2000
COLUMNAS = ("nombre", "apellido", "dni", "telefono", "email")
OBLIGATORIAS = ("nombre", "apellido")
_LARGO_NOMBRE = 120
_DNI = re.compile(r"[0-9A-Za-z]{1,20}")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class ArchivoInvalidoError(ValueError):
    """El archivo completo se rechaza (formato, columnas o limites): no se crea nada."""


@dataclass(frozen=True)
class _Fila:
    numero: int
    datos: dict[str, str]


def _texto(valor: object) -> str:
    """Celda de planilla a texto: un DNI numerico no queda como `30111001.0`."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return str(valor).strip()


def _armar_filas(encabezado: list[str], filas_crudas: list[tuple[int, list[str]]]) -> list[_Fila]:
    columnas = [c.strip().lower() for c in encabezado]
    faltan = [c for c in OBLIGATORIAS if c not in columnas]
    if faltan:
        raise ArchivoInvalidoError(f"faltan columnas obligatorias: {', '.join(faltan)}")
    posiciones = {c: columnas.index(c) for c in COLUMNAS if c in columnas}
    filas: list[_Fila] = []
    for numero, celdas in filas_crudas:
        if not any(c.strip() for c in celdas):
            continue  # fila vacia: no es un error, pero cuenta en la numeracion
        datos = {
            c: (celdas[i].strip() if i < len(celdas) else "") for c, i in posiciones.items()
        }
        filas.append(_Fila(numero, datos))
    return filas


def _leer_csv(contenido: bytes) -> list[_Fila]:
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ArchivoInvalidoError("el CSV debe estar codificado en UTF-8") from None
    if not texto.strip():
        raise ArchivoInvalidoError("el archivo está vacío")
    primera = texto.splitlines()[0]
    delimitador = ";" if primera.count(";") > primera.count(",") else ","
    lector = csv.reader(io.StringIO(texto, newline=""), delimiter=delimitador)
    try:
        encabezado = next(lector)
        crudas: list[tuple[int, list[str]]] = []
        for numero, celdas in enumerate(lector, start=2):
            if numero - 1 > MAX_FILAS:
                raise ArchivoInvalidoError(f"el archivo supera el máximo de {MAX_FILAS} filas")
            crudas.append((numero, celdas))
    except csv.Error:
        raise ArchivoInvalidoError("el CSV no se puede leer") from None
    return _armar_filas(encabezado, crudas)


def _leer_xlsx(contenido: bytes) -> list[_Fila]:
    from openpyxl import load_workbook

    try:
        libro = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    except Exception:  # noqa: BLE001 - zip corrupto, no es XLSX, etc.: todos son "no se puede leer"
        raise ArchivoInvalidoError("el XLSX no se puede leer") from None
    try:
        filas = libro.active.iter_rows(values_only=True)
        try:
            encabezado = [_texto(c) for c in next(filas)]
        except StopIteration:
            raise ArchivoInvalidoError("el archivo está vacío") from None
        crudas: list[tuple[int, list[str]]] = []
        for numero, celdas in enumerate(filas, start=2):
            if numero - 1 > MAX_FILAS:
                raise ArchivoInvalidoError(f"el archivo supera el máximo de {MAX_FILAS} filas")
            crudas.append((numero, [_texto(c) for c in celdas]))
    finally:
        libro.close()
    return _armar_filas(encabezado, crudas)


def leer_archivo(nombre_archivo: str, contenido: bytes) -> list[_Fila]:
    """Filas del archivo con su numero (encabezado = fila 1); falla entero si no es valido."""
    if len(contenido) > MAX_BYTES:
        raise ArchivoInvalidoError("el archivo supera el máximo de 1 MB")
    nombre = (nombre_archivo or "").lower()
    if nombre.endswith(".csv"):
        return _leer_csv(contenido)
    if nombre.endswith(".xlsx"):
        return _leer_xlsx(contenido)
    raise ArchivoInvalidoError("formato no admitido: subí un archivo CSV o XLSX")


def _validar(datos: dict[str, str]) -> tuple[dict[str, str | None], list[str]]:
    """Datos normalizados de una fila y la lista de motivos de rechazo (vacia si es valida)."""
    motivos: list[str] = []
    for campo in OBLIGATORIAS:
        valor = datos.get(campo, "")
        if not valor:
            motivos.append(f"falta el {campo}")
        elif len(valor) > _LARGO_NOMBRE:
            motivos.append(f"{campo} demasiado largo (máximo {_LARGO_NOMBRE} caracteres)")
    dni = datos.get("dni", "").replace(".", "").replace(" ", "")
    if dni and not _DNI.fullmatch(dni):
        motivos.append("DNI con formato inválido")
    telefono = datos.get("telefono", "")
    if telefono:
        try:
            telefono = normalizar_telefono(telefono)
        except TelefonoInvalidoError:
            motivos.append("teléfono inválido (mínimo 8 dígitos)")
    email = datos.get("email", "")
    if email and (len(email) > 320 or not _EMAIL.fullmatch(email)):
        motivos.append("email con formato inválido")
    limpio = {
        "nombre": datos.get("nombre") or None,
        "apellido": datos.get("apellido") or None,
        "dni": dni or None,
        "telefono": telefono or None,
        "email": email or None,
    }
    return limpio, motivos


async def importar_pacientes(repo, nombre_archivo: str, contenido: bytes) -> ImportacionOut:
    """Valida cada fila, crea las validas y reporta las invalidas. El router confirma."""
    filas = await asyncio.to_thread(leer_archivo, nombre_archivo, contenido)
    errores: list[ErrorFila] = []
    validas: list[tuple[int, dict[str, str | None]]] = []
    vistos: dict[str, int] = {}
    for fila in filas:
        limpio, motivos = _validar(fila.datos)
        dni = limpio["dni"]
        if not motivos and dni is not None:
            if dni in vistos:
                motivos.append(f"DNI repetido en el archivo (ya figura en la fila {vistos[dni]})")
            else:
                vistos[dni] = fila.numero
        if motivos:
            errores.append(ErrorFila(fila=fila.numero, motivo="; ".join(motivos)))
        else:
            validas.append((fila.numero, limpio))
    dnis = [d["dni"] for _, d in validas if d["dni"] is not None]
    existentes = await repo.dnis_activos(dnis) if dnis else set()
    creados = 0
    for numero, datos in validas:
        if datos["dni"] in existentes or await repo.insertar_si_no_existe(**datos) is None:
            errores.append(ErrorFila(fila=numero, motivo="el DNI ya existe entre los pacientes"))
        else:
            creados += 1
    errores.sort(key=lambda e: e.fila)
    return ImportacionOut(creados=creados, rechazados=len(errores), errores=errores)
