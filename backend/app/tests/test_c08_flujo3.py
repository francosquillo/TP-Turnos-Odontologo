"""C-08 task 9.1: Flujo 3 de punta a punta (HTTP real + PG real).

Odontólogo con turno `asistido` abre la historia, carga alergias, registra una
caries en 16 oclusal, luego la obturación, corrige un error y da de baja otro
hallazgo. El historial de 16 muestra todo; la secretaria lee y no escribe; el
admin recibe 403; `GET /tratamientos` devuelve el seed. Datos ficticios.
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c08_helpers import armar_cliente, crear_turno, sembrar_mundo  # noqa: E402
from db_utils import sesion_pg  # noqa: E402, F401


@pytest.mark.asyncio
async def test_flujo3_historia_clinica_y_odontograma_de_punta_a_punta(sesion_pg):
    from app.db.seed import seed_tratamientos

    m = await sembrar_mundo(sesion_pg)
    await crear_turno(sesion_pg, m.ana, m.prof_a, m.sillon, estado="asistido")
    await seed_tratamientos(sesion_pg)
    cli, bearer, _ = await armar_cliente(sesion_pg)
    odo, sec, admin = (bearer(m.odo_a, "odontologo"), bearer(m.secretaria, "secretaria"),
                       bearer(m.admin, "admin"))
    ana_id = m.ana.id
    async with cli:
        # 1. abre la HC y carga alergias
        hc = (await cli.post("/historias", json={"paciente_id": ana_id}, headers=odo)).json()
        assert hc["alergias"] is None
        r = await cli.patch(f"/historias/{hc['id']}", json={"alergias": "Penicilina", "antecedentes": "Hipertensión"}, headers=odo)
        assert r.status_code == 200 and r.json()["alergias"] == "Penicilina"
        base = f"/odontograma/{hc['id']}/hallazgos"

        # 2. caries en 16 oclusal, luego obturación
        caries = (await cli.post(base, json={"pieza_fdi": 16, "cara": "oclusal", "estado": "caries"}, headers=odo)).json()["hallazgo"]
        obturacion = (await cli.post(base, json={"pieza_fdi": 16, "cara": "oclusal", "estado": "obturacion"}, headers=odo)).json()["hallazgo"]

        # 3. corrige un error (pieza equivocada) y da de baja otro cargado por error
        error = (await cli.post(base, json={"pieza_fdi": 26, "cara": "mesial", "estado": "caries"}, headers=odo)).json()["hallazgo"]
        corregido = (await cli.put(f"{base}/{error['id']}", json={"pieza_fdi": 36, "cara": "mesial", "estado": "caries", "motivo": "pieza equivocada"}, headers=odo)).json()["hallazgo"]
        otro = (await cli.post(base, json={"pieza_fdi": 16, "cara": "distal", "estado": "sano"}, headers=odo)).json()["hallazgo"]
        baja = await cli.post(f"{base}/{otro['id']}/baja", json={"motivo_baja": "cargado por error"}, headers=odo)
        assert baja.status_code == 200 and baja.json()["alergias"] == "Penicilina"

        # 4. el historial de 16 muestra todo, del más reciente al más antiguo
        completo = (await cli.get(f"{base}?pieza=16&incluir_anulados=true", headers=odo)).json()
        assert completo["alergias"] == "Penicilina"
        assert [h["id"] for h in completo["hallazgos"]] == [otro["id"], obturacion["id"], caries["id"]]
        assert completo["hallazgos"][0]["motivo_baja"] == "cargado por error"
        activos = (await cli.get(f"{base}?pieza=16", headers=odo)).json()["hallazgos"]
        assert [h["id"] for h in activos] == [obturacion["id"], caries["id"]]
        # la corrección dejó al original dado de baja y a la fila nueva enlazada
        todo = {h["id"]: h for h in (await cli.get(f"{base}?incluir_anulados=true", headers=odo)).json()["hallazgos"]}
        assert todo[error["id"]]["deleted_at"] and todo[corregido["id"]]["corrige_a_id"] == error["id"]

        # 5. la secretaria lee y no escribe
        assert (await cli.get(base, headers=sec)).status_code == 200
        assert (await cli.get(f"/historias/{hc['id']}", headers=sec)).json()["alergias"] == "Penicilina"
        assert (await cli.post(base, json={"pieza_fdi": 11, "cara": "oclusal", "estado": "caries"}, headers=sec)).status_code == 403
        assert (await cli.patch(f"/historias/{hc['id']}", json={"alergias": "x"}, headers=sec)).status_code == 403
        assert (await cli.put(f"{base}/{caries['id']}", json={"pieza_fdi": 16, "cara": "oclusal", "estado": "sano", "motivo": "x"}, headers=sec)).status_code == 403

        # 6. el admin no accede a datos clínicos
        assert (await cli.get(base, headers=admin)).status_code == 403
        assert (await cli.get(f"/historias?paciente_id={ana_id}", headers=admin)).status_code == 403

        # 7. el catálogo de tratamientos sale del seed y cualquier rol lo lee
        for cabecera in (odo, sec, admin):
            trat = await cli.get("/tratamientos", headers=cabecera)
            assert trat.status_code == 200 and len(trat.json()) == 6
        assert [t["codigo"] for t in trat.json()] == sorted(t["codigo"] for t in trat.json())
