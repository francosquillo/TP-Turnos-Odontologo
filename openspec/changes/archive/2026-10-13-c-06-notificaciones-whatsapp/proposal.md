# Proposal — c-06-notificaciones-whatsapp (C-06 `notificaciones-whatsapp`)

> Nota de nombre: el change canónico en `CHANGES.md` es `C-06-notificaciones-whatsapp`.
> El CLI `openspec` exige kebab-case minúsculas, por eso el directorio es
> `openspec/changes/c-06-notificaciones-whatsapp/`. Ambos nombres refieren al mismo change.

## Why

C-04 cerró el GATE 3 staff (agenda con EXCLUDE, máquina de estados) y C-05
completó el Flujo 1 público (reserva online crea turnos `pendiente` + token de
un solo uso que confirma sin intervención), pero esos turnos
`pendiente|confirmado` hoy no generan ningún aviso: la pantalla de éxito de
C-05 dice "revisá tu WhatsApp" como texto y el token viaja en la respuesta demo.
Sin recordatorios el ausentismo no baja y secretaría sigue confirmando a mano.
Este change implementa el Flujo 2 (Épica B prioritaria, US-010 + US-011):
worker Redis con cron horario que barre turnos a 48/24 h, encola idempotente,
envía por WhatsApp (mock por env para la demo sin creds Meta), registra
estado + costo Meta y expone `POST /webhooks/whatsapp` con firma verificada
para que la respuesta del paciente actualice el turno (RN-NO-01..04, RN-AU-04,
RN-CL-04). Es prerequisite de C-07 (lista de espera reutiliza este canal para
ofertas con expiración 2 h) y cierra el loop C-05→C-06 (la reserva online entra
al barrido; la confirmación por token puede disparar la plantilla
"confirmación").

## What Changes

- Modelo `Notificacion (canal, plantilla, turno_id, estado, costo, payload sin
  PHI)` + migración `003_notificacion` (verificada: la última existente es
  `002_turno`; colisión conocida: `CHANGES.md` asigna también "003" a C-08 —
  el apply resuelve por orden de merge, ver design D-08).
- Plantillas seed (versionadas, extensibles para C-07): recordatorio 48 h,
  recordatorio 24 h, confirmación (post-reserva / post-confirmación),
  hueco liberado (base para ofertas C-07), reseña Google (post-turno).
- Worker Redis + cron horario: cada hora busca turnos `pendiente|confirmado`
  con `inicio` a 48/24 h (±ventana), encola idempotente por clave
  `notif:{turno_id}:{tipo}` (recordatorio_48h / recordatorio_24h), con
  reintentos (backoff) y registro de estado (`encolada|enviada|entregada|
  leída|fallida`) + costo Meta (USD 0,026/ref visible, RN-NO-02).
- `POST /webhooks/whatsapp`: verifica firma Meta con `WHATSAPP_WEBHOOK_SECRET`
  (RN-AU-04); sin firma o firma inválida → `401` + log estructurado (sin PHI).
  Respuesta del paciente ("SI"/"NO"/equivalentes) actualiza el turno vía la
  máquina existente (`pendiente→confirmado`, `pendiente|confirmado→cancelado`
  con motivo `respuesta_paciente`); sin número válido → `Notificacion` en
  `fallida` + aviso a secretaría (marcador consultable, RN-NO-03).
- Modo mock por env (`WHATSAPP_MOCK=true`, ya en `.env.example` desde C-01):
  sin creds Meta el envío se simula (log + estado `enviada`) para que la demo
  local y C-07 funcionen; con `false` exige `WHATSAPP_TOKEN/PHONE_ID/SECRET`
  y pega a la API real. Fallback email/SMS stub si WhatsApp falla o no hay
  número (RN-NO-03): cambia `canal` efectivo, deja traza en la misma
  `Notificacion` (o fila hija según D-05).
- PROHIBIDO PHI en el cuerpo (RN-CL-04/RN-NO-04): plantillas solo con
  nombre de pila + fecha/hora + consultorio; NUNCA diagnóstico, pieza,
  tratamiento, OS ni monto. Test específico que falla si el payload contiene
  patrones clínicos.
- Tests TDD contra **Postgres real + Redis real** (nunca SQLite):
  idempotencia del encolado, firma del webhook, actualización del turno vía
  webhook, fallback, ausencia de PHI en payload; tiempos con `freezegun`, TZ
  `America/Argentina/Buenos_Aires`.

## Capabilities

### New Capabilities

- `notificaciones-whatsapp`: modelo `Notificacion` + migración 003 + seed de
  5 plantillas, worker Redis con barrido horario 48/24 h idempotente con
  reintentos, envío WhatsApp real/mock con costo visible, webhook firmado que
  actualiza turnos, fallback email/SMS stub, garantía sin-PHI testeada,
  plantillas extensibles para las ofertas de C-07.

