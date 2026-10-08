# Design — c-02-core-models-identidad-pacientes

## Context

Ver `proposal.md` (Why). Estado actual: C-01 archivado 16/16 — compose
(api + worker + postgres:16 + redis:7), estructura
`backend/app/{api,servicios,repos,modelos,esquemas,worker,tests}` + `core/` + `main.py`,
config solo env con fail-fast, `btree_gist` habilitado, routers vacíos por recurso
(`auth, pacientes, profesionales, sillones, ...`), tests base verdes.
Restricciones vinculantes: rol FK simple (NUNCA tabla `usuario_rol`), Dueño=Admin
(NUNCA rol separado), sede única texto libre, datos 100% ficticios, soft-delete
clínico/administrativo, Pydantic `extra='forbid'`, PK `BIGINT GENERATED ALWAYS AS
IDENTITY` (serial prohibido), `TIMESTAMPTZ`, `NUMERIC` dinero, `TEXT`+`CHECK`,
`snake_case` sin comillas, indexar toda FK manualmente, tests de constraints contra
Postgres real (NUNCA SQLite).

## Goals / Non-Goals

**Goals:**

- Migración `001` reproducible (upgrade/downgrade) que crea Rol/Usuario/Paciente/
  Profesional/Sillon con tipos e índices del contrato.
- Repos async testeables + servicio con guard `>=1 admin activo`.
- Seed idempotente que deja demo mínima (roles + admin + sillón + profesional) sin
  duplicar en re-ejecuciones.
- Tasks listas para TDD estricto en apply (RED primero, verificación por task,
  Postgres real).

**Non-Goals:**

- Endpoints CRUD expuestos (routers se cablean en C-03/C-04; acá solo modelos +
  repos + servicios internos).
- JWT/RBAC/hash definitivo (C-03; acá solo `password_hash` como columna + seed
  configurable).
- Constraint `EXCLUDE` anti-solapamiento (llega con `Turno` en C-04).
- Catálogos clínicos, cobros, OS, notificaciones (C-06..C-11).

## Decisions

### D-01 — Alembic para la migración 001 (vs SQL puro versionado a mano)

Alembic con `env.py` async (`async_engine_from_config` sobre `DATABASE_URL`,
`target_metadata = Base.metadata`, modo offline/online). Migración
`001_core_identidad_pacientes`: `create_table` + índices + reversión completa en
`downgrade()`. `alembic.ini` con `script_location = backend/alembic`, sin URL
hardcodeada (la inyecta el env). Alternativa (SQL puro en `db/init/`) descartada:
el init es para bootstrap de extensión (C-01); las tablas de dominio necesitan
historial versionado, upgrade/downgrade y `autogenerate` futuro para C-04/C-08.
Skill: `fastapi-templates` (sesión async + DI), `supabase-postgres-best-practices`
(cargar antes de tocar Postgres).

### D-02 — Base repository genérico async + repos finos por entidad

`backend/app/repos/base.py`: `BaseRepository[M]` con `get/list/crear/actualizar`
async tipados por entidad; `PacienteRepository` agrega `listar_activos()`
(filtra `deleted_at IS NULL`) y `soft_delete()` (setea `deleted_at=now()`, nunca
`DELETE`). Servicios importan repos, nunca `AsyncSession` directo; `Annotated[...,
Depends(...)]` para inyección (patrón C-01 `core/deps.py`). Alternativa (repos
duplicados por entidad sin base) descartada: 5 entidades × CRUD = duplicación;
la base se prueba una vez y se hereda. Skill: `fastapi-templates`.

### D-03 — Guard `>=1 admin activo` a nivel servicio (no constraint DB)

`usuarios_servicio.deshabilitar/eliminar()` cuenta admins activos excluyendo el
objetivo; si el conteo quedaría en 0, aborta con error de dominio (el endpoint
C-03 lo mapea a 409/422). Alternativa (trigger/CHECK en DB) descartada: la regla
es "al menos uno activo", no expresable como CHECK fila-local; un trigger
acoplaría política de negocio al esquema y complicaría el seed. El servicio es
testeable sin DB (repos mockeados) + test de integración contra PG real.
Trazabilidad: RN-AU-03. Skill: `test-driven-development` (RED: desactivar último
admin falla; GREEN: guard mínimo).

### D-04 — Seed idempotente por upsert natural, no por IDs fijos

`seed.py` con funciones `seed_roles()`, `seed_admin()`, `seed_demo()` ejecutadas en
orden, cada una con guarda `SELECT ... WHERE clave_natural` antes de `INSERT`
(`rol.nombre`, `usuario.email`, `sillon.nombre`); todo dentro de una transacción
con `flush` ordenado (roles → admin → sillón → profesional). Re-ejecutar el seed
(retries de compose, demo repetida) no duplica ni falla en unique. Admin inicial
desde `SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD` (fail-fast si faltan, coherente con
D-03 de C-01). Datos 100% ficticios con prefijo `Demo`. Alternativa (seed con
`INSERT` ciego + `ON CONFLICT DO NOTHING` masivo) descartada: oculta errores
reales de esquema; las guardas explícitas son auditables por rol/entidad.

