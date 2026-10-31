"""Helpers C-09: mundo de presupuestos sobre PG real (HC, hallazgos, tratamientos).

Todo es ficticio. Se apoya en `c08_helpers.sembrar_mundo`; las fixtures usan
`create_all`, no la migración.
"""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from c08_helpers import crear_turno, sembrar_mundo

PRECIOS = {
    "CON-001": Decimal("1000.50"),
    "PRO-001": Decimal("500.00"),
    "OBT-001": Decimal("15000.00"),
    "GRATIS": Decimal("0.00"),
}
FECHA_HALLAZGO = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


async def sembrar_c09(sesion, *, vincular_a: bool = True) -> SimpleNamespace:
    """Mundo C-08 + tratamientos + HC de Ana con 3 hallazgos activos.

    Ana tiene un turno `asistido` con el profesional A (vínculo). Hallazgos:
    16 oclusal caries (h1), 26 mesial caries (h2), 36 pieza_completa ausente (h3).
    """
    from app.modelos import HallazgoOdontograma, HistoriaClinica, Tratamiento

    m = await sembrar_mundo(sesion)
    if vincular_a:
        await crear_turno(sesion, m.ana, m.prof_a, m.sillon, estado="asistido")
    trat = {
        codigo: Tratamiento(codigo=codigo, nombre=f"Trat {codigo}", precio_base=precio)
        for codigo, precio in PRECIOS.items()
    }
    sesion.add_all(trat.values())
    hc = HistoriaClinica(paciente_id=m.ana.id)
    sesion.add(hc)
    await sesion.flush()

    def hallazgo(pieza, cara, estado):
        return HallazgoOdontograma(
            hc_id=hc.id, pieza_fdi=pieza, cara=cara, estado=estado,
            catalogo_version=1, fecha=FECHA_HALLAZGO, profesional_id=m.prof_a.id,
        )

    h1 = hallazgo(16, "oclusal", "caries")
    h2 = hallazgo(26, "mesial", "caries")
    h3 = hallazgo(36, "pieza_completa", "ausente")
    sesion.add_all([h1, h2, h3])
    await sesion.flush()
    m.trat, m.hc, m.h1, m.h2, m.h3 = trat, hc, h1, h2, h3
    return m