### Modified Capabilities

- Ninguna capability existente cambia su contrato. `agenda-turnos-core` y
  `reserva-online-publica` se REUTILIZAN sin DDL ni endpoints modificados: el
  worker solo LEE turnos `pendiente|confirmado` y escribe transiciones ya
  permitidas vía `cambiar_estado`; `GET /confirmar/:token` de C-05 puede
  encolar la plantilla "confirmación" como efecto lateral (aditivo, sin
  cambiar su `200/404/410`). No se genera delta spec para capabilities
  existentes.

## Impact

- Archivos nuevos: `backend/app/modelos/notificacion.py` (modelo + catálogos
  `canal/plantilla/estado` con CHECK), `backend/alembic/versions/
  003_notificacion.py`, `backend/app/servicios/notificacion_servicio.py`
  (barrido, idempotencia, plantillas, costo), `backend/app/servicios/
  whatsapp_cliente.py` (real/mock + fallback stub),
  `backend/app/api/webhooks.py` (`POST /webhooks/whatsapp` sin Bearer, con
  verificación de firma), `backend/app/esquemas/notificacion.py` + `webhook.py`
  (`extra='forbid'`), `backend/app/worker/notif_jobs.py` (barrido + envío +
  reintentos; `worker/main.py` del stub C-01 evoluciona a scheduler, no se
  reemplaza la imagen), seed `backend/app/core/seed_plantillas.py`,
  tests `test_c06_*`.
- Archivos extendidos (sin breaking): `worker/main.py` (suma loop cron
  horario junto al heartbeat), `.env.example` (documenta `WHATSAPP_MOCK`
  ya existente + costo ref), router `main.py` (monta `/webhooks`).
- Sin cambios a `turno`, EXCLUDE, máquina de estados, endpoints staff o
  públicos de C-04/C-05 (el webhook usa `cambiar_estado`, no SQL directo).
- Desbloquea: C-07 (ofertas usan `Notificacion` + mock + plantilla
  `hueco_liberado` extensible a `oferta_lista_espera`), C-12 E2E (flujo
  reserva → recordatorio → asistencia queda demostrable en mock).
- Deuda explícita: envío real solo con creds Meta (demo = mock); fallback
  email/SMS es stub trazado (sin SMTP real hasta que se decida proveedor);
  reseña Google es link/redirect (sin API de escritura, igual que C-12);
  Google Calendar fuera de scope (C-12).
- Governance **ALTO** (secretos, firma de webhook, prohibición PHI): esta
  propuesta es análisis/diseño solamente, sin implementar código todavía; las
  decisiones sensibles (D-01..D-08 en design) quedan marcadas para revisión
  humana antes del apply.

## Leer antes (fuente de verdad)

- `knowledge-base/04_modelo_de_datos.md` — §Notificacion (canal, plantilla,
  turno_id, estado, costo, payload sin PHI) + §Seed (5 plantillas).
- `knowledge-base/05_reglas_de_negocio.md` — §RN-NO-01 (48/24 h solo
  pendiente|confirmado), §RN-NO-02 (estado + costo), §RN-NO-03 (fallback),
  §RN-NO-04 (sin clínicos), §RN-AU-04 (firma Meta), §RN-CL-04 (sin PHI plano),
  §RN-TU-03 (respuesta actualiza turno), §RN-GL-02 (auditoría).
- `knowledge-base/06_funcionalidades.md` — §US-010 (recordatorios CA-1/2/3),
  §US-011 (confirmación 1 clic, el webhook es su vía WhatsApp).
- `knowledge-base/07_flujos_principales.md` — §Flujo 2 (cron → encola
  idempotente → envía → registra → webhook actualiza; errores: sin número →
  fallida + aviso, sin firma → 401 + log).
- `knowledge-base/08_arquitectura_propuesta.md` — §Worker + cola (jobs no
  bloquean requests, reintentos), §Variables (`WHATSAPP_*`, `REDIS_URL`, `TZ`),
  §Seguridad (secretos solo env, sin PHI en mensajería).
- `backend/app/worker/main.py` — stub C-01 (heartbeat; C-06 lo extiende con
  `notif_jobs.py`, decisión D-04).
- `backend/app/modelos/turno.py` — origen `online/pendiente` de C-04/C-05
  (el barrido los consume sin modificarlos), `backend/app/core/config.py` +
  `.env.example` (`WHATSAPP_*` ya definidos, `WHATSAPP_MOCK=true`).
- `openspec/specs/` — capabilities C-04/C-05 (máquina de estados y token que
  se reutilizan; sin delta sobre ellas).
- `CHANGES.md` — fila C-06 (scope, governance ALTO, dependencia C-04) +
  árbol/GATES (GATE 3 → GATE 5: C-06 habilita C-07).
- `openspec/config.yaml` — schema spec-driven, reglas proposal/tasks.
