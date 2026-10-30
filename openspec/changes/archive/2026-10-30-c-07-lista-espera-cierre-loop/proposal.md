# Proposal — c-07-lista-espera-cierre-loop (C-07 `lista-espera-cierre-loop`)

> Nota de nombre: el change canónico en `CHANGES.md` es `C-07-lista-espera-cierre-loop`.
> El CLI `openspec` exige kebab-case minúsculas, por eso el directorio es
> `openspec/changes/c-07-lista-espera-cierre-loop/`. Ambos nombres refieren al mismo change.

## Why

C-04 cerró el GATE 3 staff (agenda con EXCLUDE, máquina de estados), C-05
completó el Flujo 1 público (reserva online) y C-06 archivó el GATE 5
(worker Redis, canal WhatsApp mock/real, webhook firmado, plantilla
`oferta_lista_espera` ya reservada en el CHECK). Pero cuando un turno se
cancela — por secretaría (`PATCH /turnos/:id/estado`) o por el paciente
(webhook C-06 evento NO → `cancelado`) — el hueco liberado hoy solo vuelve a
la disponibilidad pública: nadie avisa a los pacientes que esperan, y la
cola de espera no existe en ningún lado. Este change implementa el Flujo 6
(Épica B diferenciador, US-012): modelo `EsperaEntry`, oferta al primero
compatible con expiración de **2 h** (RN-TU-06, decisión 2026-10-05),
cascada al siguiente si rechaza/expira, conversión a turno `confirmado`, y
hueco libre a agenda pública si nadie acepta. Reutiliza C-06 para el aviso
(oferta con link token; en mock, aviso simulado + UI secretaría) y C-04/C-05
para la creación de turnos (patrón componer-no-modificar: `agenda_servicio`
y `reserva_servicio` intactos).

## What Changes

- Modelo `EsperaEntry (paciente_id, profesional_id nullable, especialidad
  nullable, preferencia_horaria JSONB nullable, estado
  activa|ofrecida|convertida|vencida, oferta_expira_en nullable,
  token_oferta_hash nullable)` + migración `004_espera` (verificada: el head
  actual es `003_notificacion`; `backend/alembic/versions/` contiene solo
  `001, 002, 003` — C-08 no tomó `004` entretanto).
- Compatibilidad FIFO: primera `activa` cuyo `profesional_id` (si fijado)
  coincide, cuya `especialidad` (si fijada) está en las especialidades del
  profesional, y cuya `preferencia_horaria` (si fijada) cubre el inicio del
  hueco; orden `created_at ASC`.
- Endpoints staff (`require_role(secretaria|admin)`): `CRUD /lista-espera`,
  `POST /lista-espera/:id/ofrecer` (disparo manual), `POST
  /lista-espera/:id/convertir` (paciente aceptó por teléfono/presencial).
  Endpoints públicos con token (sin Bearer, patrón hash C-05): `POST
  /lista-espera/aceptar/:token`, `POST /lista-espera/rechazar/:token`.
- Servicio `lista_espera_servicio` (nuevo, compone sin modificar):
  `intentar_ofrecer(hueco)` invocado desde la capa API **después** de
  `cambiar_estado→cancelado` (router turnos + webhook NO de C-06);
  `agenda_servicio` y `reserva_servicio` no cambian firma ni conducta.
- Oferta con expiración **2 h** (`oferta_expira_en = ahora + 2 h`,
  `freezegun` en tests, TZ `America/Argentina/Buenos_Aires`): rechaza/expira
  → `vencida` + cascada inmediata al siguiente; nadie acepta (cola vacía o
  todas vencidas) → hueco queda libre en disponibilidad pública.
- Aviso vía C-06: fila `Notificacion` plantilla `oferta_lista_espera`
  (CHECK de C-06 ya la admite — solo fila seed `v1`, **sin migrar**) con
  `{nombre_pila, fecha, hora, expira_en, link_oferta}`; envío por
  `whatsapp_cliente` (mock OK para demo); sin-PHI por construcción (mismo
  escáner C-06). Sin número válido → `fallida` + la oferta sigue visible en
  UI secretaría (puede convertir por teléfono).
- Conversión: aceptar (token válido, no expirado, entry `ofrecida`) crea
  turno vía `agenda.crear_turno(origen="lista_espera")` +
  `cambiar_estado→confirmado` (US-012 CA-3; `crear_turno` solo mapea
  `secretaria→confirmado`, por eso son dos pasos con funciones existentes);
  `UNIQUE`/sobreturno NO aplican a la oferta (convierte a turno normal;
  si el hueco se tomó entretanto → `409` + oferta a `vencida` + cascada).
- Worker: nuevo `worker/espera_jobs.py` (barrido cada 10 min de `ofrecidas`
  vencidas → `vencida` + cascada; lock Redis anti-doble-cascada) que
  extiende `worker/main.py` como hizo C-06 (sin servicio compose nuevo).
- Frontend `features/lista-espera` (staff): cola ordenada FIFO, botón
  ofrecer, countdown vivo 2 h, botones convertir / dar de baja; TS estricto
  sin `any`.
- Tests TDD contra **Postgres real + Redis real** (nunca SQLite):
  oferta al primero FIFO, expiración 2 h, cascada, conversión crea
  `confirmado` con `origen=lista_espera`, hueco liberado si nadie acepta,
  token reuso → `410` / desconocido → `404` / expirado → `410`.

## Capabilities

### New Capabilities

