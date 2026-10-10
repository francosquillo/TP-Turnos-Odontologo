# Design — c-04-agenda-turnos-core

## Context

Ver `proposal.md` (Why). Estado actual: C-02 archivado (modelos
`Paciente/Profesional(con agenda_config JSONB)/Sillon(sede texto)/Rol/Usuario`,
repos genéricos, seed demo), C-03 archivado (`require_role(...)`, JWT 30 min,
matriz 03, superficie admin mínima). Router `turnos` es stub C-01 y no existe
tabla `turno`. Restricciones vinculantes: doble EXCLUDE profesional+sillón
(RN-TU-01, DD-03, `btree_gist` ya habilitado en C-01), sobreturno solo con flag
+ motivo auditado (RN-TU-02 + RN-GL-02), Pydantic `extra='forbid'`,
`Annotated[..., Depends(...)]` para auth/DB, `async def` solo si todo adentro
es async no bloqueante, TS estricto sin `any`, tests de constraints contra
Postgres real (nunca SQLite), `freezegun` para tiempos, TZ
`America/Argentina/Buenos_Aires`, sede única, datos 100% ficticios.

## Goals / Non-Goals

**Goals:**

- Choque imposible garantizado por DB para profesional y sillón, con
  sobreturno explícito que no rompe la invariante.
- Máquina de estados cerrada con transiciones testeables y cancelación motivada.
- Disponibilidad calculada como horario semanal − turnos activos, reutilizable
  por C-05 sin cambios.
- Colisión concurrente degradada a `409` + re-oferta (Flujo 1), nunca a doble
  reserva silenciosa.
- Tasks listas para TDD estricto en apply (RED primero, verificación por task).

**Non-Goals:**

- Flujo token de confirmación un solo uso + expiración 72 h (C-05; acá solo la
  columna hash reservada, ver D-05).
- Recordatorios/notificaciones (C-06), lista de espera y cascada 2 h (C-07),
  validador OS pre-turno (C-11), Google Calendar sync (C-12).
- Multi-sede, pagos, AFIP (fuera de v1.0 por reglas duras).
- Borrado físico de turnos (RN-GL-01: no hay `DELETE` de negocio; la cancelación
  es cambio de estado).

## Decisions

### D-01 — Doble EXCLUDE parcial: solo turnos activos no-sobreturno participan

```sql
ALTER TABLE turno ADD CONSTRAINT ex_turno_prof_sin_solape
EXCLUDE USING gist (profesional_id WITH =, tstzrange(inicio, fin) WITH &&)
WHERE (sobre_turno IS FALSE AND estado IN ('pendiente','confirmado','asistido'));
ALTER TABLE turno ADD CONSTRAINT ex_turno_sillon_sin_solape
EXCLUDE USING gist (sillon_id WITH =, tstzrange(inicio, fin) WITH &&)
WHERE (sobre_turno IS FALSE AND estado IN ('pendiente','confirmado','asistido'));
```

Requiere `btree_gist` (ya habilitado en C-01 para el `WITH =` sobre bigint) y
rango `tstzrange(inicio, fin)` con `fin > inicio` (CHECK adicional). El predicado
`WHERE` parcial es la pieza clave: `cancelado` y `ausente` liberan el hueco
(el paciente no ocupará el sillón) y `sobre_turno=true` no participa del
constraint — el sobreturno existe *a pesar* del solapamiento, no *rompiendo* la
regla. La app además pre-valida (para devolver `409` con re-oferta en vez del
`500` del constraint) pero la DB es la autoridad final ante carreras.
Alternativas descartadas: (a) solo validación en app — pierde ante
reserva-online + secretaría concurrentes (DD-03 lo prohíbe); (b) EXCLUDE total
sin `WHERE` — bloquearía sobreturnos legítimos y obligaría a borrar/cancelar
físicamente para liberar huecos, violando RN-GL-01; (c) trigger en vez de
EXCLUDE — más código, menos declarativo, peor bajo concurrencia (no usa
predicados GiST). Índices complementarios: `(profesional_id, inicio)`,
`(sillon_id, inicio)`, `estado`, hash de token.
Revisión humana: confirmar que el equipo acepta que `ausente` libere hueco
(turno pasado, sin efecto futuro real) vs conservarlo bloqueante.
Skills: `postgresql-table-design`, `supabase-postgres-best-practices`.

### D-02 — Sobreturno = flag + motivo obligatorio + auditoría, nunca constraint roto

