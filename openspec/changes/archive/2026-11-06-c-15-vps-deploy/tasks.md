# Tasks — C-15 `vps-deploy` (Easypanel, un único servicio Compose)

> Strict TDD: cada task escribe el test RED primero (lectura de archivos con `yaml.safe_load` /
> texto, patrón de `backend/app/tests/test_compose_config.py`), luego GREEN mínimo, triangular y
> refactor. Los tests de este change NO necesitan Docker ni Postgres (no tocan constraints
> EXCLUDE). Correr desde `backend/`: `pytest app/tests/test_c15_*.py`.
> Decisiones aprobadas por el usuario (2026-11-06): Easypanel Compose único, D-01, D-02, D-04,
> D-05, D-06. D-03 (nginx-unprivileged) y D-07 a revisión liviana. DA-01..DA-04 fuera de scope.
> Safety net antes de tocar archivos existentes: `pytest app/tests/test_compose_config.py
> app/tests/test_worker_docker.py app/tests/test_gitignore.py app/tests/test_env_example.py
> app/tests/test_frontend_shell.py` → baseline verde.

## 1. Imagen backend endurecida

- [x] 1.1 RED→GREEN `test_c15_dockerfiles.py::backend`: `backend/Dockerfile` declara `USER` no-root (≠ root/0) antes de `CMD`, copia `alembic` y `alembic.ini`, define `PYTHONUNBUFFERED=1`, no declara `HEALTHCHECK`; endurecer el Dockerfile (usuario `app` uid 10001, `COPY --chown`) sin cambiar el `CMD`. Verificar: test nuevo verde + `test_worker_docker.py` verde.
- [x] 1.2 RED→GREEN `test_c15_dockerfiles.py::backend_dockerignore`: `backend/.dockerignore` excluye `.env`, `__pycache__`, `*.pyc`, `.pytest_cache`; crear el archivo. Verificar: test verde.

## 2. Imagen frontend de producción (estático, sin TLS)

- [x] 2.1 RED→GREEN `test_c15_nginx_conf.py`: `frontend/deploy/nginx.conf` con `listen 8080`, `try_files $uri $uri/ /index.html`, `server_tokens off`, `gzip on`, `X-Content-Type-Options`; triangular: sin `listen 443`/`ssl`, sin dominios literales. Verificar: test verde.
- [x] 2.2 RED→GREEN `test_c15_dockerfiles.py::frontend_prod`: `frontend/Dockerfile.prod` multi-stage (≥2 `FROM`), `npm ci`, `npm run build`, `ARG VITE_API_URL`, etapa final `nginxinc/nginx-unprivileged:*-alpine`, copia `dist` a `/usr/share/nginx/html` y `deploy/nginx.conf`, `EXPOSE 8080`, y no contiene `npm run dev` ni `vite` en `CMD`/`ENTRYPOINT`; triangular: `frontend/Dockerfile` (dev) sigue existiendo. Verificar: test verde + `test_frontend_shell.py` verde.
- [x] 2.3 RED→GREEN `test_c15_dockerfiles.py::frontend_dockerignore`: `frontend/.dockerignore` excluye `node_modules`, `dist`, `.env`, `.vite`; crear el archivo. Verificar: test verde.

## 3. Compose de producción para Easypanel

- [x] 3.1 RED→GREEN `test_c15_compose_prod.py` (estructura): `compose.prod.yml` existe, sin `name:` top-level, servicios `frontend, api, worker, migrate, db, redis`, `db` `postgres:16*`, `redis` `redis:7*`, volúmenes nombrados `pgdata, redisdata`; sin servicio ni imagen `caddy` y sin `ACME_EMAIL`; crear el compose (D-01). Verificar: test verde.
- [x] 3.2 RED→GREEN sin exposición al host (V-1, V-2): **ningún** servicio declara `ports` ni `container_name`; `frontend` declara `expose` con `8080` y `api` con `8000`. Triangular con test de regresión: `docker-compose.yml` dev sigue publicando `API_PORT/POSTGRES_PORT/REDIS_PORT`. Verificar: tests verdes + `test_compose_config.py` verde.
- [x] 3.3 RED→GREEN secretos (D-07): el texto no contiene `turnos:turnos` ni `POSTGRES_PASSWORD: turnos`; contiene `${POSTGRES_PASSWORD:?`, `${JWT_SECRET:?`, `${SEED_ADMIN_PASSWORD:?`, `${CORS_ORIGINS:?`, `${VITE_API_URL:?`; ningún servicio usa `env_file`; `DATABASE_URL` de api/worker/migrate se arma con `${POSTGRES_PASSWORD` y host `db`; `frontend.build.args.VITE_API_URL` interpolado. Verificar: tests verdes.
- [x] 3.4 RED→GREEN migración (D-04): `migrate` con command que incluye `alembic upgrade head` y `app.db.seed`, `restart: "no"`, depende de db/redis `service_healthy`; `api` y `worker` dependen de `migrate` con `service_completed_successfully`. Verificar: tests verdes.
- [x] 3.5 RED→GREEN robustez (D-03, D-06): `frontend, api, worker, db, redis` con `restart: unless-stopped`; healthcheck en `frontend` (wget 8080), `api` (`/health`), `db` (`pg_isready`), `redis` (`redis-cli ping`); `api` command con `--workers`, `--proxy-headers`, `--forwarded-allow-ips`; `db` monta `./backend/db/init` (btree_gist) y `pgdata`. Verificar: tests verdes.

