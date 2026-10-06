# Proposal — c-01-foundation-setup (C-01 `foundation-setup`)

> Nota de nombre: el change canónico en `CHANGES.md` es `C-01-foundation-setup`.
> El CLI `openspec` exige kebab-case minúsculas, por eso el directorio es
> `openspec/changes/c-01-foundation-setup/`. Ambos nombres refieren al mismo change.

## Why

Sin base ejecutable (compose + skeletons + env + `btree_gist`) ningún change posterior
(C-02 → C-03 → C-04 …) puede implementarse ni testearse. Este change crea el GATE 0
del roadmap: deja `docker compose up` verde en local para que 3 agentes trabajen en
paralelo desde el día 1 (plazo duro 12/10/2026).

## What Changes

- `docker-compose.yml` con 4 servicios: `api + worker + postgres:16 + redis:7` (solo local, sin cloud — decisión 2026-10-05).
- `backend/Dockerfile + app/main.py`: FastAPI 0.110+, routers vacíos por recurso, middlewares CORS, healthcheck `GET /health`.
- `backend/app/core/`: config por env (`DATABASE_URL, REDIS_URL, JWT_SECRET, JWT_EXPIRE_MIN=30, WHATSAPP_*, GCAL_*, CORS_ORIGINS, SEED_ADMIN_*, TZ=America/Argentina/Buenos_Aires`) + `.env.example` versionado (`.env` nunca versionado).
- Estructura de capas `backend/app/{api,servicios,repos,modelos,esquemas,worker,tests}` según KB `08_arquitectura_propuesta.md` + `backend/app/core/` (transversal).
- `frontend/`: scaffold Vite + React 18 + TS 5 (estricto, sin `any`), `src/shared/api-client + auth-context`, `src/pages/` vacías, `Dockerfile`, proxy/dev contra `api`.
- Init SQL Postgres que habilita la extensión `btree_gist` (requisito DD-03; base del `EXCLUDE` anti-solapamiento de C-04).
- Tests base: healthcheck (`GET /health` → 200), import smoke del backend, `compose up` verificado + conectividad api→postgres/redis.

## Capabilities

### New Capabilities

- `foundation-setup`: base ejecutable local — compose de 4 servicios, skeletons backend/frontend, config por env, extensión `btree_gist`, healthcheck y tests base de infraestructura.

### Modified Capabilities

(none — primer change, no existen specs previas; `openspec list --specs` → `[]`)

## Impact

- Archivos nuevos: `docker-compose.yml`, `backend/Dockerfile`, `backend/app/**`, `backend/db/init/*.sql`, `.env.example`, `frontend/**` (Vite scaffold + `Dockerfile`).
- Sin breaking changes (repo sin código previo).
- Desbloquea: C-02 (modelos + migración 001 + repos) — GATE 0 → GATE 1.
- Deuda explícita: sin modelos, sin auth, sin migraciones Alembic (llegan en C-02); worker en stub (jobs reales en C-06/C-07/C-11); frontend solo shell (features en C-04/C-05).

## Leer antes (fuente de verdad)

- `knowledge-base/08_arquitectura_propuesta.md` — capas, compose, env vars, seguridad.
- `knowledge-base/02_descripcion_general.md` — stack facultad, API REST por recurso.
- `knowledge-base/09_decisiones_y_supuestos.md` — §DD-01 (stack), §DD-02 (monolito modular), §DD-03 (EXCLUDE requiere `btree_gist`), §DD-04 (Redis async).
- `knowledge-base/04_modelo_de_datos.md` — §Turno (EXCLUDE), §Sillon (sede texto, sede única).
- `knowledge-base/10_preguntas_abiertas.md` — 11/11 RESUELTAS 2026-10-05 (sin bloqueos).
- `CHANGES.md` — fila C-01 (scope, governance BAJO, sin dependencias) + árbol/GATES.
- `openspec/config.yaml` — schema spec-driven, reglas proposal/tasks.
