"""Task 2.1 RED: estructura importable backend/app + main.py.

RED inicial: ModuleNotFoundError sin la estructura.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/app/tests -> backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_import_smoke_main():
    import app.main as main

    assert hasattr(main, "app") or hasattr(main, "create_app")


def test_estructura_capas_existe():
    base = BACKEND_DIR / "app"
    for capa in ("api", "servicios", "repos", "modelos", "esquemas", "worker", "tests", "core"):
        assert (base / capa).is_dir(), f"falta capa {capa}"
    assert (base / "main.py").is_file()
