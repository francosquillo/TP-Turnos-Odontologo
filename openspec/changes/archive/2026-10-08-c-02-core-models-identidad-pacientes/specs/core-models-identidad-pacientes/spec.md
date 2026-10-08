# Spec Delta — core-models-identidad-pacientes

## Purpose

Persiste la identidad del sistema (roles, usuarios, pacientes, profesionales y sillones)
con integridad a nivel base de datos, repositorios async reutilizables y datos semilla
demo, para que la autenticación y la agenda operen sobre entidades reales.

## ADDED Requirements

### Requirement: Roles fijos con alias Dueño=Admin

El sistema SHALL proveer exactamente los roles `admin`, `odontologo` y `secretaria`,
sin rol Dueño separado (Dueño es alias de Admin, IN-01) y sin tabla intermedia
`usuario_rol` (rol simple por FK, IN-02).

#### Scenario: Seed crea los tres roles y ningún otro

- **WHEN** se ejecuta el seed sobre una base limpia y se lista `rol`
- **THEN** existen exactamente `admin`, `odontologo` y `secretaria`, y no existe ningún rol `dueno`

#### Scenario: Nombre de rol fuera del catálogo es rechazado

- **WHEN** se intenta insertar un rol con nombre `dueno` o cualquier otro fuera del catálogo
- **THEN** la base rechaza la fila por violación de CHECK

### Requirement: Usuario con un solo rol y email único

El sistema SHALL exigir que todo usuario tenga exactamente un `rol_id` válido
(FK a `rol`), email único (lookup case-insensitive), `activo` booleano y
`created_at` con zona horaria; y SHALL impedir que la desactivación o eliminación
del último admin activo tenga éxito (resguardo RN-AU-03 a nivel servicio).

#### Scenario: Crear usuario con rol válido

- **WHEN** se crea un usuario con email nuevo y `rol_id` de `secretaria`
- **THEN** persiste con `activo=true` y `created_at` en zona horaria del sistema

#### Scenario: Email duplicado con distinta capitalización es rechazado

- **WHEN** existe `Admin@demo.test` y se crea `admin@demo.test`
- **THEN** la operación falla por violación de unicidad de email

#### Scenario: Usuario con segundo rol es imposible por modelo

- **WHEN** un consumidor intenta asignar dos roles a un mismo usuario
- **THEN** el modelo no ofrece ningún campo ni tabla para ello y la única vía
  (cambiar `rol_id`) deja exactamente un rol vigente

#### Scenario: Desactivar al último admin activo es bloqueado

- **WHEN** existe un único admin activo y se intenta desactivarlo o eliminarlo
- **THEN** el servicio aborta la operación con error de dominio y el admin sigue activo

### Requirement: Paciente con CRUD, índices y soft-delete

El sistema SHALL persistir pacientes con nombre, apellido, DNI nullable único,
teléfono, email, cobertura nullable, notas y consentimiento de datos; SHALL
indexar `dni`, `apellido` y `telefono`; y SHALL implementar baja lógica
(`deleted_at`, RN-GL-01): el paciente eliminado no aparece en listados pero su
fila persiste.

#### Scenario: CRUD de paciente ficticio

- **WHEN** se crea, lee, actualiza y elimina (lógico) un paciente con datos ficticios
- **THEN** cada operación retorna el estado esperado y la lectura por id confirma los cambios

#### Scenario: DNI duplicado es rechazado, DNI nulo múltiple es permitido

- **WHEN** se crean dos pacientes con el mismo DNI no nulo
- **THEN** el segundo falla por unicidad; y **WHEN** se crean dos pacientes sin DNI
- **THEN** ambos persisten sin error

#### Scenario: Paciente con soft-delete no aparece en listados

- **WHEN** se elimina lógicamente un paciente y se lista `pacientes activos`
- **THEN** el paciente no aparece en el listado pero su fila existe con `deleted_at` no nulo

### Requirement: Profesional con agenda semanal configurable

El sistema SHALL persistir profesionales con matrícula, especialidades,
`usuario_id` nullable (vínculo opcional con cuenta) y `agenda_config` JSON con
duración de slot y horario semanal, validado por esquema.

#### Scenario: Profesional demo con agenda semanal válida

- **WHEN** se ejecuta el seed y se lee el profesional demo
- **THEN** tiene matrícula y especialidad ficticias y `agenda_config` con
  `duracion_slot_min` positivo y al menos un día con franja `[ini, fin]` válida

#### Scenario: Agenda con forma inválida es rechazada

- **WHEN** se intenta guardar un `agenda_config` sin duración o con franja fin ≤ inicio
- **THEN** la validación falla antes de persistir

### Requirement: Sillón con sede en texto libre (sede única v1.0)

El sistema SHALL persistir sillones con nombre único, `sede` en texto libre
(por defecto sede única, extensible a multi-sede post-TP sin cambio de esquema)
y flag `activo`.

#### Scenario: Sillón demo operativo

- **WHEN** se ejecuta el seed y se lista `sillones activos`
- **THEN** existe al menos un sillón demo con nombre, sede en texto y `activo=true`

### Requirement: Migración 001 reproducible con convenciones Postgres estrictas

El sistema SHALL proveer la migración Alembic `001` que crea las cinco tablas con
PK `BIGINT GENERATED ALWAYS AS IDENTITY`, `TIMESTAMPTZ` para tiempos, `TEXT`+`CHECK`
para strings, `JSONB` para `agenda_config`, FKs con `ON DELETE` explícito e índice
manual por cada FK; y SHALL soportar `upgrade head` y `downgrade -1` limpios.

#### Scenario: Migración sube y baja sin residuos

- **WHEN** se ejecuta `upgrade head`, luego `downgrade -1`, luego `upgrade head`
  contra Postgres real
- **THEN** las tres corridas terminan sin error y las cinco tablas existen al final

#### Scenario: Convenciones de tipos verificables en catálogo

- **WHEN** se inspecciona `information_schema` tras migrar
- **THEN** toda PK es `bigint` con identity, todo tiempo es `timestamptz` y
  ninguna columna usa `serial`, `varchar(n)` ni `timestamp without time zone`

### Requirement: Base repository genérico async

El sistema SHALL exponer un `BaseRepository` async con `get/list/crear/actualizar`
tipados por entidad, del que heredan los repos de Rol, Usuario, Paciente,
Profesional y Sillon, inyectados por dependencias (nunca sesión directa en servicios).

#### Scenario: Repos heredan CRUD sin duplicar lógica

- **WHEN** un servicio lista pacientes y obtiene un sillón por id vía sus repos
- **THEN** ambas operaciones usan la base genérica y retornan entidades tipadas

### Requirement: Seed demo idempotente con datos ficticios

El sistema SHALL proveer un seed que en base limpia crea roles, 1 admin inicial
(desde `SEED_ADMIN_*`), 1 sillón demo y 1 profesional demo; y SHALL ser
idempotente: re-ejecutarlo no duplica filas ni falla en constraints de unicidad.

#### Scenario: Doble ejecución del seed no duplica

- **WHEN** se ejecuta el seed dos veces seguidas contra la misma base
- **THEN** la segunda corrida termina sin error y los conteos de roles, usuarios,
  sillones y profesionales son idénticos a los de la primera