Crear o reprogramar con solapamiento solo procede si el body trae
`sobre_turno=true` **y** `motivo_sobreturno` no vacío (≥ 5 caracteres); el
servicio registra `motivo_sobreturno`, `creado_por (usuario_id del JWT)`,
`created_at` y lo expone en `TurnoOut` para auditoría (RN-TU-02 + RN-GL-02:
quién/qué/cuándo). Sin flag o sin motivo ante solapamiento → `409`. El sobreturno
pasa el EXCLUDE por el predicado parcial (D-01), no por excepción de código.
Alternativa (tabla `sobreturno` separada) descartada: duplica el modelo de
agenda y complica `disponibilidad`/`agenda` (tendrían que unir dos tablas);
el flag + predicado mantiene una sola tabla y una sola lectura.
Skill: `fastapi` (esquemas estrictos).

### D-03 — Máquina de estados cerrada con transiciones explícitas

Estados: `pendiente → confirmado → asistido` (flujo feliz),
`pendiente|confirmado → cancelado` (con motivo obligatorio),
`confirmado → ausente` (solo pasado el `fin`, o marca manual de secretaría),
`cancelado|ausente|asistido` terminales (sin salida). `PATCH /turnos/:id/estado`
valida transición; transición ilegal → `422`. Reglas: `fin > inicio` siempre;
`inicio` en pasado solo para carga histórica por `admin` (si el equipo lo
rechaza, prohibir pasado salvo `asistido/ausente` — ver Open Questions);
`cancelado` exige `motivo_cancelacion`; reprogramar (`PATCH inicio/fin` o
`PUT`) revalida solapamiento como creación (D-06). Sin `DELETE` de negocio
(RN-GL-01). Alternativa (estados libres por string) descartada: permite
`pendiente → asistido` sin confirmar y `asistido → pendiente`, rompiendo
RN-TU-03 y los conteos de C-06/C-07.
Skills: `fastapi`, `python-testing-patterns` (tabla de transiciones como test
parametrizado).

### D-04 — Disponibilidad = horario semanal de `agenda_config` − turnos activos

`Profesional.agenda_config` (JSONB, C-02) es la fuente del horario:
`{"slots": [{"dia": 0-6, "desde": "08:00", "hasta": "12:00", "duracion_min": 30}], "excepciones": [...]}`.
El servicio genera slots candidatos en `[desde, hasta)` (TZ
`America/Argentina/Buenos_Aires`, siempre `timestamptz`), resta los rangos
ocupados por turnos activos no-sobreturno del profesional (y del sillón si se
pide `sillon_id`), y devuelve huecos `{inicio, fin}` ofrecibles. Sin
`agenda_config` o día fuera de horario → lista vacía (RN-TU-05), nunca huecos
inventados. `duracion_min` default del slot; query param puede pedir otra
duración (re-slicea). C-05 reutiliza este servicio tal cual para la reserva
pública. Alternativa (tabla `horario` normalizada) descartada: C-02 ya fijó
JSONB con índice GIN; migrar a tabla rompe el seed y el contrato C-02.
Skill: `fastapi`.

### D-05 — Columna token reservada ahora, flujo token en C-05

Migración 002 crea `token_confirmacion_hash TEXT NULLABLE` (SHA-256 hex del
token, nunca el plano) + índice parcial `WHERE token_confirmacion_hash IS NOT
NULL`. En C-04 la columna siempre se escribe `NULL` (crear/reprogramar no la
tocan; el esquema la expone solo lectura opaca o la omite). El flujo
token-un-solo-uso + expiración 72 h + `GET /confirmar/:token` es C-05 entero
(RN-TU-04). Motivo: evitar una migración 003 que solo agregue una columna;
C-05 queda en SQL cero para este campo. Alternativa (crear la columna en C-05)
descartada: partiría la revisión del modelo Turno en dos changes y el spec de
este change quedaría incompleto respecto a `04_modelo_de_datos.md` §Turno.

### D-06 — Reprogramar revalida como creación; colisión → 409 + re-oferta

Reprogramar es `PATCH /turnos/:id {inicio, fin}` (o drag en UI → mismo endpoint);
el servicio excluye el propio turno del chequeo, valida horario + solapamiento
(igual que crear, incluyendo vía sobreturno con motivo) y el `UPDATE` queda
sujeto al EXCLUDE (la DB decide la carrera). Ante `ExclusionViolation` (o
pre-chequeo positivo) la API responde `409 {"detail": "hueco ocupado",
"alternativas": [...]}` con 3 huecos próximos del mismo profesional (Flujo 1:
re-oferta). La UI ante `409` mantiene el turno en su horario original y ofrece
las alternativas (nunca lo deja flotante). Alternativa (bloqueo pesimista
`SELECT FOR UPDATE` del rango) descartada: no escala a reserva pública y el
EXCLUDE ya serializa correctamente con menos código.

