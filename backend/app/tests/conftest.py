"""Task 2.1 GREEN: hace importable el paquete backend/app en tests locales."""
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]  # backend/app/tests/conftest -> backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("JWT_SECRET", "test-secret-c01-32-chars-minimo!")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/t")
