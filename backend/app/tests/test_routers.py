"""Task 2.4 RED: 10 routers con prefix/tags visibles en /docs sin duplicados."""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

ESPERADOS = [
    "/auth",
    "/pacientes",
    "/profesionales",
    "/sillones",
    "/turnos",
    "/clinica",
    "/cobros",
    "/os",
    "/notificaciones",
    "/admin",
]


def test_routers_con_prefix_y_tags():
    import app.main  # noqa: F401
    from app.api import admin, auth, clinica, cobros, notificaciones, obras_sociales
    from app.api import pacientes, profesionales, sillones, turnos

    for mod in (auth, pacientes, profesionales, sillones, turnos, clinica, cobros, obras_sociales, notificaciones, admin):
        assert mod.router.prefix, f"{mod.__name__} sin prefix"
        assert mod.router.tags, f"{mod.__name__} sin tags"


def test_docs_lista_prefijos_sin_duplicados():
    import os

    os.environ.setdefault("JWT_SECRET", "t" * 32)
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/t")
    from app.main import app

    spec = app.openapi()
    paths = list(spec["paths"].keys())
    for prefijo in ESPERADOS:
        assert any(p == prefijo or p.startswith(prefijo + "/") for p in paths), f"falta {prefijo} en openapi"
    assert len(paths) == len(set(paths)), "paths duplicados en openapi"
