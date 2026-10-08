# Proposal — c-02-core-models-identidad-pacientes (C-02 `core-models-identidad-pacientes`)

> Nota de nombre: el change canónico en `CHANGES.md` es `C-02-core-models-identidad-pacientes`.
> El CLI `openspec` exige kebab-case minúsculas, por eso el directorio es
> `openspec/changes/c-02-core-models-identidad-pacientes/`. Ambos nombres refieren al mismo change.

## Why

Sin identidad persistida (roles, usuarios, pacientes, profesionales, sillones) ningún change
posterior puede implementarse: C-03 (auth/RBAC) necesita `usuario.rol_id`, C-04 (agenda)
necesita `profesional_id/sillon_id/paciente_id` como FKs reales. Este change crea el GATE 1
del roadmap: modelos + migración 001 + repos + seed sobre la base C-01 archivada (16/16).

## What Changes

- Modelos SQLAlchemy 2 async: `Rol`, `Usuario` (`rol_id` FK simple, un rol por usuario),
  `Paciente`, `Profesional`, `Sillon` (`sede` texto libre, sede única v1.0).
- Alembic (nuevo en este change) + migración `001`: tablas, PKs
  `BIGINT GENERATED ALWAYS AS IDENTITY`, `TIMESTAMPTZ`, índices
  (`usuario.email` unique, `paciente.dni/apellido/telefono`), FKs indexadas manualmente.
- Resguardo `>=1 admin activo` implementado **a nivel servicio, no DB** (RN-AU-03).
- Base repository genérico async (`backend/app/repos/base.py`) + repos por entidad sobre
  SQLAlchemy 2 async.
- Seed idempotente: roles fijos `admin/odontologo/secretaria` (alias Dueño=Admin sin tabla
  extra), 1 admin inicial (vía `SEED_ADMIN_*`), 1 sillón demo, 1 profesional demo con
  `agenda_config` JSON semanal.
- Soft-delete en `Paciente` (`deleted_at`, RN-GL-01).
- Tests TDD contra **Postgres real** (nunca SQLite): CRUD pacientes, unique email/dni,
  FK rol simple (rechaza segundo rol / usuario sin rol válido), seed idempotente.

## Capabilities

### New Capabilities

- `core-models-identidad-pacientes`: identidad y pacientes persistidos — modelos
  Rol/Usuario/Paciente/Profesional/Sillon, migración 001 Alembic, base repository
  genérico, seed idempotente, soft-delete Paciente y resguardo >=1 admin a nivel servicio.

### Modified Capabilities

(none — `foundation-setup` no cambia comportamiento; este change agrega la primera
capacidad de dominio sobre la infra C-01.)

## Impact

- Archivos nuevos: `backend/alembic.ini + backend/alembic/**` (env async + migración `001_*`),
  `backend/app/modelos/{rol,usuario,paciente,profesional,sillon}.py`,
  `backend/app/repos/{base,rol_repo,usuario_repo,paciente_repo,profesional_repo,sillon_repo}.py`,
  `backend/app/servicios/usuarios_servicio.py` (guard último admin),
  `backend/app/esquemas/{usuario,paciente,profesional,sillon}.py`,
  `backend/app/db/seed.py` (o `backend/app/core/seed.py`), tests `test_*` nuevos,
  dependencia `alembic` en `requirements.txt`.
- Sin breaking changes (no hay API pública previa que romper; routers C-01 siguen vacíos —
  el cableado a endpoints llega en C-03/C-04).
- Desbloquea: C-03 (auth/RBAC sobre `Usuario`) — GATE 1 → GATE 2; C-04/C-08 (FKs reales).
- Deuda explícita: sin endpoints CRUD expuestos todavía (solo repos + servicios internos);
  sin EXCLUDE anti-solapamiento (llega con `Turno` en C-04); sin hash real de password
  en seed más allá del placeholder configurable (hash Argon2/bcrypt definitivo en C-03).

## Leer antes (fuente de verdad)

- `knowledge-base/04_modelo_de_datos.md` — §Usuario, §Paciente, §Profesional, §Sillon, §Seed data inicial.
- `knowledge-base/03_actores_y_roles.md` — Dueño=Admin (alias), 3 roles fijos, un rol por usuario.
- `knowledge-base/05_reglas_de_negocio.md` — §RN-GL-01 (soft-delete), §RN-AU (en especial RN-AU-03 >=1 admin).
- `knowledge-base/08_arquitectura_propuesta.md` — capas api/servicios/repos/modelos/esquemas, Alembic, convenciones.
- `knowledge-base/10_preguntas_abiertas.md` — §IN-01 (Dueño=Admin), §IN-02 (rol FK simple) RESUELTAS.
- `openspec/specs/foundation-setup/spec.md` — base existente (compose, capas, env, btree_gist).
- `CHANGES.md` — fila C-02 (scope, governance CRITICO, dependencias C-01) + árbol/GATES.
- `openspec/config.yaml` — schema spec-driven, reglas proposal/tasks.
