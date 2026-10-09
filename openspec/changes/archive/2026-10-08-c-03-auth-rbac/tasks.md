# Tasks — c-03-auth-rbac

> Convención TDD estricta (Iron Law): cada task de implementación empieza con un
> test en fallo (RED) que falle por la razón esperada, luego GREEN mínimo, luego
> REFACTOR. Orden por dependencias. Chunks ≤ 2 h. Auth contra Postgres REAL + Redis
> REAL del compose (NUNCA SQLite). Nombres `test_<unidad>_<escenario>_<resultado>`
> (AAA). `freezegun` para expiración (JWT 30 min) y rotación. Governance CRITICO:
> no escribir código productivo sin su test en rojo primero.

## 1. Dependencias + seguridad core (hash y JWT)

- [x] 1.1 Agregar `pyjwt`, `pwdlib[argon2]` y `freezegun` a `backend/requirements.txt` con test RED de import (`from pwdlib import PasswordHash; import jwt`) que pase en GREEN al instalar, verificado con `pip install -r backend/requirements.txt`
- [x] 1.2 Implementar hash en `core/security.py` (reemplaza el stub): `hashear_password` (Argon2id) + `verificar_password` (acepta `$argon2*` y `$2b$/$2y$` heredados, rechaza incorrecta) con tests RED `test_hashear_nuevo_usa_argon2` y `test_verificar_acepta_bcrypt_heredado_y_rechaza_mala` que pasen en GREEN al implementar
- [x] 1.3 Implementar JWT en `core/security.py`: `crear_access_token(usuario_id, rol)` (claims `sub/rol/iat/exp=+JWT_EXPIRE_MIN`, UTC) + `verificar_access_token` (firma `JWT_SECRET`, `exp` con leeway 30 s, expirado → error tipado) con tests RED `test_access_expirado_rechazado_con_freezegun` (avanzar reloj >30 min → error) y `test_access_firma_invalida_rechazado` que pasen en GREEN al implementar

## 2. Endpoints de sesión (`/auth`)

- [x] 2.1 Crear `esquemas/auth.py` (`LoginIn`, `TokenOut`, `MeOut`, `extra='forbid'`, sin hash en ningún response) con test RED `test_login_in_rechaza_campo_extra` (campo extra → 422) que pase en GREEN al crear los esquemas
- [x] 2.2 Implementar `POST /auth/login` (lookup `obtener_por_email` case-insensitive, 401 genérico idéntico en los 3 casos con hash dummy si no hay hash, emite access + cookie httpOnly `refresh_token` vía Redis con TTL `REFRESH_EXPIRE_DAYS=7`) con tests RED `test_login_ok_emite_access_y_cookie`, `test_login_email_inexistente_y_password_mala_mismo_401` (mismo status y cuerpo) y `test_login_inactivo_401_generico` contra PG+Redis reales que pasen en GREEN al implementar
- [x] 2.3 Implementar `POST /auth/refresh` (rotación atómica GETDEL+SET, reuso → 401 + invalida la familia de sesión) + `POST /auth/logout` (DEL + limpia cookie) + `GET /auth/me` (`{id,email,nombre,rol}`, Bearer válido) con tests RED `test_refresh_rota_e_invalida_anterior`, `test_reuso_refresh_rotado_401` y `test_logout_invalida_refresh` contra Redis real que pasen en GREEN al implementar

## 3. RBAC (`require_role`) + superficie admin mínima

- [x] 3.1 Implementar `get_current_user` + factoría `require_role(*roles)` en `core/deps.py` (Bearer con `HTTPBearer(auto_error=False)`, 401 sin/inválido/expirado/inactivo, 403 rol no incluido) con tests RED `test_ruta_admin_con_secretaria_403`, `test_bearer_expirado_401_con_freezegun` y `test_usuario_desactivado_401` (xia app de prueba con endpoint protegido) que pasen en GREEN al implementar
- [x] 3.2 Exponer superficie admin mínima (`GET /admin/usuarios`, `PATCH /admin/usuarios/:id/desactivar`, `DELETE /admin/usuarios/:id`, solo `admin` vía `require_role("admin")`, reutilizando `usuarios_servicio` con `UltimoAdminError` → 409) con tests RED `test_desactivar_unico_admin_via_http_409`, `test_eliminar_unico_admin_via_http_409` y `test_con_dos_admins_desactivar_ok` contra PG real que pasen en GREEN al implementar
- [x] 3.3 Re-hashear seed admin a Argon2 (seed usa `hashear_password` para `SEED_ADMIN_PASSWORD`, idempotente: no re-hashea si ya es Argon2) con test RED `test_seed_admin_usa_argon2` (doble seed → mismo hash, verifica con `verificar_password`) que pase en GREEN al implementar

## 4. Frontend (sesión + guards)

- [x] 4.1 Implementar `auth-context` real (`sesion {email, rol} | null`, access solo en memoria, `iniciarSesion/cerrarSesion`, refresh silencioso con un solo reintento ante 401 y caída a login) + helpers `login/me/logout/fetchConAuth` en `api-client.ts` (tipados, cero `any`, `credentials: "include"`), verificado con test RED de `fetchConAuth` (mock fetch: 401 → refresh → reintento ok; refresh fallido → sesión nula) que pase en GREEN al implementar
- [x] 4.2 Crear `pages/Login.tsx` (form email/password, 401 genérico → "credenciales inválidas", sin enumerar) + `shared/RequireRole.tsx` (sin sesión → login; rol no incluido → "sin permiso") + cablear en `App.tsx`, verificado con test RED de render (Vitest/Testing Library o Playwright según convención del repo: login muestra error genérico; ruta admin con secretaria muestra "sin permiso") que pase en GREEN al implementar

## 5. Verificación integral GATE 2

- [x] 5.1 Agregar `REFRESH_EXPIRE_DAYS=7` a `.env.example` (sin secretos reales) con test RED `test_env_example_trae_refresh_expire` (ya existe patrón `test_env_example.py`) que pase en GREEN al agregarlo
- [x] 5.2 Ejecutar suite completa (`docker compose up -d db redis && alembic upgrade head && pytest backend/app/tests` + checks frontend) contra Postgres/Redis reales y verificar que toda la suite (C-01 + C-02 + C-03) está verde sin ningún test en SQLite — GATE 2
- [x] 5.3 Correr `openspec validate --change c-03-auth-rbac --strict` y verificar que proposal/design/specs/tasks pasan sin errores (corregir lo que el validador reporte)
