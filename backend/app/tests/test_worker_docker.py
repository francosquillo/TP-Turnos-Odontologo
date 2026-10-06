"""Task 2.5 RED: Dockerfile buildeable + worker stub con heartbeat."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
WORKER_MAIN = REPO_ROOT / "backend" / "app" / "worker" / "main.py"


def test_dockerfile_python_312_slim():
    assert DOCKERFILE.exists(), f"falta {DOCKERFILE}"
    texto = DOCKERFILE.read_text(encoding="utf-8")
    assert "3.12" in texto and "slim" in texto
    assert "uvicorn" in texto


def test_worker_stub_heartbeat():
    assert WORKER_MAIN.exists(), f"falta {WORKER_MAIN}"
    texto = WORKER_MAIN.read_text(encoding="utf-8")
    assert "heartbeat" in texto.lower() or "stub C-01" in texto


def test_worker_importable():
    import sys

    backend = REPO_ROOT / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    import app.worker.main as worker_main

    assert hasattr(worker_main, "main") or hasattr(worker_main, "heartbeat")
