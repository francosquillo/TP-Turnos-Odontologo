# Design — c-06-notificaciones-whatsapp

## Context

Ver `proposal.md` (Why). Estado actual: C-04 archivado (tabla `turno` con doble
EXCLUDE parcial, servicio `agenda_servicio` con `calcular_huecos`/
`crear_turno`/`cambiar_estado`, estados
`pendiente|confirmado|asistido|ausente|cancelado`), C-05 archivado (rutas
públicas `POST /reservas` → turno `origen=online` `pendiente` + token opaco,
`GET /confirmar/:token` → `confirmado`; pantalla de éxito con aviso WhatsApp
solo como texto). Worker: stub C-01 (`backend/app/worker/main.py` con
heartbeat, sin jobs; el comentario dice "jobs reales en C-06"). Env:
`WHATSAPP_TOKEN/PHONE_ID/WEBHOOK_SECRET` + `WHATSAPP_MOCK=true` ya en
`.env.example` y `core/config.py`; última migración existente
`002_turno.py`. Restricciones vinculantes: Pydantic `extra='forbid'`,
`Annotated[..., Depends(...)]` para auth/DB, `async def` solo si todo adentro
es async no bloqueante, TS estricto sin `any` (este change casi no toca
frontend), tests contra Postgres + Redis reales (nunca SQLite), `freezegun`
para tiempos (ventanas 48/24 h, expiración token 72 h heredada), TZ
`America/Argentina/Buenos_Aires`, sede única, datos 100% ficticios, secretos
solo env, NUNCA PHI por WhatsApp plano, NUNCA `verify` sin Docker en marcha ni
permiso explícito.

## Goals / Non-Goals

**Goals:**

- Recordatorios 48/24 h automáticos a turnos `pendiente|confirmado`, con
  encolado idempotente, reintentos y costo visible (Flujo 2 completo, US-010).
- La respuesta del paciente por WhatsApp actualiza la agenda sin intervención
  (vía WhatsApp de US-011; el link con token de C-05 sigue existiendo como vía
  alternativa y puede disparar la plantilla "confirmación").
- Demo local funciona sin creds Meta (`WHATSAPP_MOCK=true`); con creds reales
  el mismo código pega a la API sin cambiar specs.
- Plantillas extensibles: C-07 añade `oferta_lista_espera` sin migrar ni
  rediseñar (solo fila seed + tipo de job).
- Tasks listas para TDD estricto en apply (RED primero, verificación por task).

**Non-Goals:**

- Frontend nuevo (este change es backend + worker; a lo sumo un marcador de
  "avisos a secretaría" consultable por API para la UI existente — sin páginas
  nuevas; la UI de lista de espera es C-07).
- SMTP/SMS reales (el fallback es stub trazado; proveedor real post-TP).
- Escritura en Google Reviews API (la plantilla reseña es link/redirect, igual
  que C-12), Google Calendar (C-12), validador OS (C-11).
- Cambios a `turno`, EXCLUDE, máquina de estados o endpoints C-04/C-05 (solo
  lectura + transiciones existentes).
- Multi-sede, pagos, AFIP (fuera de v1.0 por reglas duras).

## Decisions

### D-01 — Modelo `Notificacion` delgado: estados + costo + payload auditado sin PHI

