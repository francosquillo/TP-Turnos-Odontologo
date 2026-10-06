"""Task 3.2 RED: .env ignorado, .env.example trackeable."""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_gitignore_ignora_env():
    gitignore = REPO_ROOT / ".gitignore"
    assert gitignore.exists(), "falta .gitignore"
    lineas = [l.strip() for l in gitignore.read_text(encoding="utf-8").splitlines()]
    assert ".env" in lineas, ".gitignore debe listar .env en su propia linea"
    assert ".env.example" not in lineas, ".env.example NO debe estar ignorado"


def test_git_check_ignore_env():
    proc = subprocess.run(
        ["git", "check-ignore", "-v", ".env"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if "not a git repository" in proc.stderr:
        import pytest

        pytest.skip("repo git aun no inicializado (verificacion pendiente al inicar git)")
    assert proc.returncode == 0, ".env debe estar ignorado por git"
