# Spec Delta — c-03-auth-rbac

## Purpose

Autenticar al staff con JWT de vida corta más refresh rotativo y autorizar cada
endpoint por rol (matriz 03), con resguardo del último admin y sesión frontend con
guards, para que agenda, clínica y cobros operen sobre identidad verificada.

## ADDED Requirements

### Requirement: Login con 401 genérico sin enumerar usuarios

El sistema SHALL exponer `POST /auth/login` que recibe `email` + `password`
(esquema estricto `extra='forbid'`) y, si las credenciales son válidas y el usuario
está activo, responde `200` con el access JWT y emite el refresh opaco en cookie
httpOnly; en cualquier otro caso (email inexistente, password incorrecta o usuario
inactivo) SHALL responder `401` con el mismo cuerpo genérico, sin distinguir la causa
(RN-AU-01, Flujo 7).

#### Scenario: Login válido emite access y cookie de refresh

- **WHEN** se envía `POST /auth/login` con email y password correctos de un usuario activo
- **THEN** responde `200`, el cuerpo trae el access JWT con `exp` a `JWT_EXPIRE_MIN=30` minutos y la respuesta incluye la cookie httpOnly `refresh_token`

#### Scenario: Email inexistente y password incorrecta devuelven el mismo 401

- **WHEN** se envía `POST /auth/login` con un email no registrado y luego con un email válido pero password incorrecta
- **THEN** ambas respuestas son `401` con idéntico cuerpo `{"detail": "credenciales inválidas"}` y no se emite ninguna cookie

#### Scenario: Usuario inactivo no puede iniciar sesión

- **WHEN** se envía `POST /auth/login` con credenciales correctas de un usuario con `activo=false`
- **THEN** responde `401` con el mismo cuerpo genérico que las credenciales inválidas

### Requirement: Refresh rotativo con invalidación del anterior

El sistema SHALL exponer `POST /auth/refresh` que lee el refresh opaco desde la
cookie httpOnly, y si es válido SHALL emitir un par nuevo (access + refresh) e
invalidar el anterior; el reuso de un refresh ya rotado SHALL responder `401`
(RN-AU-01, Flujo 7).

#### Scenario: Refresh válido rota el par

- **WHEN** se envía `POST /auth/refresh` con la cookie del refresh vigente
- **THEN** responde `200` con un access nuevo y una cookie de refresh distinta, y el refresh anterior queda invalidado

#### Scenario: Reuso de un refresh rotado es rechazado

- **WHEN** se envía `POST /auth/refresh` dos veces con el mismo refresh (el segundo con el valor ya rotado)
- **THEN** la primera responde `200` y la segunda responde `401` sin emitir tokens

### Requirement: Sesión actual y logout con invalidación

El sistema SHALL exponer `GET /auth/me` que con un Bearer válido responde `200` con
`{id, email, nombre, rol}` (nunca el hash) y SHALL exponer `POST /auth/logout` que
invalida el refresh en Redis y limpia la cookie; tras el logout el refresh SHALL
dejar de ser aceptado (Flujo 7).

#### Scenario: Me retorna la identidad del Bearer

- **WHEN** se envía `GET /auth/me` con un access válido de una secretaria
- **THEN** responde `200` con su id, email, nombre y `rol="secretaria"`, sin campo de hash

#### Scenario: Logout invalida el refresh

- **WHEN** se hace `POST /auth/logout` con la cookie vigente y luego `POST /auth/refresh` con ese mismo refresh
- **THEN** el logout responde `200` y limpia la cookie, y el refresh posterior responde `401`

### Requirement: Access JWT corto y hash Argon2

El sistema SHALL firmar el access JWT (HS256, `JWT_SECRET` solo por env) con claims
`sub`, `rol`, `iat`, `exp` a `JWT_EXPIRE_MIN=30` minutos en UTC (tolerancia `30s`),
y SHALL hashear passwords nuevas con Argon2id aceptando en verificación hashes
bcrypt heredados; un access expirado SHALL ser rechazado con `401` (RN-AU-01).

#### Scenario: Token expirado es rechazado con 401

