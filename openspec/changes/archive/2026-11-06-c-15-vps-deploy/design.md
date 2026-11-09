# Design — C-15 `vps-deploy` (target: Easypanel)

> **Governance: ALTO** (infra + secretos + exposición pública). Decisiones D-01, D-02, D-04,
> D-05, D-06 y el uso de Easypanel con un único servicio Compose fueron **aprobados por el
> usuario (2026-11-06)**. D-03 (servidor estático) y D-07/D-08 quedan a revisión liviana.

## Aprobaciones del usuario (2026-11-06)

- Destino Easypanel (un servicio Compose con `compose.prod.yml`, dominios `DOMAIN` -> frontend:8080 y `api.DOMAIN` -> api:8000): aprobado.
- D-01, D-04, D-05, D-06, D-07: aprobadas. Sin puertos de host ni `container_name`: aceptado. Postgres 16 + Redis dentro del compose: aprobado.
- D-03 (nginx-unprivileged en 8080 con fallback SPA): **aprobada CON CONDICION**: no debe causar errores de carga de CSS ni JavaScript (MIME types correctos vía `include mime.types`, fallback SPA a `index.html` para rutas del cliente, `/assets/` servido correctamente, sin base path incorrecto). Verificación en navegador agregada como task 6.3 (requiere Docker y permiso explícito).
- Docs (runbook, `.env.prod.example`, entrada C-15 en `CHANGES.md`, `CLAUDE.md` + `AGENTS.md` sin la restricción "deploy local"): aprobado. DA-01..DA-04 siguen fuera de scope.

### Desviaciones de implementación

- `nginx.conf` vive en `frontend/deploy/nginx.conf` (no `deploy/` en la raíz) porque el contexto de build del frontend es `./frontend` y `COPY` no puede salir del contexto.

## Context

Ver `proposal.md` §Why. Estado real relevante (verificado en el repo):

- `backend/Dockerfile`: `python:3.12-slim`, root, copia solo `app/` (**no** copia `alembic/` ni
  `alembic.ini`, así que hoy no se puede migrar desde el contenedor), sin healthcheck.
- `frontend/Dockerfile`: `node:20-slim` + `npm run dev`. No está en el compose de dev;
  `test_frontend_shell.py` exige que exista → se conserva tal cual.
- `docker-compose.yml`: api/worker/db/redis, `turnos:turnos` literal, db y redis publicados.
  Lo usan el desarrollo y `tp-verify-docker`; `test_compose_config.py` lo testea → **no se toca**.
- Backend: routers en la raíz (`/auth`, `/turnos`, `/lista-espera`, `/seguridad`, …), sin
  prefijo `/api`. Cookie de refresh `path="/auth"`, `httponly`, `samesite="lax"`, sin `secure`.
- Frontend: `BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"` (build-time).
  La única ruta SPA por URL es `/lista-espera/:token`, que colisiona con el prefijo de API.
- Refresh store y colas en Redis → varios workers de uvicorn son seguros.
- `Settings` (pydantic-settings) hace fail-fast sin `JWT_SECRET`/`DATABASE_URL`;
  `cors_origins: list[str]` se parsea como **JSON** (`["https://..."]`).
