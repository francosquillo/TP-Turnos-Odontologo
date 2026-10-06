# foundation-setup Specification

## Purpose
Provee la base ejecutable local del sistema (compose, skeletons, configuración por
entorno y extensión btree_gist) para que todos los changes posteriores puedan
implementarse y verificarse sobre una plataforma común y reproducible.

## Requirements

### Requirement: Compose local con cuatro servicios

El sistema SHALL proveer un `docker-compose.yml` que levante `api`, `worker`,
`postgres:16` y `redis:7` en red local con healthchecks y volúmenes persistentes
para la base de datos.

#### Scenario: Levantar la plataforma

- **WHEN** un desarrollador ejecuta `docker compose up -d --build` en una máquina con Docker
- **THEN** los cuatro servicios quedan en estado healthy y `api` responde sin errores de conexión a postgres y redis

#### Scenario: Puertos ocupados parametrizables

- **WHEN** los puertos por defecto están ocupados y el desarrollador los redefine por env en el compose
- **THEN** la plataforma levanta igual sin editar archivos versionados

### Requirement: Backend skeleton por capas con healthcheck

El sistema SHALL exponer `GET /health` que retorna 200 con el estado de
postgres y redis, montado sobre la estructura
`backend/app/{api,servicios,repos,modelos,esquemas,worker,tests}` más `core/` y `main.py`.

#### Scenario: Healthcheck verde

- **WHEN** un cliente llama `GET /health` con la plataforma levantada
- **THEN** responde 200 con cuerpo `{status: "ok", postgres: "up", redis: "up"}`

#### Scenario: Servicio caído visible

- **WHEN** postgres o redis no está reachable y un cliente llama `GET /health`
- **THEN** responde 503 identificando el servicio caído sin exponer secretos ni tracebacks

### Requirement: Configuración solo por entorno

El sistema SHALL leer toda configuración desde variables de entorno
(`DATABASE_URL, REDIS_URL, JWT_SECRET, JWT_EXPIRE_MIN=30, WHATSAPP_*,
GCAL_*, CORS_ORIGINS, SEED_ADMIN_*, TZ=America/Argentina/Buenos_Aires`),
proveer `.env.example` completo y versionado, y NUNCA versionar `.env` ni
hardcodear secretos.

#### Scenario: Falta secreto crítico

- **WHEN** `JWT_SECRET` o `DATABASE_URL` no está definido al arrancar `api`
- **THEN** el arranque falla con mensaje que nombra la variable faltante y sin valor por defecto inseguro

#### Scenario: Ejemplo versionado sin secretos

- **WHEN** un revisor inspecciona `.env.example` en el repo
- **THEN** contiene todas las variables con valores placeholder y ningún secreto real

### Requirement: Extensión btree_gist habilitada

El sistema SHALL habilitar la extensión Postgres `btree_gist` vía script init
versionado (`CREATE EXTENSION IF NOT EXISTS btree_gist`) para que C-04 pueda
crear los constraints `EXCLUDE USING gist` anti-solapamiento.

#### Scenario: Extensión disponible al arrancar

- **WHEN** el servicio `db` arranca por primera vez con volumen limpio
- **THEN** `SELECT * FROM pg_extension WHERE extname = 'btree_gist'` retorna una fila

#### Scenario: Rearranque idempotente

- **WHEN** el servicio `db` rearranca con volumen ya inicializado
- **THEN** el init no falla y la extensión sigue disponible

### Requirement: Frontend shell Vite React TS estricto

El sistema SHALL proveer el scaffold `frontend/` con Vite + React 18 + TS 5 en
modo estricto (sin `any` implícito), estructura `src/{features,shared,pages}`,
`shared/api-client` tipado, `shared/auth-context` stub tipado y páginas
placeholder, compilable con `tsc --noEmit`.

#### Scenario: Compilación estricta

- **WHEN** un desarrollador ejecuta `tsc --noEmit` en `frontend/`
- **THEN** la compilación termina sin errores y ningún archivo usa `any` explícito o implícito

#### Scenario: Cliente API tipado

- **WHEN** una página usa `shared/api-client` contra `GET /health`
- **THEN** la respuesta se tipa y los errores de red se propagan como error tipado sin `any`

### Requirement: Tests base de infraestructura

El sistema SHALL proveer tests base que verifiquen healthcheck, import smoke del
backend, presencia de `btree_gist` contra Postgres real y compilación del
frontend, sin usar SQLite para nada relacionado con Postgres.

#### Scenario: Suite base verde

- **WHEN** un desarrollador ejecuta la suite base con la plataforma levantada
- **THEN** todos los tests de healthcheck, smoke y `btree_gist` pasan y ningún test usa SQLite
