# TP-Turnos-Odontologo — config overlay for tp-verify-docker

Project-specific values. The core skill (`SKILL.md`) defines the workflow; this file overrides defaults for this repo. Read it whenever the working directory is TP-Turnos-Odontologo.

## Stack

Python 3.12 + FastAPI 0.110+ + SQLAlchemy 2 async + Postgres 16 + Redis 7 + React 18 + TS 5 + Vite 5. TZ=`America/Argentina/Buenos_Aires`.

## Services (docker compose)

- `db` (postgres:16), `redis` (redis:7), `api`, `worker`. Verify lifts `db redis` minimum.
- Docker Desktop Windows path: `%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe`. Confirm daemon via `docker info`.

## Ports and env

- Default `POSTGRES_PORT=5432`; if a local PG18 holds 5432 → `POSTGRES_PORT=5433` + `DATABASE_URL_TEST=postgresql+asyncpg://turnos:turnos@localhost:5433/turnos` (match compose user/db turnos:turnos + db_utils.py).
- Required env: `DATABASE_URL, REDIS_URL, JWT_SECRET, JWT_EXPIRE_MIN=30, WHATSAPP_*, GCAL_*, CORS_ORIGINS, SEED_ADMIN_*, TZ`. `.env.example` versioned, `.env` gitignored.

## Migrations

- Alembic heads: revisar con `alembic heads`; cadena actual `001_core_identidad_pacientes → 002_turno → 003_notificacion → 004_espera → 005_clinica → 006_presupuestos_cc → 007_caja_recibos → 008_obras_sociales → 009_auditoria_admin`; actualizar esta línea al crear cada migración.
- `btree_gist` extension required for `EXCLUDE USING gist` (overlap profesional/sillón). Verify checks `CREATE EXTENSION IF NOT EXISTS btree_gist`.
- Known false ROJO: downgrade test assuming old head — update the test, not the DB.

## Test commands

- Backend quick: `pytest -k <change-keyword>`; full: `pytest` (whole suite).
- Frontend: `npx tsc --noEmit`; full adds `npx vitest run` + `npm run build`.
- Spec: `openspec validate --all --strict` (full) or scoped validate (quick).
- E2E (only C-12): Playwright critical path (reserva pública → confirmación).

## Flaky / time-sensitive

- Concurrent overlap tests: retry x3 before ROJO.
- `freezegun` for 72 h token, 2 h espera, 30 min JWT + Pydantic `TypeAdapter` warmup on cold runs.
- Never SQLite for constraint tests (no EXCLUDE/GiST support).

## Hard rules checklist (RN-GL / RN-CO / RN-TU)

1. `extra='forbid'` en esquemas Pydantic.
2. `Annotated[..., Depends(...)]` para auth/DB.
3. Cero `any` en TS.
4. Soft-delete clínico/administrativo (RN-GL-01).
5. Saldo CC derivado; anulación por contramovimiento + motivo; cierre de caja diario (RN-CO-01..04).
6. Sobreturno solo con `sobre_turno=true + motivo` auditado (RN-TU-01/02).
7. Lista de espera con expiración 2 h + cascada (RN-TU-06).
8. Presupuesto con hallazgo FDI 11–48 + catálogo versionado (RN-CL-01/03).
9. Sin PHI en WhatsApp/SMS; verificar firma webhook Meta (RN-CL-04, RN-NO-04, RN-AU-04).
10. Sede única (`Sillon.sede` texto libre); rol FK simple `usuario.rol_id`, Dueño=alias Admin; pagos `efectivo|transferencia|tarjeta_simulada`; datos 100% ficticios.

## Change order (CHANGES.md)

Camino crítico: `C-01 → C-02 → C-03 → C-04 → C-05 → C-09 → C-10`. Turnos-pura: `... → C-06 → C-07`. Full verify required before archive on critical-path changes.
