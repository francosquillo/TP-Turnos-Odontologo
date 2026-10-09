# Design — c-03-auth-rbac

## Context

Ver `proposal.md` (Why). Estado actual: C-02 archivado 18/18 — modelos
`Rol/Usuario` (FK simple, 3 roles fijos con CHECK, email unique + índice
`LOWER(email)`), `UsuarioRepository.obtener_por_email()` (case-insensitive) y
`listar_admins_activos()`, servicio `usuarios_servicio` con `UltimoAdminError`
(unit + integración en PG ya probados), config solo-env con fail-fast
(`JWT_SECRET`, `JWT_EXPIRE_MIN=30`), `core/security.py` stub, router `auth` stub,
`auth-context.tsx` stub, `api-client.ts` solo con `fetchHealth`.
Restricciones vinculantes: NUNCA secreto en código (solo env), Pydantic
`extra='forbid'`, `Annotated[..., Depends(...)]` para auth/DB, `async def` solo si
todo adentro es async no bloqueante, TS estricto sin `any`, tests de auth contra
Postgres/Redis reales (nunca SQLite), `freezegun` para tiempos, Dueño=alias de Admin.

## Goals / Non-Goals

**Goals:**

- Par access/refresh con rotación e invalidación inmediata (logout y reuso).
- `require_role(...)` reutilizable por todos los changes futuros (C-04..C-12).
- 401 genérico sin enumeración y resguardo último-admin verificable por HTTP.
- Sesión frontend sin tokens en almacenamiento persistente + guards por rol.
- Tasks listas para TDD estricto en apply (RED primero, verificación por task).

**Non-Goals:**

- CRUD completo de usuarios y su UI (C-12; acá solo lectura + desactivar/eliminar
  mínimos para exponer el guard).
- Rate-limit / lockout por fuerza bruta (ver D-06: recomendado, diferido a C-12 o
  post-TP por plazo 12/10).
- Roles nuevos, multi-rol por usuario o permisos por recurso finos (v1.0: 3 roles
  fijos, FK simple — IN-01/IN-02).
- Portal paciente / cuentas paciente (RN-AU-02: paciente sin cuenta en v1.0).

## Decisions

### D-01 — Access JWT HS256 corto + refresh opaco en Redis (vs refresh JWT con denylist)

Access: `pyjwt` HS256, claims `sub=usuario_id`, `rol`, `iat`, `exp=+JWT_EXPIRE_MIN`.
Refresh: opaco `secrets.token_urlsafe(32)`; en Redis solo su hash SHA-256
(`auth:refresh:<sha256>` → `usuario_id`, TTL `REFRESH_EXPIRE_DAYS=7`); cookie
httpOnly `refresh_token` (`Secure` en prod, `SameSite=Lax`, `Path=/auth`).
Rotación atómica: `GETDEL` viejo + `SET` nuevo; reuso del viejo → 401 + (defensa)
invalida la familia si se detecta reuso (ver D-05). Logout: `DEL` + limpia cookie.
Alternativa (refresh JWT con `jti` + denylist) descartada: la denylist crece sin
cota y el logout exige publicarla; el opaco+Redis da revocación inmediata con una
sola key por sesión y TTL como limpieza automática. Requiere Redis disponible en
login/refresh/logout (degradado explícito: 503 si Redis caído — ver Riesgos).
Skills: `fastapi` (dependencies `Annotated`), `python-testing-patterns` (freezegun).

### D-02 — Argon2id primario, bcrypt solo verificación heredada (vs solo bcrypt)

`pwdlib[argon2]` (Argon2id, backend moderno y mantenido) para hashear; verificación
acepta `$argon2*` y `$2b$/*$2y$*` (hashes bcrypt preexistentes del seed si los hubiera)
pero todo hash nuevo sale Argon2. El seed C-02 guardó placeholder configurable: el
apply re-hashea la password de `SEED_ADMIN_*` con Argon2 al primer seed post-C-03.
Alternativa (solo bcrypt vía `passlib`) descartada: `passlib` está en mantenimiento
mínimo y Argon2 es el ganador PHC recomendado; `pwdlib` es su sucesor activo.
Revisión humana: confirmar que el equipo acepta la dependencia nueva `pwdlib[argon2]`
(+ `pyjwt`, `freezegun` solo-tests) en `requirements.txt`.

### D-03 — `require_role(*roles)` como factoría sobre `get_current_user`

```python
CurrentUser = Annotated[Usuario, Depends(get_current_user)]  # 401 si falla
require_role("admin")  # → dependencia que 403 si rol no incluido
```

`get_current_user`: extrae Bearer (`HTTPBearer(auto_error=False)` para controlar el
401), verifica firma + `exp` con `JWT_SECRET`, carga `Usuario` + `rol.nombre` por
`UsuarioRepository`, exige `activo=true`. `require_role` cierra sobre los roles
permitidos y se declara por endpoint (`dependencies=[Depends(require_role("admin"))]`
o parámetro). `def` vs `async def`: las dependencias tocan DB async → `async def`
(DB async no bloqueante, cumple la regla). Matriz `03` completa se aplica endpoint
por endpoint a medida que landing (C-04..C-12); este change la aplica a
`/admin/*` + `GET /auth/me` (cualquier rol autenticado) y deja tabla de mapeo en el
spec. Alternativa (middleware global con mapa de rutas) descartada: el mapa global
se desincroniza con los routers; la dependencia por endpoint es explícita y testeable
por endpoint. Skill: `fastapi`.

