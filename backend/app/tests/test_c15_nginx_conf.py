"""C-15 task 2.1: deploy/nginx.conf (SPA estatica, sin TLS, sin dominios)."""
import re
from pathlib import Path

CONF = Path(__file__).resolve().parents[3] / "frontend" / "deploy" / "nginx.conf"


def _conf() -> str:
    assert CONF.exists(), f"falta {CONF}"
    return CONF.read_text(encoding="utf-8")


def test_escucha_8080_con_fallback_spa():
    texto = _conf()
    assert re.search(r"listen\s+8080\s*;", texto)
    assert re.search(r"try_files\s+\$uri\s+\$uri/\s+/index\.html\s*;", texto)


def test_endurecimiento_basico():
    texto = _conf()
    assert re.search(r"server_tokens\s+off\s*;", texto)
    assert re.search(r"gzip\s+on\s*;", texto)
    assert "X-Content-Type-Options" in texto and "nosniff" in texto


def test_assets_con_cache_largo_e_index_sin_cache():
    texto = _conf()
    assert re.search(r"location\s+/assets/", texto)
    assert "immutable" in texto
    assert "no-cache" in texto


def test_assets_inexistentes_dan_404_no_index_html():
    # evita servir HTML como JS/CSS (error MIME) cuando falta un asset
    texto = _conf()
    bloque = re.search(r"location\s+/assets/\s*\{(.*?)\}", texto, flags=re.S)
    assert bloque, "falta location /assets/"
    assert "try_files $uri =404;" in bloque.group(1)


def test_sin_tls_ni_dominios_literales():
    texto = _conf()
    assert not re.search(r"listen\s+443", texto)
    assert "ssl" not in texto.lower()
    assert not re.search(r"server_name\s+(?!_\s*;)\S+", texto)