### D-07 — RBAC: escritura staff, lectura staff; público en C-05

Matriz aplicada en este change (sobre `require_role` de C-03): `CRUD /turnos`,
`PATCH estado`, `GET /disponibilidad`, `GET /agenda` → `admin|secretaria`
completo; `odontologo` lectura de agenda/disponibilidad + `PATCH estado` de sus
propios turnos (marcar `asistido/ausente`) pero sin crear/cancelar ajenos (la
cancelación con motivo es tarea de secretaría, US-003); sin Bearer → `401`,
rol insuficiente → `403`. Las variantes públicas de `disponibilidad` y
`POST /reservas` son C-05 (sin Bearer). Alternativa (odontólogo con escritura
total) descartada: contradice US-001/US-003 (secretaría opera la agenda) y
amplía la superficie de sobreturnos fuera de control.

### D-08 — Frontend agenda mínima operable: 3 vistas + colores + drag con rollback

`features/agenda/`: vista día (columna por profesional/sillón), semana (grilla),
mes (resumen con conteo); color por estado (pendiente ámbar, confirmado azul,
asistido verde, ausente gris, cancelado rojo tenue/tachado); crear (click en
hueco libre → formulario mínimo paciente+profesional+sillón+inicio/fin),
reprogramar por drag (optimista con rollback ante `409` + panel de alternativas),
cancelar con modal de motivo obligatorio. Estado con `fetchConAuth` (C-03),
tipado estricto sin `any`, componentes PascalCase. Sin virtualización ni
scroll infinito en v1.0 del change (día/semana/mes acotados). Skill:
`vercel-react-best-practices` (aplicar bundle/waterfall/rerender; ignorar
RSC/`next/dynamic` — proyecto Vite SPA).

## Risks / Trade-offs

- [EXCLUDE parcial con `WHERE` no bloquea lo que no ve] → Mitigación: el
  pre-chequeo de app cubre mensajes (`409` + re-oferta) y los tests de
  concurrencia (tasks 2.x) prueban la carrera real contra PG; validar con
  `openspec validate --strict` que el DDL propuesto es el implementado.
- [Rangos `tstzrange` y DST de `America/Argentina/Buenos_Aires`] → Mitigación:
  todo en `timestamptz` UTC en DB, conversión solo en bordes (esquemas/UI);
  `freezegun` + casos borde DST en tests (Argentina sin DST desde 2009, riesgo
  bajo pero testeado).
- [`agenda_config` JSONB heterogéneo del seed] → Mitigación: esquema de lectura
  tolerante (valores por defecto + validación Pydantic del config) y task que
  fija el formato demo; C-05 no lo reinterpreta.
- [Drag optimista deja la UI inconsistente ante `409`] → Mitigación: rollback
  obligatorio al horario original + alternativas servidas por la API (D-06);
  test frontend de este camino (task 5.2).
- [Doble EXCLUDE duplica el costo de escritura] → Mitigación: \(O(\log n)\) GiST
  por índice, aceptable para agenda humana; sin particionado en v1.0.
- [Sobreturno abusado como vía para saltarse la regla] → Mitigación: motivo
  obligatorio + auditoría visible (RN-GL-02) + RBAC (solo staff); C-12 puede
  añadir reporte de sobreturnos si la facultad lo pide.

## Migration Plan

1. Mergear solo artefactos openspec (este change: sin código).
2. Apply (TDD): migración 002 en PG real → modelo + repos → esquemas estrictos →
   `agenda_servicio` (huecos) → routers protegidos → frontend → suite verde
   (`pytest backend/app/tests` + checks frontend, PG real, nunca SQLite).
3. Rollback: `alembic downgrade -1` revierte tabla + constraints; sin datos
   productivos (todo ficticio); la columna token reservada se va con la tabla.
4. `openspec validate --change c-04-agenda-turnos-core --strict` antes de archivar;
   archivar marca `[x]` C-04 en `CHANGES.md` y abre GATE 3 (C-05/C-06/C-08).

## Open Questions

(none — la única duda real, si `ausente` libera hueco y si se permite crear en
pasado no-admin, quedó como criterio explícito en D-01/D-03 con revisión humana
marcada; no bloquea specs ni tasks.)
