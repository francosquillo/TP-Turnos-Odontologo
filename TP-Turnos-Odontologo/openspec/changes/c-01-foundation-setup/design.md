# Design — c-01-foundation-setup

## Context

Ver `proposal.md` (Why). Estado actual: repo con `knowledge-base/`, `CHANGES.md`,
`openspec/config.yaml`, sin código (`openspec list --specs` → `[]`).
Restricciones vinculantes 2026-10-05: deploy local Docker Compose, datos 100%
ficticios, sede única, rol FK simple, pagos simulados, AFIP post-TP, plazo 12/10/2026,
equipo 3. Ver `knowledge-base/08_arquitectura_propuesta.md` (monolito modular +
worker Redis) y `09_decisiones_y_supuestos.md` (DD-01..DD-04).

## Goals / Non-Goals

**Goals:**

- `docker compose up` levanta api + worker + postgres:16 + redis:7 en local y
  `GET /health` responde 200 con checks de postgres/redis.
- Skeletons importables y testeables: backend por capas y frontend Vite+TS estricto.
- Toda configuración sensible por env; `.env.example` completo y `.env` ignorado.
- `btree_gist` disponible desde el primer arranque (sin ella C-04 no puede crear el EXCLUDE).
- Tasks listas para TDD estricto en apply (test en fallo primero, verificación por task).

**Non-Goals:**

- Modelos, migraciones, seed (C-02).
- Auth/RBAC/JWT (C-03).
- Lógica de agenda, EXCLUDE en tabla turno, worker real (C-04/C-06).
- UI de features (agenda, reserva, odontograma, caja) — solo shell SPA.
- CI/cloud, TLS productivo, MercadoPago/AFIP (post-TP explícito).

## Decisions

### D-01 — Compose con 4 servicios, imágenes pineadas, red única, healthchecks

`api` (build `backend/Dockerfile`, Python 3.12-slim) + `worker` (misma imagen,
`command: python -m app.worker.main`) + `db` (`postgres:16-alpine`, volumen
persistente, `db/init/01-btree-gist.sql`) + `redis` (`redis:7-alpine`).
`api` depende de `db`/`redis` con `condition: service_healthy`.
Alternativa (servicios externos/cloud) descartada: decisión local 2026-10-05 +
plazo 7 días. Skill: `fastapi-templates` (estructura + DI + async), `redis-patterns`
(pool con timeouts 2s, TTL en toda key futura).

### D-02 — Backend `backend/app/{api,servicios,repos,modelos,esquemas,worker,tests}` + `core/` + `main.py`

Mapeo del template `fastapi-templates` (`api/v1/endpoints,core,models,schemas,
services,repositories`) a la KB 08 en español. `core/` alberga `config.py`
(pydantic-settings), `security.py` (stub, JWT real en C-03), `deps.py`
(`Annotated[..., Depends(...)]` para sesión DB). Routers vacíos por recurso
(`auth, pacientes, turnos, ...`) con `prefix/tags/dependencies` en el `APIRouter`.
`def` por defecto; `async def` solo si todo adentro es async no bloqueante.
Pydantic `extra='forbid'` desde el día 1. Alternativa (estructura inglesa del
template) descartada: la KB 08 en español es contrato del TP.

### D-03 — Config solo env + `.env.example` versionado, `.env` ignorado

Variables (KB 08): `DATABASE_URL, REDIS_URL, JWT_SECRET, JWT_EXPIRE_MIN=30,
WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_WEBHOOK_SECRET, WHATSAPP_MOCK=true,
GCAL_CLIENT_ID, GCAL_SECRET, CORS_ORIGINS=http://localhost:5173,
SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD, TZ=America/Argentina/Buenos_Aires`.
`config.py` falla en arranque si falta `JWT_SECRET`/`DATABASE_URL` (fail-fast).
`WHATSAPP_MOCK=true` por defecto para que C-06 funcione en demo sin creds Meta.
Alternativa (defaults hardcodeados) descartada: regla dura NUNCA secreto en código.

