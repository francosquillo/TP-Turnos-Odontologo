# Proposal — c-05-reserva-online-publica (C-05 `reserva-online-publica`)

> Nota de nombre: el change canónico en `CHANGES.md` es `C-05-reserva-online-publica`.
> El CLI `openspec` exige kebab-case minúsculas, por eso el directorio es
> `openspec/changes/c-05-reserva-online-publica/`. Ambos nombres refieren al mismo change.

## Why

C-04 cerró el GATE 3 parcial staff (turnos con EXCLUDE, máquina de estados,
`disponibilidad` y agenda solo para secretaría/odontólogos con Bearer), pero el
paciente sigue dependiendo del horario de secretaría: no hay reserva 24/7 ni
confirmación en 1 clic. Este change completa la segunda mitad del Flujo 1
(Épica A+B prioritaria, US-002 + US-011): rutas públicas que crean turnos
`pendiente` con token de un solo uso y confirman la agenda sin intervención
(RN-TU-03/RN-TU-04), reutilizando `calcular_huecos` y la máquina de estados de
C-04 sin modificarlos. Es camino crítico (`C-04 → C-05 → C-09 → C-10`) y
desbloquea C-06 (el worker necesita turnos `pendiente|confirmado` de origen
online + el contrato del token ya definido) y el E2E de C-12.

## What Changes

- Rutas públicas (sin Bearer, sin `require_role`): `POST /reservas` (crea turno
  `origen=online` en estado `pendiente` + token opaco un solo uso; crea o
  matchea paciente mínimo nombre+teléfono), `GET /disponibilidad` pública
  (solo lectura, mismo cálculo `horario − turnos` de C-04, sin exponer datos de
  pacientes), `GET /confirmar/:token` (token válido → turno `confirmado`;
  expirado/reusado → `410` + pantalla con teléfono del consultorio).
- Token: 256 bits opacos por URL, en DB solo hash SHA-256 en la columna
  `token_confirmacion_hash` (YA creada nullable en migración 002 de C-04,
  siempre NULL hasta ahora — **este change NO necesita migración para este
  campo**), un solo uso (se invalida al confirmar), expira a los 72 h o al
  `inicio` del turno, lo que ocurra primero (RN-TU-04).
- Confirmación actualiza la agenda sin intervención (RN-TU-03): usa la
  transición `pendiente→confirmado` existente; el turno confirmado participa
  del EXCLUDE exactamente igual que uno de secretaría.
- Colisión concurrente (dos pacientes + secretaría por el mismo hueco) → `409`
  con `alternativas` de huecos próximos, igual que C-04 (la DB sigue siendo la
  autoridad final).
- Frontend: `pages/Reservas` (reemplaza el stub: selector
  profesional/día/hora + formulario mínimo + pantalla éxito con aviso de
  revisar WhatsApp), `pages/Confirmar` (reemplaza el stub: estados
  éxito/expirado/inválido), `GET /` landing pública; manejo `409` hueco
  tomado → re-oferta sin perder los datos del formulario.
- Rate-limit en `POST /reservas` si es trivial con el stack (p. ej. dependencia
  simple en memoria/Redis); si no es trivial, se documenta como deuda para
  C-12 y no bloquea el change.
- Tests TDD contra **Postgres real** (nunca SQLite): reserva crea
  pendiente+token hasheado, confirmar actualiza, reuso → `410`, expirado →
  alternativa de contacto, concurrente → `409`; tiempos con `freezegun`, TZ
  `America/Argentina/Buenos_Aires`.

## Capabilities

### New Capabilities

- `reserva-online-publica`: reserva pública sin login (crear pendiente + token
  un solo uso con expiración 72 h/inicio), confirmación por token que actualiza
  la agenda sin intervención, disponibilidad pública de solo lectura, paciente
  mínimo nombre+teléfono con match por teléfono normalizado, páginas públicas
  reserva/confirmar/landing con manejo de `409`/`410`.

### Modified Capabilities