- **WHEN** se usa un access válido pero con el reloj avanzado más de `JWT_EXPIRE_MIN` minutos (freezegun) en `GET /auth/me`
- **THEN** responde `401` y el frontend puede recuperarse vía `POST /auth/refresh`

#### Scenario: Password verifica con Argon2 y con bcrypt heredado

- **WHEN** se verifica una password contra un hash `$argon2id$` vigente y contra un hash `$2b$` heredado
- **THEN** ambas verificaciones aceptan la password correcta y rechazan una incorrecta, y todo hash nuevo usa Argon2id

### Requirement: Autorización por rol con require_role y matriz 03

El sistema SHALL proteger los endpoints con la dependencia `require_role(...)`:
sin Bearer o con token inválido/expirado o usuario inactivo SHALL responder `401`;
con rol no incluido SHALL responder `403`. La matriz aplicable en este change es:
`GET /auth/me` cualquier rol autenticado; `GET /admin/usuarios`,
`PATCH /admin/usuarios/:id/desactivar` y `DELETE /admin/usuarios/:id` solo `admin`;
las rutas públicas (`POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`
sin exigir rol, `GET /`, `/reservas`, `/confirmar/:token`, `/disponibilidad`,
`/webhooks/whatsapp`, `/seguridad`) SHALL seguir accesibles sin Bearer
(matriz `03`, Dueño=alias de Admin sin rol separado).

#### Scenario: Rol no autorizado recibe 403

- **WHEN** una secretaria autenticada llama `GET /admin/usuarios` (solo admin)
- **THEN** responde `403` y el listado no se expone

#### Scenario: Endpoint admin con admin responde 200

- **WHEN** un admin autenticado llama `GET /admin/usuarios`
- **THEN** responde `200` con el listado de usuarios

#### Scenario: Ruta pública no exige Bearer

- **WHEN** se llama `POST /auth/login` sin header Authorization
- **THEN** no responde `401` por falta de token sino que procesa el login (200 o 401 genérico según credenciales)

### Requirement: Resguardo del último admin expuesto vía HTTP

El sistema SHALL bloquear con `409` la desactivación (`PATCH
/admin/usuarios/:id/desactivar`) o eliminación (`DELETE /admin/usuarios/:id`) del
único admin activo, reutilizando el guard de servicio de C-02; con otro admin activo
la operación SHALL tener éxito (RN-AU-03). Solo `admin` puede llamar estos endpoints.

#### Scenario: Desactivar al único admin activo vía HTTP es bloqueado

- **WHEN** existe un único admin activo y un admin llama `PATCH /admin/usuarios/:id/desactivar` sobre él
- **THEN** responde `409` y el usuario sigue con `activo=true`

#### Scenario: Eliminar al único admin activo vía HTTP es bloqueado

- **WHEN** existe un único admin activo y un admin llama `DELETE /admin/usuarios/:id` sobre él
- **THEN** responde `409` y el usuario sigue existiendo y activo

#### Scenario: Con dos admins desactivar uno funciona

- **WHEN** existen dos admins activos y se desactiva uno vía `PATCH /admin/usuarios/:id/desactivar`
- **THEN** responde `200` con `activo=false` y el otro admin sigue activo

### Requirement: Sesión frontend con guards por rol

El frontend SHALL proveer sesión real en `auth-context` (login/logout, access solo
en memoria nunca en `localStorage`, reintento silencioso con `/auth/refresh` ante un
`401` y caída a login si el refresh falla), página de login y guard `RequireRole`
que sin sesión redirige a login y con rol no incluido muestra "sin permiso"; el
backend SHALL seguir siendo la autoridad (el guard nunca sustituye el `403`).

#### Scenario: Navegación a ruta de rol distinto muestra sin permiso

- **WHEN** una secretaria autenticada visita una ruta envuelta en `RequireRole roles=["admin"]`
- **THEN** ve la pantalla "sin permiso" en lugar del contenido protegido

#### Scenario: Access expirado se recupera en silencio vía refresh

- **WHEN** el access en memoria expira y la app hace una llamada autenticada con refresh vigente
- **THEN** la app renueva el par sin mostrar el login y reintenta la llamada original una vez
