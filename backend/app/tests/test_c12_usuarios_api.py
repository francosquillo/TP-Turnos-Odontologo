"""C-12 2.1 y 2.2: alta y edicion de usuarios por admin (D-02), sobre repos falsos.

Corre sin Postgres. El login real (Argon2 + lookup case-insensitive) se verifica llamando a
`iniciar_sesion` con el mismo repo, como hace el endpoint.
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from c03_fakes import FakeStore  # noqa: E402
from c12_fakes import FakeRepoAdmin, app_admin_con, fabricar_usuario  # noqa: E402

ALTA = {"nombre": "Sofía Nueva", "email": "sofia.nueva@example.com", "password": "Clave-1234", "rol": "secretaria"}


def _repo(**extra) -> FakeRepoAdmin:
    return FakeRepoAdmin(
        [
            fabricar_usuario(id=1, rol="admin", email="admin@demo.test"),
            fabricar_usuario(id=2, rol="secretaria", email="secre@demo.test", password_plana="Vieja-1234"),
        ],
        **extra,
    )


async def _puede_loguear(repo, email: str, password: str) -> bool:
    from app.servicios.auth_servicio import CredencialesInvalidasError, iniciar_sesion

    try:
        await iniciar_sesion(repo, FakeStore(), email, password, 7)
    except CredencialesInvalidasError:
        return False
    return True


# --- 2.1 alta --------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_alta_valida_201_sin_hash_y_el_usuario_puede_loguearse():
    repo = _repo()
    _, cli, bearer, db = app_admin_con(repo)
    async with cli:
        r = await cli.post("/admin/usuarios", json=ALTA, headers=bearer(1, "admin"))
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["rol"] == "secretaria" and cuerpo["activo"] is True and cuerpo["email"] == ALTA["email"]
    assert set(cuerpo) == {"id", "nombre", "email", "rol", "activo"}
    assert ALTA["password"] not in r.text and "argon2" not in r.text
    assert db.commits == 1
    assert await _puede_loguear(repo, ALTA["email"], ALTA["password"])


@pytest.mark.asyncio
async def test_alta_guarda_hash_argon2_y_nunca_la_contrasena_en_claro():
    repo = _repo()
    _, cli, bearer, _ = app_admin_con(repo)
    async with cli:
        r = await cli.post("/admin/usuarios", json=ALTA, headers=bearer(1, "admin"))
    guardado = repo._usuarios[r.json()["id"]]
    assert guardado.password_hash.startswith("$argon2")
    assert guardado.password_hash != ALTA["password"]


@pytest.mark.asyncio
@pytest.mark.parametrize("email", ["SECRE@demo.test", "Secre@Demo.Test"])
async def test_alta_con_email_repetido_con_otras_mayusculas_409_y_no_crea(email):
    repo = _repo()
    _, cli, bearer, db = app_admin_con(repo)
    async with cli:
        r = await cli.post("/admin/usuarios", json={**ALTA, "email": email}, headers=bearer(1, "admin"))
    assert r.status_code == 409
    assert len(repo._usuarios) == 2
    assert db.commits == 0


@pytest.mark.asyncio
async def test_alta_con_carrera_de_email_el_indice_unico_responde_409_con_rollback():
    """El email no existia al consultar pero el indice unico lo rechaza al insertar."""
    repo = _repo()
    original = repo.obtener_por_email
    llamadas: list[str] = []

    async def ciega_la_primera(email):
        llamadas.append(email)
        return None if len(llamadas) == 1 else await original(email)

    repo.obtener_por_email = ciega_la_primera
    _, cli, bearer, db = app_admin_con(repo)
    async with cli:
        r = await cli.post("/admin/usuarios", json={**ALTA, "email": "secre@demo.test"},
                           headers=bearer(1, "admin"))
    assert r.status_code == 409
    assert db.rollbacks == 1 and db.commits == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cuerpo",
    [
        {**ALTA, "rol": "duenio"},
        {**ALTA, "extra": "no declarado"},
        {**ALTA, "password": "1234567"},
        {**ALTA, "email": "sin-arroba"},
        {**ALTA, "nombre": "  "},
        {k: v for k, v in ALTA.items() if k != "rol"},
    ],
)
async def test_alta_invalida_422_y_no_crea(cuerpo):
    repo = _repo()
    _, cli, bearer, _ = app_admin_con(repo)
    async with cli:
        r = await cli.post("/admin/usuarios", json=cuerpo, headers=bearer(1, "admin"))
    assert r.status_code == 422
    assert len(repo._usuarios) == 2


@pytest.mark.asyncio
async def test_alta_con_contrasena_de_8_caracteres_es_valida():
    _, cli, bearer, _ = app_admin_con(_repo())
    async with cli:
        r = await cli.post("/admin/usuarios", json={**ALTA, "password": "12345678"}, headers=bearer(1, "admin"))
    assert r.status_code == 201


@pytest.mark.asyncio
@pytest.mark.parametrize("rol", ["secretaria", "odontologo"])
async def test_alta_solo_admin_403_para_otros_roles_y_401_sin_token(rol):
    repo = _repo()
    _, cli, bearer, _ = app_admin_con(repo)
    async with cli:
        r = await cli.post("/admin/usuarios", json=ALTA, headers=bearer(2, rol))
        sin = await cli.post("/admin/usuarios", json=ALTA)
    assert r.status_code == 403 and sin.status_code == 401
    assert len(repo._usuarios) == 2


# --- 2.2 edicion -----------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_activo_true_reactiva_y_puede_loguearse():
    repo = FakeRepoAdmin([
        fabricar_usuario(id=1, rol="admin", email="admin@demo.test"),
        fabricar_usuario(id=2, rol="secretaria", email="secre@demo.test", activo=False),
    ])
    _, cli, bearer, db = app_admin_con(repo)
    assert not await _puede_loguear(repo, "secre@demo.test", "Secreta-123")
    async with cli:
        r = await cli.patch("/admin/usuarios/2", json={"activo": True}, headers=bearer(1, "admin"))
    assert r.status_code == 200 and r.json()["activo"] is True
    assert db.commits == 1
    assert await _puede_loguear(repo, "secre@demo.test", "Secreta-123")


@pytest.mark.asyncio
async def test_patch_cambia_rol_y_la_respuesta_y_el_estado_reflejan_el_rol_nuevo():
    repo = _repo()
    _, cli, bearer, _ = app_admin_con(repo)
    async with cli:
        r = await cli.patch("/admin/usuarios/2", json={"rol": "odontologo"}, headers=bearer(1, "admin"))
        lista = await cli.get("/admin/usuarios", headers=bearer(1, "admin"))
    assert r.status_code == 200 and r.json()["rol"] == "odontologo"
    assert [u["rol"] for u in lista.json() if u["id"] == 2] == ["odontologo"]
    assert repo._usuarios[2].rol.nombre == "odontologo"


@pytest.mark.asyncio
async def test_patch_rol_nuevo_autoriza_la_llamada_siguiente_con_ese_rol():
    """Despues de promover a admin, el usuario pasa el guard de admin (rol leido de la DB)."""
    repo = _repo()
    _, cli, bearer, _ = app_admin_con(repo)
    async with cli:
        antes = await cli.get("/admin/usuarios", headers=bearer(2, "admin"))
        await cli.patch("/admin/usuarios/2", json={"rol": "admin"}, headers=bearer(1, "admin"))
        despues = await cli.get("/admin/usuarios", headers=bearer(2, "admin"))
    assert antes.status_code == 403 and despues.status_code == 200


@pytest.mark.asyncio
async def test_patch_password_la_vieja_falla_y_la_nueva_entra():
    repo = _repo()
    _, cli, bearer, _ = app_admin_con(repo)
    async with cli:
        r = await cli.patch("/admin/usuarios/2", json={"password": "Nueva-98765"}, headers=bearer(1, "admin"))
    assert r.status_code == 200 and "Nueva-98765" not in r.text
    assert not await _puede_loguear(repo, "secre@demo.test", "Vieja-1234")
    assert await _puede_loguear(repo, "secre@demo.test", "Nueva-98765")


@pytest.mark.asyncio
async def test_patch_nombre_cambia_solo_el_nombre_y_un_cuerpo_vacio_no_cambia_nada():
    repo = _repo()
    _, cli, bearer, _ = app_admin_con(repo)
    async with cli:
        r = await cli.patch("/admin/usuarios/2", json={"nombre": "Otra Persona"}, headers=bearer(1, "admin"))
        vacio = await cli.patch("/admin/usuarios/2", json={}, headers=bearer(1, "admin"))
    assert r.json()["nombre"] == "Otra Persona" and r.json()["rol"] == "secretaria"
    assert vacio.status_code == 200 and vacio.json()["nombre"] == "Otra Persona"


@pytest.mark.asyncio
async def test_patch_activo_false_422_y_remite_a_desactivar():
    repo = _repo()
    _, cli, bearer, _ = app_admin_con(repo)
    async with cli:
        r = await cli.patch("/admin/usuarios/2", json={"activo": False}, headers=bearer(1, "admin"))
    assert r.status_code == 422 and "desactivar" in r.text
    assert repo._usuarios[2].activo is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cuerpo", [{"rol": "duenio"}, {"password": "corta"}, {"email": "x@y.com"}, {"nombre": ""}]
)
async def test_patch_invalido_422(cuerpo):
    _, cli, bearer, _ = app_admin_con(_repo())
    async with cli:
        r = await cli.patch("/admin/usuarios/2", json=cuerpo, headers=bearer(1, "admin"))
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_inexistente_404_y_no_admin_403():
    _, cli, bearer, _ = app_admin_con(_repo())
    async with cli:
        r404 = await cli.patch("/admin/usuarios/999", json={"nombre": "X"}, headers=bearer(1, "admin"))
        r403 = await cli.patch("/admin/usuarios/2", json={"nombre": "X"}, headers=bearer(2, "secretaria"))
    assert r404.status_code == 404 and r403.status_code == 403
