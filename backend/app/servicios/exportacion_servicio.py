"""Exportacion total del consultorio en un ZIP de CSV (C-12 R5, D-12). Solo admin.

Un CSV por tabla de `Base.metadata` en orden de dependencias, mas `LEEME.txt` con la
declaracion de datos ficticios. Nunca salen hashes de contrasena ni de token, ni el contenido
de los mensajes (puede llevar enlaces con token). Las celdas de texto se neutralizan como en
la exportacion de liquidaciones. Incluye las tablas clinicas (D-12): es el camino de RN-GL-01
para llevarse los datos; la ruta es solo admin. El servicio solo lee; el ZIP se arma en un
hilo porque es CPU sincrono.
"""
import asyncio
import csv
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Column, Table, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import Base
from app.servicios.liquidacion_export import celda_segura

# Columnas que nunca salen, ademas de toda columna cuyo nombre contenga "hash".
COLUMNAS_EXCLUIDAS = frozenset({("notificacion", "payload")})
LEEME = (
    "Exportación total del consultorio\r\n"
    "Fecha de exportación: {fecha}\r\n"
    "\r\n"
    "AVISO: los datos de esta demostración son ficticios y de prueba; no corresponden a\r\n"
    "pacientes ni a operaciones reales.\r\n"
    "\r\n"
    "Contenido: un archivo CSV por tabla (UTF-8, separador ';'), incluidas las tablas clínicas.\r\n"
    "Tratalo como información sensible: solo lo descarga el administrador.\r\n"
    "No se incluyen hashes de contraseñas ni de tokens ni el contenido de los mensajes.\r\n"
    "\r\n"
    "Tablas ({cantidad}):\r\n"
    "{detalle}\r\n"
)


@dataclass(frozen=True)
class TablaExportada:
    nombre: str
    columnas: list[str]
    filas: list[tuple[object, ...]]


def columnas_exportables(tabla: Table) -> list[Column]:
    """Columnas de la tabla que pueden salir en la exportacion."""
    return [
        c for c in tabla.columns
        if "hash" not in c.name and (tabla.name, c.name) not in COLUMNAS_EXCLUIDAS
    ]


def _celda(valor: object) -> str:
    """Texto de una celda: numeros tal cual (un negativo no es una formula), texto neutralizado."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, Decimal)):
        return str(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, (dict, list)):
        return celda_segura(json.dumps(valor, ensure_ascii=False, default=str))
    return celda_segura(str(valor))


def _a_csv(tabla: TablaExportada) -> bytes:
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(tabla.columnas)
    for fila in tabla.filas:
        escritor.writerow([_celda(v) for v in fila])
    return b"\xef\xbb\xbf" + salida.getvalue().encode("utf-8")


def armar_zip(tablas: list[TablaExportada], *, fecha: date) -> bytes:
    """ZIP con un CSV por tabla y el LEEME. Funcion pura."""
    detalle = "\r\n".join(f"- {t.nombre}.csv: {len(t.filas)} filas" for t in tablas)
    leeme = LEEME.format(fecha=fecha.isoformat(), cantidad=len(tablas), detalle=detalle)
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("LEEME.txt", leeme.encode("utf-8"))
        for tabla in tablas:
            z.writestr(f"{tabla.nombre}.csv", _a_csv(tabla))
    return memoria.getvalue()


async def leer_tablas(sesion: AsyncSession) -> list[TablaExportada]:
    """Lee todas las tablas exportables en orden de dependencias (solo SELECT)."""
    tablas: list[TablaExportada] = []
    for tabla in Base.metadata.sorted_tables:
        columnas = columnas_exportables(tabla)
        if not columnas:
            continue
        orden = [c for c in tabla.primary_key.columns if c in columnas]
        consulta = select(*columnas).order_by(*orden)
        filas = (await sesion.execute(consulta)).all()
        tablas.append(TablaExportada(tabla.name, [c.name for c in columnas], [tuple(f) for f in filas]))
    return tablas


async def exportar_total(sesion: AsyncSession, fecha: date | None = None) -> bytes:
    """ZIP completo de la base. `fecha` por defecto es hoy en la zona operativa."""
    if fecha is None:
        from app.servicios.caja_servicio import hoy_operativo

        fecha = hoy_operativo()
    tablas = await leer_tablas(sesion)
    return await asyncio.to_thread(armar_zip, tablas, fecha=fecha)
