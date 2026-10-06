"""Task 4.1-4.3 RED: scaffold Vite+React+TS estricto, api-client, auth-context, pages.

RED inicial: falta frontend/.
GREEN: archivos presentes, tsconfig strict, cero `: any` en src.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FRONT = REPO_ROOT / "frontend"
SRC = FRONT / "src"


def test_frontend_scaffold_presente():
    for rel in (
        "package.json",
        "tsconfig.json",
        "vite.config.ts",
        "index.html",
        "Dockerfile",
        "src/main.tsx",
        "src/App.tsx",
        "src/shared/api-client.ts",
        "src/shared/auth-context.tsx",
        "src/pages/Reservas.tsx",
        "src/pages/Confirmar.tsx",
        "src/pages/Seguridad.tsx",
    ):
        assert (FRONT / rel).is_file(), f"falta frontend/{rel}"


def test_tsconfig_estricto():
    import json

    assert (FRONT / "tsconfig.json").is_file(), "falta tsconfig.json"
    tsconfig = json.loads((FRONT / "tsconfig.json").read_text(encoding="utf-8"))
    opts = tsconfig.get("compilerOptions", {})
    assert opts.get("strict") is True
    assert opts.get("noImplicitAny") is True


def test_src_sin_any():
    assert SRC.is_dir(), "falta frontend/src"
    ofensores = [
        p for p in SRC.rglob("*.ts*")
        if ": any" in p.read_text(encoding="utf-8")
    ]
    assert ofensores == [], f"archivos con `any`: {ofensores}"


def test_api_client_tipado_contra_health():
    p = SRC / "shared" / "api-client.ts"
    assert p.is_file(), "falta shared/api-client.ts"
    texto = p.read_text(encoding="utf-8")
    assert "/health" in texto
    assert "Promise<" in texto