- `agenda-turnos-core`: `GET /disponibilidad` gana variante pública de solo
  lectura (mismo cálculo, sin Bearer, sin datos de pacientes; la variante staff
  con RBAC no cambia) y la columna `token_confirmacion_hash` —reservada siempre
  NULL en C-04— ahora es escrita por `POST /reservas` e invalidada por
  `GET /confirmar/:token` (sin cambio de DDL).

## Impact

- Archivos nuevos: `backend/app/api/reservas.py` (rutas públicas
  `POST /reservas`, `GET /confirmar/:token`; variante pública de
  disponibilidad), `backend/app/servicios/reserva_servicio.py` (token +
  expiración + match paciente mínimo, delegando huecos/creación/estados a
  `agenda_servicio`), `backend/app/esquemas/reserva.py`
  (`ReservaIn/ReservaOut/ConfirmarOut`, `extra='forbid'`),
  tests `test_c05_*` nuevos.
- Archivos reemplazados: stubs `pages/Reservas.tsx` y `pages/Confirmar.tsx` →
  implementación real; extensión de `App.tsx` (rutas públicas `/`, `/reservas`,
  `/confirmar/:token` fuera del guard de roles) y de `disponibilidad.py` (rama
  pública sin auth junto a la staff existente).
- Sin migración SQL (columna hash ya existe desde C-04); sin breaking changes
  (endpoints staff intactos; la columna pasa de siempre-NULL a escrita solo en
  turnos `origen=online`).
- Desbloquea: C-06 (contrato del token + turnos online para recordatorios),
  C-12 E2E (landing → reserva → confirmar requiere este change) — GATE 3 →
  GATE 4.
- Deuda explícita: sin notificaciones reales (C-06, el "revisá tu WhatsApp" es
  texto hasta que exista el worker), sin lista de espera (C-07), sin validador
  OS pre-turno (C-11); rate-limit queda condicional a trivialidad con el stack.
- Governance **MEDIO** (superficie pública sin auth pero sin PHI ni escritura
  privilegiada): esta propuesta es análisis/diseño solamente, sin implementar
  código todavía; las decisiones sensibles (D-01..D-08 en design) quedan
  marcadas para revisión humana antes del apply.

## Leer antes (fuente de verdad)

- `knowledge-base/03_actores_y_roles.md` — §Rutas públicas (`POST /reservas`,
  `GET /confirmar/:token`, `GET /disponibilidad`, paciente sin cuenta v1.0).
- `knowledge-base/05_reglas_de_negocio.md` — §RN-TU-03 (confirmación actualiza
  agenda), §RN-TU-04 (token un solo uso, 72 h o inicio), §RN-TU-05 (solo huecos
  válidos), §RN-AU-02 (paciente sin cuenta, solo token), §RN-GL-02 (auditoría).
- `knowledge-base/06_funcionalidades.md` — §US-002 (reserva online CA-1/2/3),
  §US-011 (confirmación 1 clic CA-1/2).
- `knowledge-base/07_flujos_principales.md` — §Flujo 1 (reserva + confirmación,
  409 + re-oferta, token expirado → teléfono).
- `backend/app/servicios/agenda_servicio.py` — `calcular_huecos`, `crear_turno`
  (`origen=online` nace `pendiente`), `cambiar_estado`, `sugerir_alternativas`
  (se reutilizan sin cambios).
- `backend/app/api/disponibilidad.py` + `backend/app/modelos/turno.py`
  (`token_confirmacion_hash`, índice parcial ya creado) — se reutilizan.
- `openspec/specs/agenda-turnos-core/spec.md` — máquina de estados, 409 con
  re-oferta, RBAC D-07 (las rutas públicas van SIN `require_role`).
- `CHANGES.md` — fila C-05 (scope, governance MEDIO, dependencia C-04) +
  árbol/GATES (GATE 3 → GATE 4, camino crítico).
- `openspec/config.yaml` — schema spec-driven, reglas proposal/tasks.
