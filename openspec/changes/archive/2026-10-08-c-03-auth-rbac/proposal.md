# Proposal — c-03-auth-rbac (C-03 `auth-rbac`)

> Nota de nombre: el change canónico en `CHANGES.md` es `C-03-auth-rbac`.
> El CLI `openspec` exige kebab-case minúsculas, por eso el directorio es
> `openspec/changes/c-03-auth-rbac/`. Ambos nombres refieren al mismo change.

## Why

C-02 dejó identidad persistida (roles, usuarios con `rol_id` FK simple, guard
`>=1 admin activo` a nivel servicio) pero sin forma de autenticarse: `core/security.py`
es un stub que levanta `NotImplementedError` y el router `auth` responde un placeholder.
Sin JWT + RBAC ningún endpoint de C-04 en adelante puede protegerse por rol, y la
matriz de permisos de `03` (admin/odontologo/secretaria + público) queda en papel.
Este change crea el GATE 2 del roadmap: login/refresh/logout + `require_role(...)`
reutilizable + resguardo último-admin expuesto vía HTTP + sesión frontend con guards.

## What Changes

- `POST /auth/login` (email + password; 401 genérico `credenciales inválidas` sin
  enumerar usuarios; verificación a tiempo aproximadamente constante con hash dummy
  cuando el usuario no existe o está inactivo).
- `POST /auth/refresh` (refresh opaco rotativo en cookie httpOnly; cada uso emite un
  par nuevo e invalida el anterior; reuso del anterior → 401).
- `GET /auth/me` (sesión actual desde el Bearer) y `POST /auth/logout` (invalida el
  refresh en Redis + limpia la cookie).
- Access JWT Bearer HS256 de vida corta (`JWT_EXPIRE_MIN=30`, claims `sub/rol/exp/iat`)
  firmado con `JWT_SECRET` (solo env, fail-fast ya existente en C-01); hash de password
  Argon2 (primario) con verificación compatible bcrypt para hashes heredados.
- Dependencia FastAPI `require_role(...)` (factoría sobre `get_current_user`): 401 ante
  token ausente/inválido/expirado o usuario inactivo; 403 ante rol insuficiente; matriz
  `03` aplicada a la superficie de este change y reutilizable por C-04..C-12.
- Resguardo último admin (RN-AU-03) expuesto vía HTTP: `GET /admin/usuarios` (solo
  admin) + `PATCH /admin/usuarios/:id/desactivar` + `DELETE /admin/usuarios/:id`, que
  reutilizan `servicios/usuarios_servicio.py` (C-02) y mapean `UltimoAdminError` → 409.
  El CRUD completo de usuarios y su UI llegan en C-12; acá solo la superficie mínima
  para que el guard sea testeable por HTTP.
- Refresh tokens opacos: `secrets.token_urlsafe` guardado como hash SHA-256 en Redis
  con TTL `REFRESH_EXPIRE_DAYS=7`; rotación atómica (GETDEL + SET) e invalidación en
  logout. Sin tabla nueva en Postgres.
- Frontend: `auth-context` real (sesión `{email, rol}`, access solo en memoria — nunca
  `localStorage` —, refresh silencioso ante 401), `LoginPage`, guard `RequireRole` por
  rol y helpers en `api-client` (`login/me/logout/fetchConAuth`).
- Tests TDD contra **Postgres real + Redis real** (nunca SQLite): login/refresh/logout,
  RBAC por endpoint, bloqueo último admin vía HTTP, token expirado → 401 (con
  `freezegun`), hash Argon2 verifica y bcrypt heredado sigue válido.

## Capabilities

### New Capabilities

- `auth-rbac`: autenticación JWT (login/refresh/me/logout), autorización `require_role`
  con matriz `03`, resguardo último-admin vía HTTP y sesión frontend con guards por rol.

### Modified Capabilities

(none — `core-models-identidad-pacientes` no cambia comportamiento: el guard
`>=1 admin` a nivel servicio se reutiliza tal cual y solo se expone vía HTTP desde la
nueva capacidad `auth-rbac`; `foundation-setup` tampoco cambia.)

## Impact

- Archivos nuevos: `backend/app/core/refresh.py` (o extensión de `security.py`),
  `backend/app/api/auth.py` (real, reemplaza el stub), `backend/app/servicios/auth_servicio.py`,
  `backend/app/esquemas/auth.py` (`LoginIn/TokenOut/MeOut`, `extra='forbid'`),
  `backend/app/api/admin_usuarios.py` (superficie mínima admin),
  `frontend/src/pages/Login.tsx`, `frontend/src/shared/RequireRole.tsx`,
  tests `test_c03_*` nuevos, dependencias `pyjwt + pwdlib[argon2] + freezegun` en
  `requirements.txt`, `REFRESH_EXPIRE_DAYS` en `.env.example`.
- Archivos reemplazados: `backend/app/core/security.py` (stub → JWT real),
  `frontend/src/shared/auth-context.tsx` (stub → sesión real), extensión de
  `api-client.ts` y `App.tsx` (ruta login + guards).
- Sin breaking changes (los routers C-01/C-02 eran stubs sin consumidores; el cambio de
  `security.py` de stub a real es el comportamiento esperado anunciado en C-01).
- Desbloquea: C-04 (endpoints protegidos por rol) — GATE 2 → GATE 3 (fork C-04/C-08/C-12);
  C-08/C-12 reutilizan `require_role`.
- Deuda explícita: sin CRUD completo de usuarios (C-12); sin rate-limit en login
  (recomendado post-TP o C-12 si hay tiempo — ver design D-06); refresh de 7 días fijo
  por env, sin "recordarme" (post-TP).
- Governance **CRITICO** (auth): esta propuesta es análisis/diseño solamente, sin
  implementar código todavía; las decisiones sensibles (D-01..D-06 en design) quedan
  marcadas para revisión humana antes del apply.

## Leer antes (fuente de verdad)

- `knowledge-base/03_actores_y_roles.md` — matriz RBAC, 3 roles fijos, Dueño=Admin (alias), rutas públicas.
- `knowledge-base/07_flujos_principales.md` — §Flujo 7 (auth y sesiones).
- `knowledge-base/05_reglas_de_negocio.md` — §RN-AU-01 (JWT + refresh + Argon2/bcrypt), §RN-AU-02 (paciente sin cuenta), §RN-AU-03 (>=1 admin).
- `knowledge-base/08_arquitectura_propuesta.md` — §Seguridad (JWT + refresh httpOnly, RBAC por dependencia, secrets por env).
- `openspec/specs/core-models-identidad-pacientes/spec.md` — capacidad existente (rol FK simple, email unique case-insensitive, guard último-admin a nivel servicio — se reutiliza, no se modifica).
- `.env.example` / `backend/app/core/config.py` — `JWT_SECRET` (fail-fast), `JWT_EXPIRE_MIN=30`.
- `CHANGES.md` — fila C-03 (scope, governance CRITICO, dependencia C-02) + árbol/GATES.
- `openspec/config.yaml` — schema spec-driven, reglas proposal/tasks.