### D-04 — 401 genérico con verificación a tiempo aproximadamente constante

Login siempre responde `401 {"detail": "credenciales inválidas"}` tanto si el email
no existe como si la password falla o el usuario está inactivo. Cuando no hay hash
contra el cual verificar (usuario inexistente/inactivo), se verifica la password
recibida contra un **hash dummy Argon2 constante** (solo para igualar tiempos, su
resultado se descarta). No se revela `email no registrado` vs `password incorrecta`
ni en cuerpo ni en timing grueso. `UsuarioResponse`/`MeOut` nunca incluyen hash.
Revisión humana: el dummy iguala el costo Argon2 pero no el tiempo de query DB;
si el equipo exige indistinguibilidad total, diferir a hardening post-TP.

### D-05 — Reuso de refresh = robo probable: invalida la familia

Si un refresh ya rotado (o inexistente) se presenta, se responde 401 **y** se elimina
la key del refresh vigente asociado a ese hash cuando sea trazable (rotación guarda
`auth:refresh:<nuevo>` sin vínculo al viejo; para invalidar la familia se guarda
además `auth:sesion:<usuario_id>:<sesion_id>` — el refresh lleva `sesion_id` en su
valor Redis). Simplificación v1.0: valor Redis = `{"usuario_id":…, "sesion_id":…}`;
ante reuso se borran todas las keys de esa `sesion_id`. Compromiso consciente:
barrido por patrón `SCAN` acotado a la sesión (nunca `KEYS *`). Alarming: log con
`usuario_id + sesion_id` (sin tokens) para auditoría (RN-GL-02).

### D-06 — Sin rate-limit en v1.0 del change (diferido, explícito)

Con plazo 12/10 y equipo de 3, el throttling de login (p. ej. fixed-window en Redis
por IP+email) queda fuera del scope exigible; el costo Argon2 (~100-500 ms) ya
ralentiza la fuerza bruta online. Se deja como deuda explícita para C-12 (tiene
capa admin donde darle UI de auditoría) o post-TP. Revisión humana: si la facultad
exige evidencia anti-fuerza-bruta en la demo, priorizar un límite simple
(5 intentos / 15 min por IP) dentro de la task 2.4.

### D-07 — Frontend: access solo en memoria, refresh silencioso, guards declarativos

`auth-context` real: `sesion {email, rol} | null`, `iniciarSesion(email,password)`
→ `POST /auth/login` (access se guarda en variable en memoria + `me`), `cerrarSesion()`
→ `POST /auth/logout`. `fetchConAuth`: adjunta `Authorization: Bearer <access>`; ante
401 **una sola vez** intenta `POST /auth/refresh` (cookie via `credentials: "include"`)
y reintenta; si falla → `sesion=null` + redirige a login. `RequireRole roles=[...]`:
sin sesión → login; con sesión pero rol no incluido → pantalla "sin permiso" (sin
filtrar rutas por oscuridad: el backend sigue siendo la autoridad). NUNCA access o
refresh en `localStorage/sessionStorage` (XSS los leería; httpOnly + memoria es el
modelo). Skill: `vercel-react-best-practices` (aplicar bundle/waterfall/rerender;
ignorar RSC/`next/dynamic` — proyecto Vite SPA).

## Risks / Trade-offs

- [Redis caído bloquea login/refresh/logout] → Mitigación: 503 explícito con
  `{"detail": "servicio de sesión no disponible"}` + health ya lo señala; access
  vigentes siguen válidos hasta expirar (stateless). No se cae a refresh sin estado.
- [Argon2 sube latencia de login ~100-500 ms] → Mitigación: parámetros OWASP
  moderados (`time_cost=2, memory_cost=19 MiB`); aceptable para login humano, y a la
  vez frena fuerza bruta (ver D-06).
- [XSS robaría el access en memoria en runtime] → Mitigación: vida de 30 min +
  refresh httpOnly no legible por JS + `Content-Security-Policy` básica en el
  `index.html` de Vite (diferida a C-12 si no entra). Sin tokens en storage.
- [Relojes desincronizados rechazan tokens válidos] → Mitigación: `leeway=30s` en
  verificación de `exp`; TZ `America/Argentina/Buenos_Aires` solo para agenda,
  JWT siempre en UTC.
- [Superficie admin mínima puede confundirse con CRUD completo] → Mitigación:
  Non-Goals explícitos + tasks 3.x nombran exactamente los 3 endpoints; C-12 amplía.

## Migration Plan

1. Mergear solo artefactos openspec (este change: sin código).
2. Apply (TDD): dependencias → `security.py` real → esquemas → `auth_servicio` →
   router `/auth` → `require_role` + superficie admin mínima → frontend → suite verde.
3. Re-seed post-apply: el seed re-hashea `SEED_ADMIN_PASSWORD` con Argon2 (task 5.1).
4. Rollback: revertir commits del apply; no hay migración DB (sin cambios de esquema),
   solo expira Redis por TTL. `openspec validate --strict` antes de archivar.

## Open Questions

(none — las decisiones diferibles reales (rate-limit, CSP) quedaron como deuda
explícita en Non-Goals/D-06 con criterio de re-priorización, no como incógnitas.)
