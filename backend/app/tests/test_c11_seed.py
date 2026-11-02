"""C-11 task 2.7: seed de obras sociales, planes y aranceles (D-21) contra PG real."""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db_utils import sesion_pg  # noqa: E402, F401


async def _contar(sesion, tabla):
    return await sesion.scalar(sa.text(f"SELECT count(*) FROM {tabla}"))


async def _sembrar(sesion):
    from app.db import seed

    await seed.seed_roles(sesion)
    await seed.seed_tratamientos(sesion)
    await seed.seed_obras_sociales(sesion)
    await sesion.flush()


@pytest.mark.asyncio
async def test_seed_doble_corrida_no_duplica_ni_falla(sesion_pg):
    await _sembrar(sesion_pg)
    primera = [await _contar(sesion_pg, t) for t in ("obra_social", "plan", "arancel")]
    await _sembrar(sesion_pg)
    segunda = [await _contar(sesion_pg, t) for t in ("obra_social", "plan", "arancel")]
    assert primera == segunda and primera[0] == 1 and primera[1] == 2 and primera[2] > 0


@pytest.mark.asyncio
async def test_seed_cubre_cinco_de_seis_y_deja_ext_001_sin_arancel(sesion_pg):
    await _sembrar(sesion_pg)
    cubiertos = (await sesion_pg.execute(sa.text(
        "SELECT DISTINCT t.codigo FROM arancel a JOIN tratamiento t "
        "ON t.codigo_nomenclador = a.codigo_nomenclador ORDER BY 1"))).scalars().all()
    assert sorted(cubiertos) == sorted(["CON-001", "PRO-001", "OBT-001", "END-001", "COR-001"])
    ext = await sesion_pg.scalar(sa.text(
        "SELECT codigo_nomenclador FROM tratamiento WHERE codigo = 'EXT-001'"))
    assert ext is not None  # tiene código, pero ningún plan lo cubre
    assert await sesion_pg.scalar(sa.text(
        "SELECT count(*) FROM arancel WHERE codigo_nomenclador = :c"), {"c": ext}) == 0


@pytest.mark.asyncio
async def test_seed_no_pisa_un_codigo_de_nomenclador_existente(sesion_pg):
    from app.db import seed

    await seed.seed_tratamientos(sesion_pg)
    await sesion_pg.execute(sa.text(
        "UPDATE tratamiento SET codigo_nomenclador = 'PROPIO-9' WHERE codigo = 'CON-001'"))
    await seed.seed_obras_sociales(sesion_pg)
    await seed.seed_obras_sociales(sesion_pg)
    assert await sesion_pg.scalar(sa.text(
        "SELECT codigo_nomenclador FROM tratamiento WHERE codigo = 'CON-001'")) == "PROPIO-9"


@pytest.mark.asyncio
async def test_seed_muestra_version_cerrada_y_cobertura_total_de_plan_plus(sesion_pg):
    await _sembrar(sesion_pg)
    cerrados = await sesion_pg.scalar(sa.text(
        "SELECT count(*) FROM arancel WHERE vigencia_hasta IS NOT NULL"))
    assert cerrados >= 1
    base, precio_plus = (await sesion_pg.execute(sa.text(
        "SELECT t.precio_base, a.precio FROM arancel a JOIN plan p ON p.id = a.plan_id "
        "JOIN tratamiento t ON t.codigo_nomenclador = a.codigo_nomenclador "
        "WHERE p.nombre = 'Plan Plus' AND t.codigo = 'PRO-001' AND a.vigencia_hasta IS NULL"
    ))).one()
    assert precio_plus >= base  # cubre al 100 %


def test_seed_obras_sociales_no_contiene_secretos_ni_datos_reales():
    texto = (BACKEND_DIR / "db" / "seed.py").read_text(encoding="utf-8")
    constantes = texto[texto.index("OBRA_SOCIAL_DEMO ="):texto.index("AGENDA_DEMO = {")]
    funcion = texto[texto.index("async def seed_obras_sociales"):texto.index("async def _usuario_demo")]
    bloque = constantes + funcion
    for prohibido in ("password", "secret", "token", "@", "http"):
        assert prohibido not in bloque.lower()
    assert "OS Ficticia Demo" in bloque


def test_seed_aranceles_demo_usan_precios_positivos_y_fechas_validas():
    from app.db.seed import ARANCELES_DEMO, NOMENCLADOR_DEMO, TRATAMIENTOS_DEMO

    codigos = {c for c, _, _ in TRATAMIENTOS_DEMO}
    assert set(NOMENCLADOR_DEMO) == codigos
    assert len(set(NOMENCLADOR_DEMO.values())) == len(NOMENCLADOR_DEMO)
    for plan, codigo, precio, desde, hasta in ARANCELES_DEMO:
        assert plan in ("Plan Base", "Plan Plus") and codigo in codigos
        assert precio > Decimal("0")
        assert hasta is None or hasta >= desde
        assert isinstance(desde, date)
