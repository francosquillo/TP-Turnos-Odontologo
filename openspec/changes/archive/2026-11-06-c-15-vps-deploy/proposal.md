# Proposal — C-15 `vps-deploy`

## Why

Hoy el sistema solo corre en local: el `docker-compose.yml` publica Postgres y Redis, usa
`turnos:turnos` hardcodeado, el backend corre como root y el frontend solo existe como servidor
de desarrollo de Vite. El equipo necesita publicar la demo en su VPS, que ya corre **Easypanel**
(proxy Traefik con HTTPS automático, junto a otras apps como `calculadora-front/back`), con
dominio propio y HTTPS para la presentación del TP (plazo 08/11/2026), sin romper el flujo de
desarrollo ni el verify con Docker (`.claude/skills/tp-verify-docker`).

> **Revisión de restricción (a pedido del usuario, 2026-11-06):** este change revisa la
> restricción v1.0 **"Deploy local Docker Compose"** del checkpoint 2026-10-05 (CLAUDE.md /
> AGENTS.md §Roadmap, CHANGES.md encabezado, `knowledge-base/08` §Despliegue v1.0). El
> despliegue pasa a ser **local (dev/verify) + VPS opcional con Easypanel (demo productiva)**.
> Todas las demás restricciones siguen vigentes: los datos siguen siendo **100 % ficticios**
> (RN-GL-03) y `GET /seguridad` sigue declarándolo; pagos simulados, sin AFIP, sede única.

## What Changes

- **Nuevo** `compose.prod.yml` *standalone* (no override), desplegado como **un único servicio
  Compose de Easypanel**, con servicios `frontend`, `api`, `worker`, `migrate` (one-off), `db`,
  `redis`: **ningún puerto publicado en el host** (TLS y ruteo por dominio los hace Traefik de
  Easypanel, configurados en su UI), sin `container_name`, secretos solo por entorno
  (`POSTGRES_PASSWORD`, `JWT_SECRET`, `SEED_ADMIN_PASSWORD`, `CORS_ORIGINS`, `VITE_API_URL`
  obligatorios con `${VAR:?}`), `restart: unless-stopped`, healthchecks.
- **Dos dominios** asignados en la UI de Easypanel: `DOMAIN` → `frontend:8080` y
  `api.DOMAIN` → `api:8000`, ambos con HTTPS (Let's Encrypt del panel).
- **Nuevo** `frontend/Dockerfile.prod` multi-stage: `npm ci` + `npm run build` con
  `VITE_API_URL` como build-arg, etapa final `nginxinc/nginx-unprivileged:alpine` (no-root,
  HTTP plano en 8080, fallback SPA a `index.html`) con `deploy/nginx.conf`. El
  `frontend/Dockerfile` de dev queda intacto.
- **Modificado** `backend/Dockerfile` (endurecido, compatible con dev): usuario no-root, copia
  `alembic/` + `alembic.ini` (hoy no se copian: las migraciones no podían correr en el
  contenedor), `PYTHONDONTWRITEBYTECODE/PYTHONUNBUFFERED`. El `CMD` por defecto no cambia; el
  healthcheck de `api` se declara en `compose.prod.yml`.
- **Nuevo** servicio `migrate`: `alembic upgrade head && python -m app.db.seed` (seed idempotente
  con `SEED_ADMIN_*`); `api` y `worker` dependen de él con `service_completed_successfully`.
- `api` prod con `uvicorn --workers ${UVICORN_WORKERS:-2} --proxy-headers
  --forwarded-allow-ips=*` (solo alcanzable por Traefik de Easypanel en la red interna).
- **Nuevos** `backend/.dockerignore` y `frontend/.dockerignore`.
- **Nuevo** `.env.prod.example` versionado (placeholders, sin secretos) para pegar en el editor
  de entorno de Easypanel, y `!.env.prod.example` en `.gitignore`.
- **Nuevo** runbook `docs/deploy-vps.md`: paso a paso en Easypanel (proyecto → servicio Compose
  desde Git → entorno → DNS → dominios → Deploy → logs de `migrate` → backups con `pg_dump` →
  actualizaciones por redeploy), sin interferir con otras apps del panel.
- **Nuevos** tests de configuración (TDD, sin Docker): `test_c15_compose_prod.py`,
  `test_c15_dockerfiles.py`, `test_c15_nginx_conf.py`, `test_c15_env_prod_example.py`,
  `test_c15_runbook.py` en `backend/app/tests/`.
- **Docs**: entrada C-15 en `CHANGES.md` (dependencia C-14) y la mención "deploy local" en
  `CLAUDE.md`/`AGENTS.md` (sincronizados), encabezado de `CHANGES.md` y
  `knowledge-base/08_arquitectura_propuesta.md` §Despliegue.
- **Sin cambios**: `docker-compose.yml` de dev, endpoints, modelos, migraciones, `frontend/src/`.

## Capabilities

### New Capabilities
- `production-deploy`: despliegue productivo en un VPS con Easypanel como un único servicio
  Compose, dominio + HTTPS gestionados por el panel, imágenes endurecidas, migración en el
  deploy, runbook de operación y respaldo.

### Modified Capabilities
<!-- Ninguna: `foundation-setup` (compose local) no cambia de requisitos; el endurecimiento del
     backend/Dockerfile es compatible con el compose de dev. `seguridad-publica` no cambia en
     este change (ver design.md, DA-04). -->

## Impact

- **Archivos nuevos**: `compose.prod.yml`, `deploy/nginx.conf`, `frontend/Dockerfile.prod`,
  `backend/.dockerignore`, `frontend/.dockerignore`, `.env.prod.example`, `docs/deploy-vps.md`,
  5 archivos de test `test_c15_*.py`.
- **Archivos modificados**: `backend/Dockerfile`, `.gitignore`, `CHANGES.md`, `CLAUDE.md`,
  `AGENTS.md`, `knowledge-base/08_arquitectura_propuesta.md`.
- **Dependencias**: imagen `nginxinc/nginx-unprivileged:alpine` (nueva, solo prod). Sin paquetes
  Python/npm nuevos. Plataforma: Easypanel existente en el VPS (Traefik + Let's Encrypt).
- **Convivencia**: sin puertos de host ni nombres fijos de contenedor → no choca con
  `calculadora-front/back` ni otras apps del panel.
- **Governance**: **ALTO** (infra + secretos + exposición pública). Decisiones principales
  aprobadas por el usuario el 2026-11-06 (ver `design.md`).
- **Dependencia de change**: `C-14` (último archivado). No bloquea ni modifica C-01..C-14.
- **Leer antes**: `knowledge-base/08_arquitectura_propuesta.md` §Seguridad, §Despliegue v1.0,
  §Variables de entorno; `knowledge-base/02_descripcion_general.md` §Arquitectura;
  `knowledge-base/05_reglas_de_negocio.md` §RN-GL-03; `docker-compose.yml`;
  `.claude/skills/tp-verify-docker/references/tp-turnos-config.md`;
  <https://easypanel.io/docs/services/compose>.
- **Riesgo de plazo**: el plazo duro es 08/11/2026; el change es de infraestructura aislada y
  puede recortarse sin afectar C-01..C-14.