- Seed `python -m app.db.seed` idempotente, fail-fast sin `SEED_ADMIN_PASSWORD`.
- El VPS ya corre **Easypanel** (proxy Traefik dueño de 80/443 + Let's Encrypt) con otras apps
  (`calculadora-front`, `calculadora-back`).

### Easypanel: hechos verificados vs supuestos

Fuente consultada 2026-11-06: <https://easypanel.io/docs/services/compose> y
<https://easypanel.io/docs/services/app>.

**Verificado en la documentación:**
- V-1 "Prefer Easypanel domains over `ports` for public HTTP traffic"; un puerto publicado en el
  host "must be unique across the server" → **no se publican puertos**.
- V-2 Evitar `container_name`: "a fixed container name can collide with another Compose
  project"; dejar que Compose genere nombres con scope.
- V-3 Un dominio de Compose "routes traffic to one internal service" y al crearlo se elige
  "the internal Compose service and port". Advertencia: no apuntar dominios a DB/colas.
- V-4 Variables de interpolación en formato `.env` en el editor de entorno; con
  **"Create .env file"** activado se escribe `.env` en el build path y Compose lo lee para
  interpolar. Advertencia: no imprimir secretos en el build ni commitearlos.
- V-5 Para fuentes Git, si el repo no tiene `.env`, Easypanel **copia `.env.example`** al editor.
  → En este repo eso copiaría el `.env.example` **de desarrollo**: el runbook indica
  reemplazarlo por el contenido de `.env.prod.example`.
- V-6 Fuente Git: Repository URL, Branch, Build Path (debe empezar con `/`) y Docker Compose
  File relativo al build path. Repos privados: deploy key SSH de solo lectura.
- V-7 Rutas relativas (build contexts, archivos referenciados) se resuelven desde el build path
  y deben existir en el repo → el bind mount `./backend/db/init` funciona con build path `/`.
- V-8 **Deploy** ejecuta `docker compose up --build -d`; cambios de fuente/entorno requieren
  redeploy. Existe una URL de **Deployment Trigger** para CI.
- V-9 Datos persistentes como volúmenes nombrados o binds explícitos; respaldar antes de cambiar
  definiciones de volúmenes. Logs filtrables por servicio interno.
- V-10 (página de App services) existe backup programado de volúmenes desde la pestaña Storage
  hacia un proveedor configurado; no está documentado para Compose.

**Supuestos a verificar en el panel durante el primer deploy (no documentados):**
- S-1 Easypanel conecta los servicios del Compose a su red de Traefik sin que declaremos redes;
  por eso el compose **no** define `networks` (usa la red por defecto del proyecto). Si el
  dominio no resuelve el servicio, agregar la red externa que indique el panel.
- S-2 `build.args` con interpolación (`VITE_API_URL: ${VITE_API_URL:?}`) se resuelve desde el
  `.env` generado (comportamiento estándar de Compose; Easypanel no documenta build args).
- S-3 Easypanel define su propio nombre de proyecto Compose → el archivo **no** declara `name:`
  (evita colisiones y deja el scoping al panel). Volúmenes `pgdata`, etc. quedan prefijados por
  proyecto, sin chocar con `calculadora-*`.
- S-4 Hay acceso a shell/consola de un contenedor del Compose desde el panel (documentado solo
  para App services: "Shell opens sh, bash…"). Alternativa garantizada: SSH al VPS +
  `docker exec` sobre el contenedor `db` (nombre visible en `docker ps`).
- S-5 `depends_on: condition: service_completed_successfully` y `restart` se respetan porque el
  panel usa `docker compose up` (V-8), no Swarm.

## Goals / Non-Goals

**Goals:** desplegar todo como un único servicio Compose de Easypanel apuntando a
`compose.prod.yml`; testeable por TDD leyendo archivos (sin Docker en los tests); cero cambios en
código de aplicación (`backend/app/**` salvo tests, `frontend/src/**`); cero interferencia con
otras apps del panel.

**Non-Goals:** reverse proxy/TLS propio (lo hace Traefik de Easypanel), CI/CD propio (opcional
vía Deployment Trigger), registry de imágenes, backups automáticos programados, observabilidad,
multi-sede, datos reales, cambios a `GET /seguridad` (DA-04) o a la cookie (DA-03).

## Decisions

### D-01 — `compose.prod.yml` standalone, no override (aprobada)
Archivo completo e independiente en la raíz. Un override **suma** `ports`/`environment` y
quitar los puertos de db/redis y el `turnos:turnos` literal exigiría `!reset`; además Easypanel
toma un único "Docker Compose File" (V-6). Sin `name:` (S-3) ni `container_name` (V-2).
- *Costo*: duplicación de ~40 líneas de db/redis/worker. Aceptable.

### D-02 — Dos dominios: `DOMAIN` → frontend, `api.DOMAIN` → api:8000 (aprobada)
Los dominios se asignan en la UI de Easypanel (V-3) con HTTPS: `DOMAIN` → servicio `frontend`
puerto `8080`; `api.DOMAIN` → servicio `api` puerto `8000`. Build arg
`VITE_API_URL=https://api.DOMAIN`; `CORS_ORIGINS=["https://DOMAIN"]`.
- *Por qué*: replica el modelo de dev (SPA y API en orígenes distintos del mismo *site*, CORS
  con credenciales); la cookie `path=/auth` sigue funcionando. **Cero cambios en `auth.py`**.
- *Alternativa A (mismo origen + `/api`)*: rompe el envío de la cookie `path=/auth`.
- *Alternativa B (rutas backend en la raíz)*: colisiona con `/lista-espera/:token`.

### D-03 — Frontend: build estático servido por `nginxinc/nginx-unprivileged:alpine` **[REVISIÓN]**
`frontend/Dockerfile.prod` multi-stage: `node:20-slim` (`npm ci`, `ARG VITE_API_URL`,
`npm run build`) → `nginxinc/nginx-unprivileged:1.27-alpine` con `dist/` en
`/usr/share/nginx/html` y `deploy/nginx.conf` (`listen 8080`, `try_files $uri $uri/ /index.html`,
`gzip on`, cache largo para `/assets/*` con hash, `no-cache` para `index.html`,
`server_tokens off`, `X-Content-Type-Options nosniff`, `Referrer-Policy`). `expose: ["8080"]`.
- *Por qué nginx y no Caddy*: la variante oficial *unprivileged* de NGINX corre como no-root
  (uid 101) en 8080, cumpliendo el requisito de no-root sin trucos; la config SPA es estándar
  y diminuta. Caddy aportaría TLS automático, que acá sobra (lo hace Traefik) y habría que
  desactivar (`auto_https off`, `:80`), y su imagen oficial corre como root.
- *Alternativa*: `nginx:alpine` común — corre master como root y escucha en 80.
- *HSTS*: lo debe poner Traefik (middleware en la UI de dominios de Easypanel), no nginx, porque
  nginx ve HTTP plano. Documentado como opcional en el runbook.
- `npm run build` corre `tsc --noEmit` antes de `vite build`: errores de tipos frenan el deploy.
- Healthcheck: `wget -q --spider http://127.0.0.1:8080/` (busybox en alpine).

### D-04 — Migraciones: servicio one-off `migrate` (aprobada)
`migrate` usa la imagen del backend con
`command: sh -c "alembic upgrade head && python -m app.db.seed"`, `restart: "no"`, depende de
`db`/`redis` healthy; `api` y `worker` dependen de `migrate` con
`service_completed_successfully` (S-5). El seed carga la demo ficticia completa (idempotente).

### D-05 — `backend/Dockerfile` endurecido y compartido dev/prod (aprobada)
`ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1`, usuario `app` (uid 10001), `COPY --chown`,
copia `app/ alembic/ alembic.ini`. `CMD` por defecto sin cambios y **sin `HEALTHCHECK` en la
imagen** (el worker/migrate no sirven HTTP): el healthcheck de `api` va en `compose.prod.yml`
(`python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"`).
- `.dockerignore` backend: `.env*`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`.

### D-06 — uvicorn en prod (aprobada)
`uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}
--proxy-headers --forwarded-allow-ips=*`, `expose: ["8000"]`. Confiar en `X-Forwarded-*` es
seguro porque `api` no publica puertos: solo la alcanza Traefik de Easypanel por la red interna.

### D-07 — Secretos y entorno **[REVISIÓN liviana]**
- Todo valor entra por el editor de entorno de Easypanel con **"Create .env file"** activado
  (V-4). El compose usa **interpolación explícita en `environment:`** por servicio (no
  `env_file:`), para que cada contenedor reciba solo lo que necesita y el fallo por variable
  faltante sea explícito.
- Obligatorias con `${VAR:?mensaje}`: `POSTGRES_PASSWORD`, `JWT_SECRET`, `SEED_ADMIN_PASSWORD`,
  `CORS_ORIGINS`, `VITE_API_URL`. Con default: `POSTGRES_USER:-turnos`, `POSTGRES_DB:-turnos`,
  `UVICORN_WORKERS:-2`, `JWT_EXPIRE_MIN:-30`, `WHATSAPP_MOCK:-true`,
  `TZ:-America/Argentina/Buenos_Aires`, `SEED_ADMIN_EMAIL:-admin@example.com`.
- `DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}`
  armado en compose; contraseña hex (`openssl rand -hex 32`) para no romper la URL.
- `DOMAIN` queda en `.env.prod.example` como referencia para armar `CORS_ORIGINS` y
  `VITE_API_URL` (no se usa interpolación anidada `${A:-${B}}` para no depender de la versión de
  Compose del panel).
- `REDIS_URL=redis://redis:6379/0` (sin password: no publicado; ver DA-02).
- `.gitignore` agrega `!.env.prod.example`. `.env.prod.example` sin secretos reales.

