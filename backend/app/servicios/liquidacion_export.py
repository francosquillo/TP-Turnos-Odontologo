"""Informe de liquidación para la obra social: modelo de filas, CSV y PDF (C-11, D-17).

Funciones puras sobre `LiquidacionDetalleOut`: no tocan la base. Las filas llevan paciente,
fecha, código, descripción, cantidad y monto; NUNCA pieza dental, hallazgo ni notas clínicas
(RN-CL-04). Las prestaciones en revisión manual salen identificadas como no liquidadas. El CSV
neutraliza las celdas que una planilla podría ejecutar como fórmula. El PDF se arma con
Platypus; es síncrono y el router lo corre en un hilo (`asyncio.to_thread`).
"""
import csv
import io
from dataclasses import dataclass
from decimal import Decimal
from xml.sax.saxutils import escape

from app.esquemas.liquidacion import LiquidacionDetalleOut

COLUMNAS = ("Plan", "Fecha", "Paciente", "Codigo", "Descripcion", "Cantidad", "Monto", "Estado")
LEYENDA = "Datos ficticios de demostracion: no corresponden a pacientes ni a operaciones reales."
ESTADO_LIQUIDADA = "liquidada"
ESTADO_REVISION = "NO LIQUIDADA (revision manual)"
_PREFIJOS_FORMULA = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class FilaInforme:
    plan: str
    fecha: str
    paciente: str
    codigo: str
    descripcion: str
    cantidad: int
    monto: Decimal
    estado: str


@dataclass(frozen=True)
class GrupoInforme:
    plan: str
    subtotal: Decimal
    filas: list[FilaInforme]


@dataclass(frozen=True)
class Informe:
    obra_social: str
    periodo: str
    estado: str
    grupos: list[GrupoInforme]
    total: Decimal
    leyenda: str


def construir_informe(detalle: LiquidacionDetalleOut) -> Informe:
    """Agrupa por plan, con subtotales; el total es el de la liquidación."""
    grupos = [
        GrupoInforme(
            plan=plan.plan_nombre, subtotal=plan.subtotal,
            filas=[
                FilaInforme(
                    plan=plan.plan_nombre, fecha=item.fecha_prestacion.isoformat(),
                    paciente=item.paciente_nombre, codigo=item.codigo,
                    descripcion=item.descripcion, cantidad=item.cantidad, monto=item.monto,
                    estado=ESTADO_REVISION if item.revision else ESTADO_LIQUIDADA,
                )
                for item in plan.items
            ],
        )
        for plan in detalle.planes
    ]
    return Informe(
        obra_social=detalle.obra_social, periodo=detalle.periodo.strftime("%Y-%m"),
        estado=detalle.estado, grupos=grupos, total=detalle.total, leyenda=LEYENDA,
    )


# --- CSV -----------------------------------------------------------------------------------------

def _celda(valor: str) -> str:
    """Una celda de texto que empieza con =, +, -, @ o control se escribe con un apóstrofo."""
    return "'" + valor if valor.startswith(_PREFIJOS_FORMULA) else valor


celda_segura = _celda  # nombre publico: lo reutiliza la exportacion total (C-12)


def a_csv(informe: Informe) -> bytes:
    """UTF-8 con BOM (Excel), separador `;` y fin de línea CRLF."""
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(["Obra social", _celda(informe.obra_social)])
    escritor.writerow(["Periodo", informe.periodo])
    escritor.writerow(["Estado", informe.estado])
    escritor.writerow(["Aviso", informe.leyenda])
    escritor.writerow([])
    escritor.writerow(COLUMNAS)
    vacias = [""] * 5
    for grupo in informe.grupos:
        for f in grupo.filas:
            escritor.writerow([
                _celda(f.plan), f.fecha, _celda(f.paciente), _celda(f.codigo),
                _celda(f.descripcion), f.cantidad, f"{f.monto:.2f}", f.estado,
            ])
        escritor.writerow([_celda(f"Subtotal {grupo.plan}"), *vacias, f"{grupo.subtotal:.2f}", ""])
    escritor.writerow(["TOTAL", *vacias, f"{informe.total:.2f}", ""])
    return b"\xef\xbb\xbf" + salida.getvalue().encode("utf-8")


# --- PDF -----------------------------------------------------------------------------------------

def a_pdf(informe: Informe) -> bytes:
    """Documento A4 apaisado con una tabla por plan, subtotales, total y la leyenda."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    estilos = getSampleStyleSheet()
    pequeno = estilos["BodyText"].clone("celda", fontSize=8, leading=10)
    buffer = io.BytesIO()
    # Sin compresión: el texto queda legible en el binario y la prueba verifica el contenido.
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm, pageCompression=0,
        title=f"Liquidacion {informe.periodo}",
    )
    elementos = [
        Paragraph(escape(f"Liquidacion {informe.periodo} - {informe.obra_social}"), estilos["Title"]),
        Paragraph(escape(f"Estado: {informe.estado}"), estilos["Normal"]),
        Paragraph(escape(informe.leyenda), estilos["Italic"]),
        Spacer(1, 4 * mm),
    ]
    encabezado = [Paragraph(f"<b>{c}</b>", pequeno) for c in COLUMNAS[1:]]
    for grupo in informe.grupos:
        elementos.append(Paragraph(escape(f"Plan: {grupo.plan}"), estilos["Heading3"]))
        datos = [encabezado] + [
            [Paragraph(escape(str(v)), pequeno) for v in (
                f.fecha, f.paciente, f.codigo, f.descripcion, f.cantidad, f"{f.monto:.2f}",
                f.estado)]
            for f in grupo.filas
        ]
        datos.append([
            "", "", "", "", Paragraph("<b>Subtotal</b>", pequeno),
            Paragraph(f"<b>{grupo.subtotal:.2f}</b>", pequeno), "",
        ])
        tabla = Table(datos, repeatRows=1, colWidths=[24 * mm, 55 * mm, 24 * mm, 65 * mm,
                                                      22 * mm, 28 * mm, 45 * mm])
        tabla.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elementos += [tabla, Spacer(1, 3 * mm)]
    elementos.append(Paragraph(f"<b>TOTAL: {informe.total:.2f}</b>", estilos["Heading2"]))
    doc.build(elementos)
    return buffer.getvalue()


__all__ = [
    "COLUMNAS", "ESTADO_LIQUIDADA", "ESTADO_REVISION", "FilaInforme", "GrupoInforme",
    "Informe", "LEYENDA", "a_csv", "a_pdf", "construir_informe",
]
