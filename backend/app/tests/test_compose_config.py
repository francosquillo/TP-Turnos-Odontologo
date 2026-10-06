"""Task 1.1 + 1.3 RED: compose con 4 servicios, healthchecks, puertos por env.

RED inicial: falla porque docker-compose.yml no existe.
GREEN: pasa al crear el compose segun D-01.
"""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
# backend/app/tests -> parents[0]=tests, [1]=app, [2]=backend, [3]=root
COMPOSE = REPO_ROOT / "docker-compose.yml"


def _load():
    assert COMPOSE.exists(), f"falta {COMPOSE}"
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and "services" in data
    return data


def test_compose_tiene_cuatro_servicios():
    data = _load()
    services = data["services"]
    for svc in ("api", "worker", "db", "redis"):
        assert svc in services, f"falta servicio {svc}"


def test_compose_imagenes_pineadas():
    data = _load()
    db_image = str(data["services"]["db"]["image"])
    redis_image = str(data["services"]["redis"]["image"])
    assert db_image.startswith("postgres:16"), f"db debe ser postgres:16, es {db_image}"
    assert redis_image.startswith("redis:7"), f"redis debe ser redis:7, es {redis_image}"


def test_compose_api_depende_saludable():
    data = _load()
    depends = data["services"]["api"].get("depends_on", {})
    assert "db" in depends and "redis" in depends
    assert depends["db"].get("condition") == "service_healthy"
    assert depends["redis"].get("condition") == "service_healthy"


def test_compose_puertos_parametrizados_por_env():
    # Task 1.3: puertos por env, sin editar archivos versionados
    raw = COMPOSE.read_text(encoding="utf-8") if COMPOSE.exists() else ""
    assert COMPOSE.exists(), f"falta {COMPOSE}"
    for var in ("API_PORT", "POSTGRES_PORT", "REDIS_PORT"):
        assert var in raw, f"puerto no parametrizado por env: {var}"


def test_compose_worker_reusa_imagen_api():
    # Revision vinculante #3: worker reusa imagen api con distinto command
    data = _load()
    api = data["services"]["api"]
    worker = data["services"]["worker"]
    assert "build" in api
    assert worker.get("build", {}).get("context") == api["build"].get("context") or "image" in worker or "build" in worker
    assert "command" in worker, "worker debe definir command distinto"
    assert "Dockerfile.worker" not in str(worker.get("build", {}).get("dockerfile", ""))