### D-05 — Tipos Postgres estrictos según skill + KB 04

PK `BIGINT GENERATED ALWAYS AS IDENTITY` (serial prohibido); `TIMESTAMPTZ NOT NULL
DEFAULT now()` (`created_at`, `deleted_at` nullable); `TEXT NOT NULL` + `CHECK
(LENGTH(col) <= n)` en vez de `varchar(n)`; email `CITEXT`-free: `TEXT` unique +
índice expresión `LOWER(email)` para lookup case-insensitive; `rol.nombre TEXT +
CHECK (nombre IN ('admin','odontologo','secretaria'))` (set chico estable → CHECK
válido; si el negocio evoluciona se migra a lookup, pero v1.0 son 3 fijos);
`profesional.agenda_config JSONB NOT NULL DEFAULT '{}'` + índice GIN (semi-estructurado
opcional: duración slot + horario semanal); `paciente.dni TEXT UNIQUE NULLS NOT
DISTINCT` evitado — DNI nullable con unique parcial `WHERE dni IS NOT NULL`
(múltiples NULL permitidos, duplicados reales rechazados); `BOOLEAN NOT NULL
DEFAULT` en `activo`; `usuario_id` nullable en Profesional (`ON DELETE SET NULL`,
profesional demo sin cuenta); toda FK con `CREATE INDEX` manual (Postgres no los
crea solo). `sillon.sede TEXT NOT NULL DEFAULT 'Sede única'` (texto libre,
extensible post-TP). Skill: `postgresql-table-design` (reglas núcleo),
`supabase-postgres-best-practices` (performance/conexiones/seguridad antes de DDL).

### D-06 — Soft-delete solo en Paciente (este change), con filtro por defecto

`paciente.deleted_at TIMESTAMPTZ NULL`; `DELETE` físico prohibido en repo
(`soft_delete()` + `listar_activos()`); tests: eliminado no aparece en listados
pero la fila persiste (RN-GL-01). `Usuario/Profesional/Sillon` sin soft-delete en
C-02 (su baja lógica llega con su dominio: usuarios en C-03/C-12, clínica en
C-08); no se anticipa comportamiento que ningún spec exige. Alternativa
(soft-delete global con mixin en las 5 tablas) descartada: YAGNI + auditoría del
TP exige el Paciente ahora; el mixin se extrae en REFACTOR si C-08 lo necesita.

### D-07 — Esquemas Pydantic estrictos desde el día 1

`esquemas/{usuario,paciente,profesional,sillon}.py` con `extra='forbid'`,
`response_model` sin `password_hash`, `consentimiento_datos` requerido en crear
paciente (RN-GL-03 futuro). Sin endpoints todavía, pero los esquemas se prueban
(unit: campo extra → 422-equivalente `ValidationError`, email inválido → error).
Skill: `fastapi-templates` (borde estricto).

## Risks / Trade-offs

- [Risk] Alembic `env.py` async mal configurado rompe `upgrade head` en CI local →
  Mitigación: task 1.x verifica `alembic upgrade head && downgrade -1 && upgrade head`
  contra PG real del compose; `TEST_DATABASE_URL` separada para no pisar la demo.
- [Risk] `UNIQUE` en `dni` nullable permite duplicados si se modela mal →
  Mitigación: unique parcial `WHERE dni IS NOT NULL` + test RED con dos NULL (pasa)
  y dos DNI iguales (falla).
- [Risk] Seed con password placeholder débil queda en demo → Mitigación: password solo
  desde `SEED_ADMIN_*`, nunca hardcodeado; documentado como ficticio; hash definitivo
  en C-03 (deuda explícita en proposal).
- [Risk] `agenda_config` JSONB sin schema se vuelve bolsa de campos →
  Mitigación: esquema Pydantic `AgendaConfig` valida forma semanal en seed + test;
  índice GIN solo para containment, no para campos ad-hoc.
- [Trade-off] Sin RLS en v1.0 (RBAC a nivel app según skill) → se acepta: 3 roles +
  deploy local; RLS se evalúa post-TP si hay datos reales (RN-GL-03).
- [Trade-off] Guard último-admin solo en servicio (bypass con SQL directo posible) →
  se acepta: amenaza fuera del modelo v1.0 (solo app escribe); documentado.

## Migration Plan

Deploy: `docker compose up -d db` → `alembic upgrade head` → `python -m app.db.seed`
(idempotente, re-ejecutable). Rollback: `alembic downgrade -1` (elimina las 5 tablas;
seed es solo INSERT, no necesita reversión propia) + `docker compose down -v` si se
quiere volumen limpio. Sin downtime concerns (pre-producción, deploy local).

## Open Questions

Ninguna que cambie specs, enfoque o tasks. Diferida a su change: Argon2 vs bcrypt
(C-03), forma semanal exacta del `agenda_config` si C-04 pide slots distintos
(hoy: `{duracion_slot_min, horario: {dia: [[ini,fin]]}}` validado por Pydantic).