## 4. Entorno de producción

- [x] 4.1 (archivo creado manualmente por el usuario 2026-11-06) RED→GREEN `test_c15_env_prod_example.py`: `.env.prod.example` lista `DOMAIN, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, JWT_SECRET, JWT_EXPIRE_MIN=30, SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD, CORS_ORIGINS=["https://…"], VITE_API_URL=https://api.…, UVICORN_WORKERS, WHATSAPP_MOCK=true, TZ=America/Argentina/Buenos_Aires` con placeholders (sin valores con forma de secreto real, p. ej. ≥32 hex), sin `ACME_EMAIL`; triangular: `git check-ignore .env.prod.example` → no ignorado y `.env` sigue ignorado; agregar `!.env.prod.example` a `.gitignore`. Verificar: tests verdes + `test_gitignore.py` y `test_env_example.py` verdes.

## 5. Runbook Easypanel y documentación

- [x] 5.1 Escribir `docs/deploy-vps.md` paso a paso: (1) crear proyecto en Easypanel; (2) crear servicio **Compose** con fuente Git (repo, branch, build path `/`, file `compose.prod.yml`; deploy key si el repo es privado); (3) entorno: reemplazar el `.env.example` de dev que el panel copia por el contenido de `.env.prod.example`, completar secretos (`openssl rand -hex 32`) y activar **Create .env file**; (4) DNS A `DOMAIN` y `api.DOMAIN` → IP del VPS; (5) dominios en la UI con HTTPS: `DOMAIN` → `frontend:8080`, `api.DOMAIN` → `api:8000` (HSTS opcional vía middleware Traefik); (6) Deploy y revisar logs de `migrate`; (7) login con `SEED_ADMIN_*`; (8) backup `pg_dump -Fc` / restore `pg_restore --clean` desde la consola del contenedor `db` o SSH + `docker exec`; (9) actualizar = push + Deploy (o Deployment Trigger), rollback por branch/commit; (10) convivencia con `calculadora-front/back`: sin puertos de host ni `container_name`; (11) supuestos S-1..S-5 a confirmar; (12) aviso de datos 100 % ficticios. Verificar con `test_c15_runbook.py` (menciona `compose.prod.yml`, `Create .env file`, `api.`, `8000`, `8080`, `pg_dump`, `pg_restore`, `ficticios`).
- [x] 5.2 Actualizar `CHANGES.md`: entrada `### [C-15] vps-deploy` con el formato de C-13/C-14 (Estado, Scope, Dependencias `C-14`, Governance ALTO, Leer antes), fila en la tabla Resumen, total de changes y la restricción "Deploy local" del encabezado → "Deploy local (dev/verify) + VPS Easypanel opcional (C-15)". Verificar: `grep -n "C-15" CHANGES.md` muestra entrada y fila.
- [x] 5.3 Actualizar `CLAUDE.md` y `AGENTS.md` (idénticos): "deploy local" → "deploy local + VPS Easypanel opcional (C-15)" en §Roadmap y nota en §Stack (Easypanel/Traefik + nginx estático en prod); actualizar `knowledge-base/08_arquitectura_propuesta.md` §Despliegue v1.0 y la nota de §Seguridad (cambio a pedido del usuario 2026-11-06, datos ficticios intactos). Verificar: `diff CLAUDE.md AGENTS.md` sin diferencias en esas secciones.

## 6. Integración

- [x] 6.1 Suite de configuración completa: `pytest app/tests/test_c15_*.py app/tests/test_compose_config.py app/tests/test_worker_docker.py app/tests/test_gitignore.py app/tests/test_env_example.py app/tests/test_frontend_shell.py` → verde; `openspec validate c-15-vps-deploy --strict` → OK.
- [x] 6.3 (Requiere Docker y permiso explícito del usuario; condición de D-03) Verificación del frontend de producción en navegador: construir localmente la imagen `frontend/Dockerfile.prod`, levantarla, abrir la app en un navegador y comprobar en la consola que no hay errores ni requests fallidos de CSS/JS (MIME types correctos, `/assets/*` 200 con `Content-Type` css/js), y recargar una ruta interna (p. ej. `/agenda` y `/lista-espera/<token>`) que debe devolver la SPA y no 404. Detener y borrar el contenedor al terminar. Sin permiso: pendiente del verify.
- [x] 6.2 (Requiere permiso explícito del usuario para Docker, regla dura) `docker compose -f compose.prod.yml --env-file .env.prod.example config -q` valida sintaxis e interpolación, y `docker compose -f compose.prod.yml --env-file .env.prod.example build` termina sin errores; luego `docker compose down` y cerrar Docker Desktop. Sin permiso: registrar como pendiente del verify.

## Workflow follow-up

- Verify con `tp-verify-docker` en modo `full` (con permiso) antes de archivar.
- Primer deploy real en Easypanel siguiendo `docs/deploy-vps.md` y confirmar supuestos S-1..S-5 (fuera del alcance del agente).
- Archivar con `/opsx:archive c-15-vps-deploy` y marcar `[x]` en `CHANGES.md`.
- Evaluar changes de seguimiento si se aprueban DA-01..DA-04.