- `lista-espera-cierre-loop`: modelo `EsperaEntry` + migración 004 +
  matching FIFO compatible, servicio de oferta con expiración 2 h y cascada,
  token de oferta un solo uso (hash, expira 2 h), conversión a turno
  `confirmado` `origen=lista_espera`, aviso por canal C-06 (plantilla
  `oferta_lista_espera` seed `v1`), worker de vencimientos, UI secretaría
  con countdown, garantía sin-PHI heredada.

### Modified Capabilities

- Ninguna capability existente cambia su contrato. `agenda-turnos-core`,
  `reserva-online-publica` y `notificaciones-whatsapp` se REUTILIZAN sin DDL
  ni endpoints modificados: el hook de cancelación es una llamada aditiva en
  la capa API (router turnos + webhook C-06) hacia el servicio nuevo; el
  worker suma un job junto a los existentes; la plantilla nueva es fila seed
  (el CHECK ya la contempla). No se genera delta spec para capabilities
  existentes.

## Impact

- Archivos nuevos: `backend/app/modelos/espera_entry.py` (modelo + CHECKs +
  índices), `backend/alembic/versions/004_espera.py`,
  `backend/app/servicios/lista_espera_servicio.py` (matching, oferta,
  expiración, conversión, tokens), `backend/app/api/lista_espera.py`
  (`CRUD + ofrecer/convertir` staff, `aceptar/rechazar/:token` públicos),
  `backend/app/esquemas/lista_espera.py` (`extra='forbid'`),
  `backend/app/repos/espera_repo.py`, `backend/app/worker/espera_jobs.py`,
  `frontend/src/features/lista-espera/*`, tests `test_c07_*`.
- Archivos extendidos (sin breaking): `api/turnos.py` (tras
  `cambiar_estado→cancelado`, llamada aditiva a `intentar_ofrecer`),
  `api/webhooks.py` (tras NO→`cancelado`, misma llamada),
  `worker/main.py` (suma `bucle_espera(600s)`), `core/seed_plantillas.py`
  (+ fila `oferta_lista_espera v1`), router `main.py` (monta `/lista-espera`).
- Sin cambios a `agenda_servicio`, `reserva_servicio`,
  `notificacion_servicio`, `whatsapp_cliente`, máquina de estados, EXCLUDE
  ni contratos C-04/C-05/C-06.
- Desbloquea: nada pendiente (C-07 es hoja del árbol; GATE 6 sigue con
  C-09/C-10/C-11 en paralelo). Recorte explícito si atrasa: C-07 es el
  primero en recortarse (CHANGES.md) — este diseño lo mantiene aislado para
  que recortarlo no arrastre deuda.
- Deuda explícita: oferta no bloqueante (el hueco sigue público durante la
  ventana 2 h; la aceptación compite y EXCLUDE arbitra — ver D-03); una sola
  oferta sobresaliente por entry (sin ofertas paralelas al mismo paciente);
  matching por especialidad es `contains` simple (sin ranking de cercanía
  horaria fina); countdown frontend por polling (sin websocket).
- Governance **MEDIO**: esta propuesta es análisis/diseño solamente, sin
  implementar código todavía; las decisiones (D-01..D-08 en design) siguen el
  patrón componer-no-modificar de C-05/C-06.

## Leer antes (fuente de verdad)

- `knowledge-base/04_modelo_de_datos.md` — §EsperaEntry (paciente,
  profesional/especialidad, preferencia, estados, flujo hueco→primero→reserva).
- `knowledge-base/05_reglas_de_negocio.md` — §RN-TU-06 (oferta al primero,
  ventana 2 h, cascada), §RN-TU-01/02 (EXCLUDE arbitra la aceptación;
  sobreturno NO aplica), §RN-TU-03 (conversión a `confirmado`), §RN-NO-04 +
  §RN-CL-04 (sin PHI en el aviso).
- `knowledge-base/06_funcionalidades.md` — §US-012 (CA-1 oferta 2 h, CA-2
  cascada, CA-3 conversión a `confirmado`).
- `knowledge-base/07_flujos_principales.md` — §Flujo 6 (cancelación → primero
  → acepta/rechaza-expira → siguiente; nadie → hueco libre).
- `backend/app/servicios/agenda_servicio.py` — `crear_turno`,
  `cambiar_estado` (se reutilizan; NO se modifican; `origen=lista_espera` ya
  está en el CHECK `ck_turno_origen_catalogo`).
- `backend/app/servicios/reserva_servicio.py` — patrón token opaco + hash
  SHA-256 + un solo uso (D-04 lo replica para la oferta).
- `backend/app/servicios/notificacion_servicio.py` +
  `backend/app/modelos/notificacion.py` (`PLANTILLAS` y CHECK ya incluyen
  `oferta_lista_espera`; solo falta la fila seed — D-07) +
  `backend/app/core/seed_plantillas.py` (upsert `nombre+version`, render con
  variables declaradas, escáner sin-PHI).
- `backend/app/api/turnos.py` (`PATCH /turnos/:id/estado` — punto de enganche
  D-02) + `backend/app/api/webhooks.py` (evento NO→`cancelado` — segundo
  punto de enganche) + `backend/app/worker/main.py` (patrón de extensión
  C-06, D-04 de C-06).
- `openspec/specs/` — capabilities C-04/C-05/C-06 (máquina, token, canal que
  se reutilizan; sin delta sobre ellas).
- `CHANGES.md` — fila C-07 (scope, governance MEDIO, dependencias C-04 +
  C-06) + GATES (GATE 5 ✓ abre C-07).
- `openspec/config.yaml` — schema spec-driven, reglas proposal/tasks.