### D-08 — Tests (TDD, sin Docker)
Patrón de `test_compose_config.py` (`yaml.safe_load` + texto).
- `test_c15_compose_prod.py`: servicios `frontend, api, worker, migrate, db, redis`; **ningún**
  servicio con `ports`; ninguno con `container_name`; sin `name:` top-level; `expose` 8080 en
  frontend y 8000 en api; sin `turnos:turnos` ni password literal; `${…:?` para los secretos de
  D-07; `restart: unless-stopped` en larga vida; healthcheck en frontend/api/db/redis; `migrate`
  con `alembic upgrade head` + seed y `restart: "no"`; api/worker dependen de migrate con
  `service_completed_successfully`; api con `--workers`, `--proxy-headers`,
  `--forwarded-allow-ips`; build arg `VITE_API_URL`; sin servicio/imagen `caddy` ni
  `ACME_EMAIL`; regresión: `docker-compose.yml` dev intacto.
- `test_c15_dockerfiles.py`: backend `USER` no-root antes de `CMD`, copia `alembic`;
  `frontend/Dockerfile.prod` multi-stage, `npm ci`, `npm run build`, `ARG VITE_API_URL`, etapa
  final `nginxinc/nginx-unprivileged`, sin `npm run dev`/`vite`; `.dockerignore` de ambos.
