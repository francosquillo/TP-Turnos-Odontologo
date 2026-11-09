"""C-15 tasks 1.1, 1.2, 2.2, 2.3: Dockerfiles endurecidos y de produccion (sin Docker)."""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
BACKEND_IGNORE = REPO_ROOT / "backend" / ".dockerignore"
FRONT_DEV = REPO_ROOT / "frontend" / "Dockerfile"
FRONT_PROD = REPO_ROOT / "frontend" / "Dockerfile.prod"
FRONT_IGNORE = REPO_ROOT / "frontend" / ".dockerignore"


def _read(path: Path) -> str:
    assert path.exists(), f"falta {path}"
    return path.read_text(encoding="utf-8")


def _instrucciones(texto: str) -> list[str]:
    return [l.strip() for l in texto.splitlines() if l.strip() and not l.strip().startswith("#")]


def _ignore_lines(path: Path) -> set[str]:
    return {l.strip() for l in _read(path).splitlines() if l.strip() and not l.startswith("#")}


# --- 1.1 backend ---------------------------------------------------------------------

def test_backend_usuario_no_root_antes_de_cmd():
    lineas = _instrucciones(_read(BACKEND_DOCKERFILE))
    users = [i for i, l in enumerate(lineas) if l.upper().startswith("USER ")]
    cmds = [i for i, l in enumerate(lineas) if l.upper().startswith("CMD ")]
    assert users and cmds, "debe declarar USER y CMD"
    assert users[-1] < cmds[-1], "USER debe ir antes de CMD"
    usuario = lineas[users[-1]].split(None, 1)[1].strip()
    assert usuario.split(":")[0] not in ("root", "0")


def test_backend_copia_alembic_y_ini():
    texto = _read(BACKEND_DOCKERFILE)
    assert re.search(r"COPY\s+(--chown=\S+\s+)?alembic\s", texto)
    assert re.search(r"COPY\s+(--chown=\S+\s+)?alembic\.ini\s", texto)
    assert re.search(r"COPY\s+(--chown=\S+\s+)?app\s", texto)  # no se pierde app/


def test_backend_env_y_sin_healthcheck():
    texto = _read(BACKEND_DOCKERFILE)
    assert "PYTHONUNBUFFERED=1" in texto
    assert "PYTHONDONTWRITEBYTECODE=1" in texto
    assert "HEALTHCHECK" not in texto  # worker/migrate no sirven HTTP


def test_backend_cmd_sin_cambios_de_dev():
    texto = _read(BACKEND_DOCKERFILE)
    assert 'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]' in texto


# --- 1.2 backend .dockerignore -------------------------------------------------------

def test_backend_dockerignore_excluye_secretos_y_cache():
    lineas = _ignore_lines(BACKEND_IGNORE)
    for patron in (".env", "__pycache__", "*.pyc", ".pytest_cache"):
        assert patron in lineas or f"{patron}/" in lineas, f"falta {patron}"


def test_backend_dockerignore_excluye_variantes_env():
    lineas = _ignore_lines(BACKEND_IGNORE)
    assert ".env*" in lineas or ".env.*" in lineas


# --- 2.2 frontend prod ---------------------------------------------------------------

def test_frontend_prod_multistage_y_build():
    texto = _read(FRONT_PROD)
    froms = re.findall(r"^FROM\s+(\S+)", texto, flags=re.M | re.I)
    assert len(froms) >= 2
    assert "npm ci" in texto
    assert "npm run build" in texto
    assert re.search(r"^ARG\s+VITE_API_URL", texto, flags=re.M)


def test_frontend_prod_etapa_final_nginx_unprivileged():
    texto = _read(FRONT_PROD)
    froms = re.findall(r"^FROM\s+(\S+)", texto, flags=re.M | re.I)
    assert re.fullmatch(r"nginxinc/nginx-unprivileged:[\w.]+-alpine", froms[-1]), froms[-1]
    assert "/usr/share/nginx/html" in texto
    assert "deploy/nginx.conf" in texto
    assert re.search(r"^EXPOSE\s+8080\b", texto, flags=re.M)


def test_frontend_prod_sin_servidor_dev():
    lineas = _instrucciones(_read(FRONT_PROD))
    finales = [l for l in lineas if l.upper().startswith(("CMD", "ENTRYPOINT"))]
    for l in finales:
        assert "vite" not in l.lower() and "npm run dev" not in l.lower()
    assert "npm run dev" not in "\n".join(lineas)


def test_frontend_prod_mime_types_incluidos_en_conf():
    # D-03 condicion: sin errores de MIME en CSS/JS -> el conf debe incluir mime.types
    conf = _read(REPO_ROOT / "frontend" / "deploy" / "nginx.conf")
    assert re.search(r"include\s+/etc/nginx/mime\.types\s*;", conf)


def test_frontend_dev_dockerfile_sigue_existiendo():
    texto = _read(FRONT_DEV)
    assert '"npm", "run", "dev"' in texto


# --- 2.3 frontend .dockerignore ------------------------------------------------------

def test_frontend_dockerignore_excluye_artefactos():
    lineas = _ignore_lines(FRONT_IGNORE)
    for patron in ("node_modules", "dist", ".env", ".vite"):
        assert patron in lineas or f"{patron}/" in lineas, f"falta {patron}"


def test_frontend_dockerignore_excluye_variantes_env():
    lineas = _ignore_lines(FRONT_IGNORE)
    assert ".env*" in lineas or ".env.*" in lineas