### D-04 — `btree_gist` vía init SQL versionado, no manual

`backend/db/init/01-btree-gist.sql` → `CREATE EXTENSION IF NOT EXISTS btree_gist;`,
montado en `/docker-entrypoint-initdb.d`. Verificado por test de integración
contra Postgres real (`SELECT * FROM pg_extension WHERE extname='btree_gist'`).
No SQLite en ningún test de este change (regla dura: SQLite no soporta EXCLUDE/GiST).
Skill: `supabase-postgres-best-practices` (cargar antes de tocar DB),
`postgresql-table-design` (base del EXCLUDE de C-04).
Alternativa (`CREATE EXTENSION` en migración Alembic posterior) descartada: C-04
necesita la extensión antes de su migración 002.

### D-05 — Frontend Vite + React 18 + TS 5 estricto, shell mínimo

`frontend/src/{features,shared,pages}` (KB 08): `shared/api-client.ts`
(fetch tipado + base URL por env), `shared/auth-context.tsx` (stub con tipos,
lógica real en C-03), `pages/` vacías (`Reservas, Confirmar, Seguridad` como
placeholders). `tsconfig` con `strict: true, noImplicitAny: true`.
Sin barrel files; `lazy()` reservado para futuros pesados (agenda, odontograma).
Skill: `vercel-react-best-practices` (adaptación Vite: bundle/waterfall/rerender,
ignorar RSC), `frontend-design` (dos pasadas; en C-01 solo tokens mínimos, sin
héroe todavía). Alternativa (CRA/Next.js) descartada: stack facultad fija Vite SPA.

### D-06 — Tests base con Postgres/Redis reales vía compose, pytest + Vitest smoke

Backend: `pytest` con capas `tests/{conftest,test_unit,test_integration,test_e2e}`
(`python-testing-patterns`: AAA, `test_<unidad>_<escenario>_<resultado>`).
`test_health_*` con `httpx.AsyncClient + dependency_overrides`;
`test_btree_gist_*` contra Postgres real del compose. Frontend: `tsc --noEmit`
+ render smoke de `App`. Verificación global: `docker compose up -d && pytest &&
tsc --noEmit`. Skill: `test-driven-development` (Iron Law RED→GREEN→REFACTOR —
cada task de apply empieza por test en fallo).

## Risks / Trade-offs

- [Risk] Puertos 5432/6379/8000/5173 ocupados en máquinas de alumnos → Mitigación:
  puertos parametrizables por env en compose + documentado en `.env.example`.
- [Risk] Imagen `postgres:16-alpine` sin `btree_gist` contrib → Mitigación: la imagen
  oficial sí la incluye; el test `test_btree_gist_*` lo verifica en CI local y falla
  con mensaje accionable si falta.
- [Risk] `worker` como stub puede confundirse con worker real → Mitigación: `worker/main.py`
  loguea `worker stub C-01` + loop heartbeat; jobs reales llegan en C-06.
- [Trade-off] Sin Alembic en C-01 (llega en C-02) → se acepta: no hay tablas propias
  aún; el init SQL solo crea la extensión.
- [Trade-off] Frontend shell sin diseño final → se acepta: `frontend-design` a fondo
  aplica en C-04/C-05 (agenda/reserva); C-01 solo tokens y layout raíz.

## Migration Plan

Sin migración (repo sin código previo). Rollback: `docker compose down -v` +
borrar `backend/`, `frontend/`, `docker-compose.yml`. Deploy: solo local
(`docker compose up --build`); sin cloud ni pipeline en v1.0.

## Open Questions

Ninguna que cambie specs, enfoque o tasks. Diferidas a sus changes:
C-02 (Alembic vs SQL puro), C-03 (Argon2 vs bcrypt), C-06 (imagen worker separada si crece).