- `test_c15_nginx_conf.py`: `listen 8080`, `try_files … /index.html`, `server_tokens off`.
- `test_c15_env_prod_example.py`: claves requeridas, placeholders, no ignorado por git.
- `test_c15_runbook.py`: el runbook menciona `compose.prod.yml`, `Create .env file`, `api.`,
  `8000`, `8080`, `pg_dump`, `pg_restore`, `ficticios`.

## UI Mockups

- Design system revision: n/a
- Decision: no (no UI) — 2026-11-06. Change de infraestructura; `frontend/src/**` no cambia.
- Mockups: n/a
- Approval: n/a
- Preview: n/a
- Visual verify: n/a

## Risks / Trade-offs

- [Easypanel copia el `.env.example` de dev al editor (V-5)] → runbook: reemplazar todo por
  `.env.prod.example` antes del primer Deploy; los `:?` frenan el deploy si falta algo.
- [Red de Traefik no conectada automáticamente (S-1)] → verificar al asignar dominios; plan B
  documentado (red externa indicada por el panel).
- [Build de Node en el VPS compartido con otras apps] → `npm ci` + `tsc` usan ~1 GB RAM; runbook
  sugiere swap y deployar fuera de horario de uso de `calculadora-*`.
- [Cookie refresh sin `Secure`] → HTTPS forzado por Traefik; DA-03.
- [OpenAPI `/docs` público en `api.DOMAIN`] → aceptable para demo; DA-01.
- [`/seguridad` declara TLS pendiente aunque esté activo] → conservador; DA-04.
- [`down -v` o borrar el servicio en el panel elimina `pgdata`] → runbook: backup previo (V-9).
- [Plazo 08/11/2026] → change aislado; recortable sin impacto en C-01..C-14.

## Migration Plan

Detalle en `docs/deploy-vps.md` (task 6.1). Resumen: proyecto Easypanel → servicio Compose
(Git, branch, build path `/`, file `compose.prod.yml`) → entorno desde `.env.prod.example` con
"Create .env file" → DNS A `DOMAIN` y `api.DOMAIN` → dominios en la UI (frontend:8080,
api:8000, HTTPS) → Deploy → logs de `migrate` → login admin. Actualizar = push + Deploy (o
Deployment Trigger). Rollback = Branch/commit anterior + Deploy; si una migración dañó datos,
restaurar el último `pg_dump` (`pg_restore --clean`).

## Decisiones abiertas para el usuario (fuera de scope)

- **DA-01** ¿Deshabilitar `/docs` y `/openapi.json` en prod? (flag en `main.py`).
- **DA-02** ¿Password en Redis (`requirepass`)? No publicado → hoy innecesario.
- **DA-03** ¿Cookie refresh con `Secure` vía env? Toca `auth.py` (CRÍTICO) → change aparte.
- **DA-04** ¿`GET /seguridad` declara TLS activo en VPS? MODIFIED de `seguridad-publica` →
  change aparte.

## Open Questions

- Dominio concreto: lo define el operador en el entorno; no afecta el diseño.
- Supuestos S-1..S-5: se confirman en el primer deploy; ninguno cambia la estructura de tasks.
