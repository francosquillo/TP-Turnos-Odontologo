"""C-15 tasks 3.1-3.5: compose.prod.yml para Easypanel (lectura de archivo, sin Docker)."""
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE = REPO_ROOT / "compose.prod.yml"
DEV_COMPOSE = REPO_ROOT / "docker-compose.yml"
SERVICIOS = ("frontend", "api", "worker", "migrate", "db", "redis")


def _texto() -> str:
    assert COMPOSE.exists(), f"falta {COMPOSE}"
    return COMPOSE.read_text(encoding="utf-8")


def _data() -> dict:
    data = yaml.safe_load(_texto())
    assert isinstance(data, dict) and "services" in data
    return data


def _svc(nombre: str) -> dict:
    return _data()["services"][nombre]


def _cmd(nombre: str) -> str:
    c = _svc(nombre)["command"]
    return c if isinstance(c, str) else " ".join(c)


# --- 3.1 estructura ------------------------------------------------------------------

def test_servicios_y_sin_name_top_level():
    data = _data()
    assert "name" not in data, "Easypanel define el nombre del proyecto (S-3)"
    assert set(data["services"]) == set(SERVICIOS)


def test_imagenes_y_volumenes():
    data = _data()
    assert str(data["services"]["db"]["image"]).startswith("postgres:16")
    assert str(data["services"]["redis"]["image"]).startswith("redis:7")
    assert {"pgdata", "redisdata"} <= set(data["volumes"])


def test_sin_caddy_ni_acme():
    texto = _texto().lower()
    assert "caddy" not in texto
    assert "acme_email" not in texto


def test_frontend_build_usa_dockerfile_prod():
    build = _svc("frontend")["build"]
    assert build["context"] == "./frontend"
    assert build["dockerfile"] == "Dockerfile.prod"


# --- 3.2 sin exposicion al host ------------------------------------------------------

@pytest.mark.parametrize("nombre", SERVICIOS)
def test_ningun_servicio_publica_puertos_ni_container_name(nombre):
    svc = _svc(nombre)
    assert "ports" not in svc
    assert "container_name" not in svc


def test_expose_frontend_y_api():
    assert "8080" in [str(p) for p in _svc("frontend")["expose"]]
    assert "8000" in [str(p) for p in _svc("api")["expose"]]


def test_regresion_dev_sigue_publicando_puertos():
    texto = DEV_COMPOSE.read_text(encoding="utf-8")
    for var in ("API_PORT", "POSTGRES_PORT", "REDIS_PORT"):
        assert var in texto


# --- 3.3 secretos --------------------------------------------------------------------

def test_sin_credenciales_literales():
    texto = _texto()
    assert "turnos:turnos" not in texto
    assert "POSTGRES_PASSWORD: turnos" not in texto
    assert "POSTGRES_PASSWORD: \"turnos\"" not in texto


@pytest.mark.parametrize(
    "var", ["POSTGRES_PASSWORD", "JWT_SECRET", "SEED_ADMIN_PASSWORD", "CORS_ORIGINS", "VITE_API_URL"]
)
def test_variables_obligatorias_fallan_rapido(var):
    assert "${" + var + ":?" in _texto()


@pytest.mark.parametrize("nombre", SERVICIOS)
def test_ningun_servicio_usa_env_file(nombre):
    assert "env_file" not in _svc(nombre)


@pytest.mark.parametrize("nombre", ["api", "worker", "migrate"])
def test_database_url_armada_con_password_y_host_db(nombre):
    url = _svc(nombre)["environment"]["DATABASE_URL"]
    assert url.startswith("postgresql+asyncpg://")
    assert "${POSTGRES_PASSWORD" in url
    assert "@db:5432/" in url


def test_frontend_build_arg_interpolado():
    assert "${VITE_API_URL:?" in _svc("frontend")["build"]["args"]["VITE_API_URL"]


def test_api_recibe_jwt_cors_y_redis_internos():
    env = _svc("api")["environment"]
    assert "${JWT_SECRET:?" in env["JWT_SECRET"]
    assert "${CORS_ORIGINS:?" in env["CORS_ORIGINS"]
    assert env["REDIS_URL"] == "redis://redis:6379/0"


def test_migrate_recibe_credenciales_de_seed():
    env = _svc("migrate")["environment"]
    assert "${SEED_ADMIN_PASSWORD:?" in env["SEED_ADMIN_PASSWORD"]
    assert "SEED_ADMIN_EMAIL" in env


# --- 3.4 migracion -------------------------------------------------------------------

def test_migrate_one_off_con_alembic_y_seed():
    cmd = _cmd("migrate")
    assert "alembic upgrade head" in cmd and "app.db.seed" in cmd
    assert "&&" in cmd, "el seed solo corre si alembic termina bien"
    assert _svc("migrate")["restart"] == "no"
    dep = _svc("migrate")["depends_on"]
    assert dep["db"]["condition"] == "service_healthy"
    assert dep["redis"]["condition"] == "service_healthy"


@pytest.mark.parametrize("nombre", ["api", "worker"])
def test_api_y_worker_esperan_a_migrate(nombre):
    dep = _svc(nombre)["depends_on"]
    assert dep["migrate"]["condition"] == "service_completed_successfully"


def test_worker_command_es_el_del_worker():
    assert "app.worker.main" in _cmd("worker")


# --- 3.5 robustez --------------------------------------------------------------------

@pytest.mark.parametrize("nombre", ["frontend", "api", "worker", "db", "redis"])
def test_restart_unless_stopped(nombre):
    assert _svc(nombre)["restart"] == "unless-stopped"


def _hc(nombre: str) -> str:
    hc = _svc(nombre)["healthcheck"]
    t = hc["test"]
    return t if isinstance(t, str) else " ".join(t)


def test_healthchecks_de_servicios_que_sirven():
    assert "8080" in _hc("frontend") and "wget" in _hc("frontend")
    assert "/health" in _hc("api") and "8000" in _hc("api")
    assert "pg_isready" in _hc("db")
    assert "redis-cli" in _hc("redis") and "ping" in _hc("redis")


def test_api_uvicorn_detras_de_proxy():
    cmd = _cmd("api")
    assert "uvicorn app.main:app" in cmd
    assert "--workers ${UVICORN_WORKERS:-2}" in cmd
    assert "--proxy-headers" in cmd
    assert "--forwarded-allow-ips" in cmd


def test_db_monta_init_btree_gist_y_pgdata():
    vols = [str(v) for v in _svc("db")["volumes"]]
    assert any(v.startswith("pgdata:") for v in vols)
    assert any(v.startswith("./backend/db/init:") for v in vols)
    assert (REPO_ROOT / "backend" / "db" / "init").is_dir()


def test_db_usa_password_de_entorno():
    env = _svc("db")["environment"]
    assert "${POSTGRES_PASSWORD:?" in env["POSTGRES_PASSWORD"]
