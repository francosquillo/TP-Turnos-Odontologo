"""C-15 task 4.1: .env.prod.example con placeholders, versionable, sin secretos reales."""
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_PROD = REPO_ROOT / ".env.prod.example"

REQUERIDAS = (
    "DOMAIN", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "JWT_SECRET",
    "JWT_EXPIRE_MIN", "SEED_ADMIN_EMAIL", "SEED_ADMIN_PASSWORD", "CORS_ORIGINS",
    "VITE_API_URL", "UVICORN_WORKERS", "WHATSAPP_MOCK", "TZ",
)


def _vars() -> dict[str, str]:
    assert ENV_PROD.exists(), f"falta {ENV_PROD}"
    out: dict[str, str] = {}
    for linea in ENV_PROD.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def test_lista_todas_las_variables_requeridas():
    faltan = [k for k in REQUERIDAS if k not in _vars()]
    assert not faltan, f"faltan: {faltan}"


def test_valores_fijos_del_contrato():
    v = _vars()
    assert v["JWT_EXPIRE_MIN"] == "30"
    assert v["WHATSAPP_MOCK"] == "true"
    assert v["TZ"] == "America/Argentina/Buenos_Aires"


def test_cors_json_y_api_url_https():
    v = _vars()
    assert v["CORS_ORIGINS"].startswith('["https://') and v["CORS_ORIGINS"].endswith('"]')
    assert v["VITE_API_URL"].startswith("https://api.")


def test_placeholders_sin_secretos_reales():
    v = _vars()
    for clave in ("POSTGRES_PASSWORD", "JWT_SECRET", "SEED_ADMIN_PASSWORD"):
        assert not re.fullmatch(r"[0-9a-fA-F]{32,}", v[clave]), f"{clave} parece secreto real"
        assert "cambiar" in v[clave].lower() or "changeme" in v[clave].lower() or "<" in v[clave]


def test_sin_acme_email():
    assert "ACME_EMAIL" not in ENV_PROD.read_text(encoding="utf-8")


def _check_ignore(nombre: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "check-ignore", "-q", nombre], capture_output=True, text=True, cwd=str(REPO_ROOT)
    )


def test_env_prod_example_no_ignorado_y_env_si():
    assert _check_ignore(".env.prod.example").returncode == 1, "debe poder versionarse"
    assert _check_ignore(".env").returncode == 0, ".env debe seguir ignorado"
    assert _check_ignore(".env.prod").returncode == 0, ".env.prod (con secretos) debe ignorarse"
