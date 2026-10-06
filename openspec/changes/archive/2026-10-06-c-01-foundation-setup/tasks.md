# Tasks — c-01-foundation-setup

> Convención TDD estricta (Iron Law): cada task de implementación empieza con un
> test en fallo (RED) que falle por la razón esperada, luego GREEN mínimo, luego
> REFACTOR. La verificación de cada task indica el test/comando que lo prueba.
> Orden por dependencias. Chunks ≤ 2 h. Nunca SQLite para nada Postgres.

## 1. Compose + DB init (infra base)

- [x] 1.1 Redactar `docker-compose.yml` (api + worker + db `postgres:16-alpine` + redis `redis:7-alpine`, red única, healthchecks, `service_healthy`) con test de parse `docker compose config` verde y verificación `docker compose config` sin errores
- [x] 1.2 Crear `backend/db/init/01-btree-gist.sql` (`CREATE EXTENSION IF NOT EXISTS btree_gist;`) con test RED `test_btree_gist_extension_present` contra Postgres real del compose que verifique `pg_extension` y pase en GREEN tras `compose up -d db`
- [x] 1.3 Parametrizar puertos por env en compose y verificar con `docker compose config` que redefine puertos sin editar archivos versionados

## 2. Backend skeleton FastAPI (capas + config + health)

- [x] 2.1 Crear estructura `backend/app/{api,servicios,repos,modelos,esquemas,worker,tests}` + `core/` + `main.py` con test RED de import smoke (`import app.main`) que falle sin la estructura y pase en GREEN al crearla
- [x] 2.2 Implementar `core/config.py` (pydantic-settings con todas las env de KB 08, `JWT_EXPIRE_MIN=30`, `TZ`, fail-fast sin `JWT_SECRET`/`DATABASE_URL`) con test RED `test_config_falla_sin_jwt_secret` que pase en GREEN al implementar fail-fast
- [x] 2.3 Implementar `GET /health` (200 `{status, postgres, redis}` / 503 si caído, sin secretos) con test RED `test_health_ok` + `test_health_503_servicio_caido` vía `httpx.AsyncClient` que pasen en GREEN al montar el router con `Annotated[..., Depends(...)]`
- [x] 2.4 Crear routers vacíos por recurso (`auth, pacientes, profesionales, sillones, turnos, clinica, cobros, os, notificaciones, admin`) con `prefix/tags` en el `APIRouter` y verificar que `GET /docs` lista los prefijos sin duplicados
- [x] 2.5 Crear `backend/Dockerfile` (Python 3.12-slim, async, no bloquea event loop) + `worker/main.py` stub con heartbeat y verificar con `docker compose build api worker` que ambas imágenes buildean

## 3. Env + seguridad base

- [x] 3.1 Redactar `.env.example` completo (todas las vars de D-03 con placeholders, `WHATSAPP_MOCK=true`, `CORS_ORIGINS=http://localhost:5173`) con test RED que aserte presencia de cada clave y ausencia de secretos reales, verde al completar el archivo
- [x] 3.2 Agregar `.env` a `.gitignore` y verificar con `git check-ignore -v .env` que está ignorado y con `git status --porcelain` que `.env.example` sí está trackeado
- [x] 3.3 Configurar CORS por env + `extra='forbid'` en esquemas base y verificar con test que origen no permitido es rechazado y payload con campo extra retorna 422

## 4. Frontend shell (Vite + TS estricto)

- [x] 4.1 Scaffold Vite + React 18 + TS 5 con `strict/noImplicitAny`, estructura `src/{features,shared,pages}` y `Dockerfile`, verificado con `tsc --noEmit` sin errores
- [x] 4.2 Implementar `shared/api-client.ts` tipado (sin `any`) contra `GET /health` con test RED de tipado/error de red que pase en GREEN al implementarlo
- [x] 4.3 Implementar `shared/auth-context.tsx` stub tipado + `pages/` placeholder (Reservas, Confirmar, Seguridad) con test de render smoke de `App` verde y `grep -rn ": any"` vacío en `src/`

## 5. Verificación integral GATE 0

- [x] 5.1 Ejecutar E2E local `docker compose up -d --build && pytest backend/app/tests && tsc --noEmit` y verificar que healthcheck, suite base y compilación están verdes con postgres/redis reales — **Verificado E2E Docker 2026-10-06 por el usuario: suite verde** (`docker compose up -d --build` + suite completa TODO EN VERDE, incluye los 2 tests de config + btree_gist contra PG real).
  - **PENDIENTE E2E Docker (2026-10-06): verificar con `docker compose up -d --build` + pytest suite completa. 2 tests skipeados cubren esto.** Decisión vinculante del usuario: se archiva HOY con G5.1 pendiente; la verificación E2E se hace mañana en máquina con Docker y se registra sobre el change archivado (si da rojo, se reabre o se crea mini-change de fix). Estado local sin Docker: `pytest` 30 passed + 2 skipped, `tsc --noEmit` + `vitest run` verdes.
  - **FIX fail-fast 2026-10-06 (change reabierto):** la E2E del usuario dio 2 en RED (`test_config_falla_sin_jwt_secret`, `test_config_falla_sin_database_url`, contenedores OK). Causa raíz: `SettingsConfigDict(env_file=".env")` en `backend/app/core/config.py` enmascaraba el fail-fast (el `.env` del repo aportaba valores aunque el environ no los tuviera). Fix: solo environ (D-03 "config solo env"; Compose ya inyecta `.env` vía `env_file:`/`environment:`) + `extra="forbid"`. Verificado sin Docker: `pytest backend/app/tests` → 30 passed + 2 skipped (skips pre-existentes: postgres-real y git-check-ignore, requieren Docker/git ausentes acá), `tsc --noEmit` EXIT 0. Queda pendiente: UNA corrida `docker compose up -d --build && pytest backend/app/tests` en máquina con Docker tras este fix, y luego archivar 16/16.
- [x] 5.2 Correr `openspec validate --change c-01-foundation-setup --strict` y verificar que proposal/design/specs/tasks pasan sin errores (corregir lo que el validador reporte)