Tabla `notificacion`: `id, turno_id FK→turno (RESTRICT), canal
(whatsapp|email|sms, CHECK), plantilla (texto, CHECK contra catálogo
versionado), destinatario_ref (teléfono normalizado o email, NUNCA nombre
completo + dato clínico juntos), estado
(encolada|enviada|entregada|leída|fallida, CHECK), costo (NUMERIC nullable —
USD 0,026 por envío real, 0 en mock/stub), payload (JSONB: solo variables de
render `{nombre_pila, fecha, hora, consultorio_tel}` + `job_key`), intentos
(INT default 0), ultimo_error (texto sin PHI), timestamps. Índices:
`(turno_id)`, `(estado)` para el barrido de reintentos, UNIQUE parcial
`(turno_id, plantilla)` WHERE `estado != 'fallida'` como segunda barrera de
idempotencia a nivel DB (la primera es la clave Redis, D-03). El cuerpo
renderizado NUNCA se persiste (solo las variables): así un `SELECT` accidental
no expone texto enviado y el test sin-PHI audita variables, no strings.
Alternativa (persistir `cuerpo` enviado) descartada: duplica PHI-riesgo y no
aporta auditoría que las variables + plantilla versionada no den.
Revisión humana: confirmar que UNIQUE parcial no choca con reenvíos legítimos
(p. ej. reprogramación → nuevo recordatorio: se permite porque cambia el
`turno.inicio`; documentar que reprogramar habilita reenvío).
Skills: `fastapi`, `postgresql-table-design`, `supabase-postgres-best-practices`.

### D-02 — Catálogo cerrado de 5 plantillas seed, versionado y sin PHI por construcción

Seed (migración + `seed_plantillas.py` idempotente por `nombre+version`):
`recordatorio_48h` ("Hola {nombre_pila}, te recordamos tu turno del {fecha} a
las {hora}. Respondé SI para confirmar o llamanos al {consultorio_tel}"),
`recordatorio_24h` (igual tenor), `confirmacion` ("Tu turno del {fecha} {hora}
quedó confirmado. Te esperamos."), `hueco_liberado` (base genérica que C-07
especializa en `oferta_lista_espera` con `{fecha}/{hora}/{expira_en}`),
`resena_google` ("Gracias por tu visita. Si querés, dejanos tu reseña aquí:
{link_resena}"). Versión `v1` en cada fila; el render solo acepta las
variables declaradas (cualquier otra → `422` interno, nunca se envía). Test
sin-PHI: cada plantilla + cada payload renderizado se escanea contra lista
bloqueada (`diagnóstico, caries, endodoncia, corona, implante, pieza, FDI,
obra social, monto, deuda, historia clínica`, etc.) y contra regex de
34+ dígitos seguidos (DNI/teléfono accidental en cuerpo). Alternativa
(plantillas editables por UI admin) descartada en v1.0: exige versionado
concurrente + auditoría RN-GL-02 que C-12 puede retomar.
Skills: `fastapi`, `python-testing-patterns`.

### D-03 — Barrido horario + encolado idempotente `turno_id+tipo` con reintentos

Cron cada hora (en el worker, `asyncio` + `TZ` Buenos Aires): `SELECT` turnos
`estado IN ('pendiente','confirmado')` con `inicio` en ventana
`[48h±30min]` → tipo `recordatorio_48h`, `[24h±30min]` → `recordatorio_24h`
(`freezegun` en tests; ventana ±30 min absorbe el skew del cron horario).
Por cada candidato: clave Redis `notif:{turno_id}:{tipo}` con `SET NX EX 49h`
(48 h + margen): si ya existe → skip (idempotente ante doble tick o restart);
si no → crea fila `encolada` (respeta el UNIQUE parcial D-01; colisión →
skip) y encola job con backoff (3 intentos: inmediato, +5 min, +30 min;
`intentos` + `ultimo_error` en cada fallo). Envío confirma `enviada`
(mock: inmediata; real: `message_id` de Meta guardado en `payload`).
`entregada|leída` llegan después por webhook de estado (mismo endpoint,
evento distinto al de respuesta). Costo: mock/stub → `0`; real → `0.026`
USD por `enviada` (constante `COSTO_META_USD=0.026` documentada como ref
visible). Sin número válido (teléfono NULL o < 8 dígitos) → fila `fallida`
con `ultimo_error='sin_numero_valido'` + marcador para secretaría (D-06), sin
encolar. Alternativa (cola por `paciente_id`) descartada: dos turnos del mismo
paciente en un día deben generar dos recordatorios (uno por turno).
Skills: `redis-patterns` (SET NX EX, backoff, keys `notif:*`), `fastapi`.

### D-04 — Worker: extender el stub C-01 con módulo `notif_jobs`, no crear servicio aparte

`backend/app/worker/main.py` (stub: solo `heartbeat`) SHALL evolucionar a
scheduler: mantiene `heartbeat` y suma `bucle_notif(intervalo=3600s)` que
llama a `notif_jobs.barrido_recordatorios()` + `notif_jobs.reintentar_fallidas()`.
Nuevo `backend/app/worker/notif_jobs.py` (lógica de jobs, sin HTTP) + nuevo
`backend/app/servicios/notificacion_servicio.py` (barrido DB, idempotencia,
render, costo) + nuevo `backend/app/servicios/whatsapp_cliente.py`
(interfaz `enviar(destinatario, plantilla, variables) → {estado, message_id?,
costo}` con dos implementaciones: `Mock` y `Meta`, elegidas por
`WHATSAPP_MOCK`). El worker comparte imagen/contenedor `api` (decisión C-01):
sin servicio compose nuevo. Ante Redis caído: el barrido degrada a crear filas
`encolada` y reintenta el envío en el próximo tick (documentado; C-05 usó el
mismo patrón token→410/404 ante Redis ausente). Alternativa (servicio worker
separado en compose) descartada: duplica imagen y rompe la decisión C-01 de 4
servicios.
Skills: `redis-patterns`, `fastapi`.

### D-05 — `POST /webhooks/whatsapp`: firma obligatoria, dos eventos, sin Bearer

Ruta pública SIN `require_role` (Meta no tiene JWT nuestro) pero CON
verificación HMAC-SHA256 del cuerpo usando `WHATSAPP_WEBHOOK_SECRET`
(RN-AU-04): `X-Hub-Signature-256: sha256=<hex>`; ausente o inválida → `401` +
log estructurado con `ip + motivo` (sin cuerpo, sin teléfono). `GET
/webhooks/whatsapp` responde el challenge de verificación de Meta
(`hub.mode/hub.verify_token/hub.challenge`, token por env) — necesario para
dar de alta el webhook real. Eventos: (a) `respuesta_paciente` (texto
SI/NO/CONFIRMO/CANCELAR y equivalentes normalizados): SI → si el turno está
`pendiente`, `cambiar_estado→confirmado` (+ encola plantilla `confirmacion`
como efecto lateral); NO → si está `pendiente|confirmado`,
`cambiar_estado→cancelado` con `motivo_cancelacion='respuesta_paciente'` (el
hueco liberado queda visible para C-07); turno ya `asistido|ausente|cancelado`
→ responde `200` sin mutar (idempotente, con `detail` honesto). (b)
`estado_mensaje` (`sent/delivered/read/failed` con `message_id`) → actualiza
la `Notificacion` (`enviada|entregada|leída|fallida`) sin tocar el turno.
Fallback (RN-NO-03): si el envío WhatsApp falla 3 veces o el paciente no
tiene número válido, el servicio crea intento por `email` (si hay email) o
marca `sms` stub; el cambio de canal queda en la misma fila (`canal` muta
`whatsapp→email|sms`, `intentos` sigue) para no romper el UNIQUE D-01.
Esquemas `WebhookIn` estrictos `extra='forbid'`; cuerpo crudo preservado para
HMAC (dependencia que lee `request.body()` antes de Pydantic). Alternativa
(webhook con Bearer propio) descartada: Meta no envía nuestro JWT; la firma
HMAC ES la auth.
Revisión humana: confirmar el mapeo NO→`cancelado` directo (sin ventana de
gracia ni confirmación de secretaría) y el vocabulario aceptado (lista
cerrada vs. contiene-palabra).
Skills: `fastapi`, `python-testing-patterns`, `test-driven-development`.

### D-06 — Sin número válido → `fallida` + aviso a secretaría sin PHI

Cuando el barrido encuentra turno en ventana pero el paciente no tiene
teléfono válido (< 8 dígitos tras normalizar, igual regla que C-05 D-05) o
los 3 intentos fallan: fila en `fallida` + endpoint de lectura staff
`GET /notificaciones/pendientes` (con `require_role(secretaria|admin)`,
paginado, solo `{turno_id, inicio, paciente_nombre, motivo}` — sin PHI) para
que secretaría llame a mano. Sin websocket ni push en v1.0 (la UI lo consulta;
C-07 puede añadir contador). Log estructurado en cada `fallida` (sin teléfono
completo: últimos 4 dígitos). Alternativa (tabla `aviso_secretaria` separada)
descartada: la fila `fallida` YA es el aviso; endpoint la proyecta.

### D-07 — Mock por env + costo cero vs. real con costo, mismo contrato

`whatsapp_cliente.enviar()` tiene idéntica firma en ambas implementaciones;
`WHATSAPP_MOCK=true` (default, ya en `.env.example`) → `MockWhatsAppCliente`:
no hace HTTP, responde `{estado:'enviada', message_id:'mock-uuid', costo:0}`
y loguea plantilla + variables (sin PHI por D-02). `false` → `MetaCliente`:
exige `WHATSAPP_TOKEN` + `WHATSAPP_PHONE_ID` (ausentes → error de config en
arranque, fail-fast) y POST a Graph API con timeout 10 s; `costo=0.026` por
`enviada`. Tests parametrizan ambas (mock siempre; real con `respx`/mock
HTTP, nunca contra Meta). Fallback stub (`email/sms`) responde
`{estado:'enviada', costo:0, via_fallback:true}` y se audita igual. Esta
decisión es la que permite a C-07 funcionar en mock desde el día uno.

### D-08 — Migración `003_notificacion` + coordinación de numeración con C-08

Verificado: última migración en `backend/alembic/versions/` es
`002_turno.py` (C-04); C-05 fue cero-migración. Este change propone
`003_notificacion.py` (tabla + CHECKs + índices + UNIQUE parcial + seed de
plantillas vía `seed_plantillas.py`). Colisión conocida: `CHANGES.md` asigna
"migración 003" también a C-08 (`HC + hallazgos + catálogo`). Regla de
desempate: gana quien se aplique primero; el segundo renumera su archivo a
`004_*` (solo nombre de archivo + `down_revision`; el contenido no cambia
porque las tablas no se tocan entre sí). El apply de C-06 SHALL verificar al
inicio que `002_turno` sigue siendo `head` y, si C-08 ya generó `003_*`,
renombrar a `004_notificacion.py` con `down_revision` apuntando al `003` de
C-08. Rollback: `downgrade` borra seed + tabla (sin datos reales en v1.0).

## Risks / Trade-offs

- [Firma HMAC con cuerpo crudo choca con Pydantic que consume el body] →
  Mitigación: la dependencia lee `await request.body()` primero, verifica, y
  recién parsea (D-05); test con firma válida/inválida/ausente cubre el orden.
- [Doble tick del cron o restart duplica WhatsApps (costo + spam)] →
  Mitigación: doble barrera Redis `SET NX EX` + UNIQUE parcial DB (D-01/D-03);
  test de idempotencia con doble barrido exige 1 fila + 1 envío.
- [Ventana ±30 min pierde turnos si el worker cae > 1 h] → Mitigación: al
  arrancar, barrido de recuperación con ventana extendida `[47h,49h]/[23h,25h]`
  (una vez); caídas mayores se documentan como hueco aceptado v1.0 (los
  turnos siguen confirmables por link C-05).
- [NO por WhatsApp cancela sin intervención — riesgo de broma/error] →
  Mitigación: solo transiciones permitidas + `motivo_cancelacion` auditado
  (RN-GL-02); vocabulario cerrado (D-05); revisión humana del mapeo.
- [Plantillas seed con fecha/hora mal formateada confunden] → Mitigación:
  formato `America/Argentina/Buenos_Aires` `DD/MM HH:MM` centralizado en el
  render; test de formato con `freezegun`.
- [Costo Meta cambia y la constante miente] → Mitigación: constante con nombre
  `COSTO_META_USD_REF` + comentario "ref visible, actualizar si Meta cambia";
  el campo `costo` por fila permite recalcular histórico.
- [Colisión de numeración 003 con C-08] → Mitigación: D-08 documenta el
  desempate; el apply lo verifica antes de migrar.
- [Webhook expone superficie pública sensible] → Mitigación: governance ALTO,
  firma obligatoria + `401` + log, challenge solo con token env, sin Bearer
  que bypasee, rate-limit si trivial (igual criterio que C-05 D-04, deuda a
  C-12 si no).

## Migration Plan

1. Mergear solo artefactos openspec (este change: sin código).
2. Apply (TDD, orden): modelo + migración 003 (verificar head 002, D-08) →
   seed plantillas (idempotente) → `whatsapp_cliente` mock/real + fallback stub
   → `notificacion_servicio` (barrido, idempotencia, costo, sin-PHI) →
   `notif_jobs` + evolución `worker/main.py` (cron horario) →
   `POST/GET /webhooks/whatsapp` (firma + eventos) +
   `GET /notificaciones/pendientes` (staff) → suite verde (`pytest
   backend/app/tests` contra PG + Redis reales, nunca SQLite; `freezegun`).
3. Rollback: revertir código + `alembic downgrade -1` (borra seed + tabla);
   claves `notif:*` en Redis expiran solas (TTL 49 h) o `redis-cli DEL`.
4. `openspec validate --change c-06-notificaciones-whatsapp --strict` antes de
   archivar; archivar marca `[x]` C-06 en `CHANGES.md` y habilita C-07
   (GATE 5: C-04 ✓ + C-06 ✓).

## Open Questions

- (D-01/D-03 — revisión humana en apply, no bloquea specs/tasks): ante
  reprogramación del turno, ¿el recordatorio ya enviado se reenvía con la
  nueva hora (propuesta: sí, documentado) o se suprime?
- (D-05 — revisión humana en apply): ¿NO por WhatsApp cancela directo o pide
  confirmación de secretaría? ¿vocabulario cerrado o contiene-palabra?
- (D-08 — el apply decide): si C-08 ya generó `003_*`, ¿renumerar este change
a `004_notificacion.py` (propuesta: sí, automático)?

## Resoluciones humanas (2026-10-13, registradas por el usuario)

- **Punto 1 → opción A**: reprogramación reenvía el recordatorio con la nueva
hora (documentado en D-01).
- **Punto 2 → opción A (v1.0 demo)**: NO cancela directo con motivo auditado.
**Mejora futura post-TP**: opción B (gracia/confirmación de secretaría o
doble confirmación) — en producción real, una cancelación sin verificación
es riesgosa (broma/error). Si el proyecto escala, agregar estado intermedio
`cancelacion_a_confirmar` + endpoint staff de validación.
- **Punto 3 → opción A (v1.0 demo)**: vocabulario cerrado normalizado; lo no
reconocido → `200` sin mutar + aviso a secretaría.
**Mejora futura post-TP**: opción B (contiene-palabra / fuzzy matching con
umbral de confianza + fallback a secretaría ante ambigüedad) — en producción
los pacientes escriben frases naturales, no comandos.
