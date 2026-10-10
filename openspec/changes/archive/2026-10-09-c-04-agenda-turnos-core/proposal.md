# Proposal — c-04-agenda-turnos-core (C-04 `agenda-turnos-core`)

> Nota de nombre: el change canónico en `CHANGES.md` es `C-04-agenda-turnos-core`.
> El CLI `openspec` exige kebab-case minúsculas, por eso el directorio es
> `openspec/changes/c-04-agenda-turnos-core/`. Ambos nombres refieren al mismo change.

## Why

C-03 cerró el GATE 2 (JWT + RBAC + `require_role(...)` verificados contra PG/Redis
reales) pero la agenda sigue siendo un stub (`GET /turnos` responde
`{"recurso": "turnos", "status": "stub C-01"}`): no existe tabla `turno`, no hay
anti-solapamiento a nivel DB (DD-03) y la secretaría no puede operar el día sin
papel. Este change crea el núcleo evaluable del TP (Épica A prioritaria,
US-001 + US-003, Flujo 1 parcial staff): turnos persistidos con choque imposible
por profesional y por sillón, estados con máquina explícita, disponibilidad y
agenda por vistas, y UI `features/agenda` día/semana/mes. Es el GATE 3 del
roadmap: desbloquea C-05 (reserva pública + token), C-06 (recordatorios),
C-07 (lista de espera), C-09 (presupuesto/CC) y C-11 (liquidación).

## What Changes

- Modelo `Turno (paciente_id, profesional_id, sillon_id, inicio, fin, estado,
  origen, token_confirmacion_hash nullable, sobre_turno bool + motivo)` y
  migración 002: tabla `turno` + doble constraint
  `EXCLUDE USING gist (profesional WITH =, tstzrange WITH &&)` e ídem sillón,
  parciales a turnos activos no-sobreturno; sobreturno solo con
  `sobre_turno=true + motivo` auditado (quién/qué/cuándo).
- Endpoints protegidos con `require_role` (C-03): `CRUD /turnos`
  (crear exige `fin > inicio`, FKs existentes, sin solapamiento),
  `PATCH /turnos/:id/estado` (transiciones de la máquina + motivo obligatorio al
  cancelar), `GET /disponibilidad?profesional_id&desde&hasta[&sillon_id&duracion_min]`
  (huecos = horario semanal de `agenda_config` − turnos activos, respeta
  RN-TU-01 + RN-TU-05) y `GET /agenda?vista=dia|semana|mes&profesional_id&sillon_id&fecha`
  (agregación para las vistas).
- Servicio agenda (`servicios/agenda_servicio.py`): cálculo de huecos, creación /
  reprogramación con revalidación de solapamiento, cancelación con motivo;
  colisión concurrente (carrera reserva online + secretaría) → `409` con re-oferta
  de huecos alternativos (Flujo 1).
- Columna `token_confirmacion_hash` nullable creada ahora (hash SHA-256, nunca el
  token plano) pero **sin endpoints de confirmación**: el flujo token un solo uso
  con expiración 72 h es C-05 (RN-TU-04); acá solo queda la columna reservada y
  documentada para no requerir migración en C-05.
- Frontend `features/agenda`: vistas día/semana/mes, colores por estado
  (`pendiente|confirmado|asistido|ausente|cancelado`), crear/editar, drag para
  reprogramar (ante `409` muestra re-oferta), cancelación con modal de motivo.
- Tests TDD contra **Postgres real** (nunca SQLite — SQLite no soporta
  EXCLUDE/GiST): anti-solapamiento concurrente por profesional y por sillón,
  sobreturno auditado, máquina de estados, disponibilidad = horario − turnos,
  reprogramación y cancelación; tiempos con `freezegun`, TZ
  `America/Argentina/Buenos_Aires`.

## Capabilities

### New Capabilities

