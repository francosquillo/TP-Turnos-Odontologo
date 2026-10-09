"""Task 3.1 RED: .env.example completo con placeholders, sin secretos reales."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_EXAMPLE = REPO_ROOT / ".env.example"

REQUERIDAS = [
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_SECRET",
    "JWT_EXPIRE_MIN",
    "WHATSAPP_TOKEN",
    "WHATSAPP_PHONE_ID",
    "WHATSAPP_WEBHOOK_SECRET",
    "WHATSAPP_MOCK",
    "GCAL_CLIENT_ID",
    "GCAL_SECRET",
    "CORS_ORIGINS",
    "SEED_ADMIN_EMAIL",
    "SEED_ADMIN_PASSWORD",
    "TZ",
]


def test_env_example_tiene_todas_las_claves():
    assert ENV_EXAMPLE.exists(), f"falta {ENV_EXAMPLE}"
    texto = ENV_EXAMPLE.read_text(encoding="utf-8")
    for clave in REQUERIDAS:
        assert clave in texto, f"falta {clave} en .env.example"


def test_env_example_defaults_segurs():
    assert ENV_EXAMPLE.exists(), f"falta {ENV_EXAMPLE}"
    texto = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "WHATSAPP_MOCK=true" in texto
    assert "JWT_EXPIRE_MIN=30" in texto
    assert "http://localhost:5173" in texto
    assert "America/Argentina/Buenos_Aires" in texto


def test_env_example_sin_secretos_reales():
    assert ENV_EXAMPLE.exists(), f"falta {ENV_EXAMPLE}"
    texto = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "CHANGEME" in texto or "placeholder" in texto.lower() or "example" in texto.lower()
    for linea in texto.splitlines():
        if linea.startswith("JWT_SECRET="):
            valor = linea.split("=", 1)[1].strip()
            assert valor == "" or "CHANGEME" in valor or "placeholder" in valor.lower()


def test_env_example_trae_refresh_expire():
    """C-03 task 5.1 RED: REFRESH_EXPIRE_DAYS con default 7 documentado."""
    assert ENV_EXAMPLE.exists(), f"falta {ENV_EXAMPLE}"
    texto = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "REFRESH_EXPIRE_DAYS=7" in texto