- `agenda-turnos-core`: modelo Turno + EXCLUDE anti-solapamiento, CRUD y máquina
  de estados, disponibilidad y agenda por vistas, servicio de huecos,
  sobreturno auditado y UI agenda día/semana/mes.

### Modified Capabilities

(none — `core-models-identidad-pacientes` y `auth-rbac` no cambian
comportamiento: se reutilizan `Profesional.agenda_config`, `Paciente`, `Sillon`
y `require_role(...)` tal cual; `foundation-setup` tampoco cambia.)

## Impact

- Archivos nuevos: `backend/app/modelos/turno.py`,
  `backend/alembic/versions/002_turno.py` (o ruta de migraciones del repo),
  `backend/app/repos/turno_repo.py`, `backend/app/servicios/agenda_servicio.py`,
  `backend/app/esquemas/turno.py` (`TurnoIn/TurnoOut/EstadoPatch/DisponibilidadOut`,
  `extra='forbid'`), `backend/app/api/turnos.py` (real, reemplaza el stub),
  `backend/app/api/disponibilidad.py` + `agenda.py` (o sub-routers),
  `frontend/src/features/agenda/*` (vistas + drag + colores),
  tests `test_c04_*` nuevos.
- Archivos reemplazados: router stub `turnos.py` → implementación real; extensión
  de `App.tsx` (ruta agenda + guards por rol).
- Sin breaking changes (el stub no tenía consumidores; la columna token reservada
  no expone comportamiento hasta C-05).
- Desbloquea: C-05 (token + reserva pública sobre `disponibilidad` y columna hash
  ya creada), C-06 (turnos `pendiente|confirmado` para recordatorios), C-07
  (cancelación libera hueco → oferta), C-09/C-11 (turno como prestación facturable)
  — GATE 2 → GATE 3 (fork C-04/C-08/C-12; C-04 es el prioritario del Agente A).
- Deuda explícita: sin notificaciones (C-06), sin lista de espera (C-07), sin
  sincronización Google Calendar (C-12 stub con flag), sin validador OS pre-turno
  (C-11); paginación de agenda acotada a vistas día/semana/mes (sin scroll
  infinito).
- Governance **CRITICO** (núcleo del TP + constraints de concurrencia): esta
  propuesta es análisis/diseño solamente, sin implementar código todavía; las
  decisiones sensibles (D-01..D-08 en design) quedan marcadas para revisión
  humana antes del apply.

## Leer antes (fuente de verdad)

- `knowledge-base/04_modelo_de_datos.md` — §Turno (atributos, EXCLUDE, índices),
  §Profesional (`agenda_config`), §Sillon (sede única texto).
- `knowledge-base/05_reglas_de_negocio.md` — §RN-TU-01 (choque imposible DB),
  §RN-TU-02 (sobreturno flag + motivo), §RN-TU-03 (estados + confirmación),
  §RN-TU-05 (huecos dentro de horario), §RN-GL-02 (auditoría), §RN-GL-01 (sin
  borrado físico).
- `knowledge-base/06_funcionalidades.md` — §US-001 (agenda multi-profesional,
  CA-1/2/3), §US-003 (reprogramar/cancelar, CA-1/2).
- `knowledge-base/07_flujos_principales.md` — §Flujo 1 (reserva + 409 + re-oferta).
- `knowledge-base/09_decisiones_y_supuestos.md` — §DD-03 (EXCLUDE, btree_gist,
  tests PG real).
- `openspec/specs/core-models-identidad-pacientes/spec.md` — `agenda_config`,
  FK rol simple (se reutiliza, no se modifica).
- `openspec/specs/auth-rbac/spec.md` — `require_role(...)` y matriz 03
  (se reutiliza para proteger `/turnos`, `/disponibilidad`, `/agenda`).
- `CHANGES.md` — fila C-04 (scope, governance CRITICO, dependencias C-02 + C-03)
  + árbol/GATES (GATE 2 → GATE 3).
- `openspec/config.yaml` — schema spec-driven, reglas proposal/tasks.
