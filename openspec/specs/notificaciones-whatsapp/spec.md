# notificaciones-whatsapp Specification

## Purpose

Dar al consultorio los recordatorios 48/24 h automáticos y la confirmación por
WhatsApp: worker Redis con barrido horario idempotente que envía plantillas
sin PHI (mock sin creds o API real con costo visible) y webhook firmado que
actualiza la agenda sin intervención, para que el Flujo 2 baje el ausentismo
sin trabajo manual y C-07 reutilice el canal para ofertas (US-010, US-011;
RN-NO-01..04, RN-AU-04, RN-CL-04, RN-TU-03).

## Requirements

### Requirement: Modelo Notificacion con estados, costo y payload sin PHI

El sistema SHALL persistir una fila `Notificacion` por envío (`turno_id FK,
canal whatsapp|email|sms, plantilla del catálogo versionado, estado
encolada|enviada|entregada|leída|fallida, costo, payload solo con variables de
render, intentos, ultimo_error sin PHI`) con UNIQUE parcial
`(turno_id, plantilla)` WHERE `estado != 'fallida'`; el cuerpo renderizado
NUNCA SHALL persistirse; la migración SHALL ser `003_notificacion.py` sobre
`002_turno` (renumerando a `004` si C-08 ya ocupó el `003`, sin cambiar
contenido).

#### Scenario: Canal inválido es rechazado por CHECK

- **WHEN** se inserta una notificación con `canal='paloma_mensajera'`
- **THEN** la DB rechaza la fila (CHECK) y ningún envío se encola

#### Scenario: UNIQUE parcial permite reintentar tras fallida pero no duplicar activa

- **WHEN** existe una fila `fallida` para un turno+plantilla y se reencola
- **THEN** la segunda fila persiste; y cuando la primera está `encolada`, la
  segunda es rechazada por la DB

#### Scenario: Migración encadena 002 sin cabezas múltiples

- **WHEN** se corre `alembic heads` tras aplicar la migración del change
- **THEN** hay una sola cabeza y la cadena incluye `002_turno`

### Requirement: Catálogo seed de 5 plantillas versionadas sin datos clínicos

El sistema SHALL sembrar idempotentemente (upsert por `nombre+version`) las
plantillas `recordatorio_48h, recordatorio_24h, confirmacion, hueco_liberado,
resena_google` en `v1`, cuyo render SOLO SHALL aceptar variables declaradas
(`{nombre_pila, fecha, hora, consultorio_tel[, link_resena, expira_en]}`) y
cuyo texto + payloads SHALL pasar el escáner sin-PHI (lista bloqueada clínica
+ regex de dígitos largos); `hueco_liberado` SHALL aceptar `{expira_en}` para
que C-07 la especialice sin migrar.

#### Scenario: Doble seed no duplica

- **WHEN** el seed corre dos veces
- **THEN** siguen existiendo exactamente 5 plantillas en `v1`

#### Scenario: Variable no declarada no se envía

- **WHEN** se intenta renderizar con una variable fuera del catálogo
- **THEN** el servicio responde error interno `422` y ningún mensaje se envía

#### Scenario: Plantilla con PHI es detectada en tests

- **WHEN** una plantilla o payload contiene un término clínico bloqueado
- **THEN** el test sin-PHI falla antes de cualquier envío

### Requirement: Barrido horario 48/24 h con encolado idempotente y reintentos

El worker SHALL correr cada hora (TZ `America/Argentina/Buenos_Aires`) y
buscar turnos `estado IN ('pendiente','confirmado')` con `inicio` en ventana
`[48h±30min]` (tipo `recordatorio_48h`) y `[24h±30min]` (tipo
`recordatorio_24h`); por candidato SHALL reservar la clave Redis
`notif:{turno_id}:{tipo}` con `SET NX EX 49h` y crear la fila `encolada` (si
la clave o el UNIQUE ya existen → skip); SHALL reintentar hasta 3 veces
(inmediato, +5 min, +30 min) registrando `intentos + ultimo_error`; cada envío
`enviada` SHALL registrar `costo` (`0` en mock/stub, `0.026` USD real,
constante `COSTO_META_USD_REF`); con Redis caído SHALL degradar a filas
`encolada` y reintentar en el próximo tick.

#### Scenario: Barrido 48 h encola pendiente y confirmado, ignora fuera de ventana

- **WHEN** hay turnos `pendiente` y `confirmado` a 48 h y otro a 12 h
- **THEN** los dos primeros quedan `encolada` con envío registrado y el tercero
  no genera fila

#### Scenario: Doble barrido no duplica envíos

- **WHEN** el barrido corre dos veces seguidas sobre el mismo turno
- **THEN** existe una sola fila no-`fallida` y un solo envío (el segundo es skip)

#### Scenario: Reintentos agotan y marcan fallida con costo trazado

- **WHEN** el envío falla 3 veces seguidas
- **THEN** la fila queda `fallida` con `intentos=3`, `ultimo_error` sin PHI y
  costo acumulado visible

### Requirement: Envío mock por env y fallback email/SMS stub

Con `WHATSAPP_MOCK=true` el sistema SHALL simular el envío (sin HTTP,
`{estado:'enviada', message_id mock, costo:0}`); con `false` SHALL exigir
`WHATSAPP_TOKEN + WHATSAPP_PHONE_ID` en arranque (fail-fast) y POST a la API
real con timeout 10 s; si WhatsApp falla 3 veces o no hay número válido,
SHALL intentar fallback `email` (si existe) o `sms` stub en la MISMA fila
(mutando `canal`, `via_fallback:true`, costo 0), dejando traza auditable
(RN-NO-03).

#### Scenario: Mock no hace HTTP y cuesta cero

- **WHEN** `WHATSAPP_MOCK=true` y se envía un recordatorio
- **THEN** no hay request HTTP, el estado es `enviada` y el costo es `0`

#### Scenario: Fallback por email tras 3 fallos deja traza

- **WHEN** WhatsApp falla 3 veces y el paciente tiene email
- **THEN** la misma fila muta a `canal=email` con `via_fallback:true` y queda
  `enviada` con costo `0`

### Requirement: Webhook verifica firma Meta y actualiza turnos

El sistema SHALL exponer `GET /webhooks/whatsapp` (challenge de verificación
con token env) y `POST /webhooks/whatsapp` SIN Bearer que SHALL verificar
HMAC-SHA256 del cuerpo crudo con `WHATSAPP_WEBHOOK_SECRET`
(`X-Hub-Signature-256`); ausente o inválida SHALL responder `401` + log sin
PHI; el evento `respuesta_paciente` SHALL normalizar SI/NO (vocabulario
cerrado): SI con turno `pendiente` SHALL aplicar `pendiente→confirmado` vía
`cambiar_estado` y encolar `confirmacion`; NO con turno
`pendiente|confirmado` SHALL aplicar `→cancelado` con
`motivo_cancelacion='respuesta_paciente'` (hueco liberado para C-07); con
turno `asistido|ausente|cancelado` SHALL responder `200` sin mutar; el evento
`estado_mensaje` SHALL actualizar solo la `Notificacion`
(`enviada|entregada|leída|fallida`) sin tocar el turno (RN-AU-04, RN-TU-03).

#### Scenario: Webhook sin firma es rechazado

- **WHEN** se llama `POST /webhooks/whatsapp` sin header de firma
- **THEN** responde `401` y ningún turno ni notificación muta

#### Scenario: Firma inválida es rechazada sin exponer datos

- **WHEN** se llama con firma incorrecta
- **THEN** responde `401`, loguea motivo sin cuerpo ni teléfono, nada muta

#### Scenario: SI confirma un pendiente y dispara confirmación

- **WHEN** el paciente responde SI para un turno `pendiente`
- **THEN** el turno pasa a `confirmado` y existe una notificación
  `confirmacion` encolada/enviada para ese turno

#### Scenario: NO cancela un confirmado y libera el hueco

- **WHEN** el paciente responde NO para un turno `confirmado`
- **THEN** el turno pasa a `cancelado` con motivo `respuesta_paciente` y el
  hueco queda ofrecible por disponibilidad

#### Scenario: Respuesta duplicada es idempotente

- **WHEN** llegan dos SI idénticos para el mismo turno
- **THEN** el primer muta a `confirmado` y el segundo responde `200` sin
  cambiar nada más

#### Scenario: Estado de mensaje no toca el turno

- **WHEN** llega `delivered` con un `message_id` conocido
- **THEN** la notificación pasa a `entregada` y el turno conserva su estado

### Requirement: Sin número válido la notificación falla y avisa a secretaría

Si el paciente no tiene teléfono válido (< 8 dígitos normalizados, misma regla
que C-05) el sistema SHALL crear la fila en `fallida`
(`ultimo_error='sin_numero_valido'`) SIN encolar; y SHALL exponer
`GET /notificaciones/pendientes` con `require_role(secretaria|admin)`
(paginado, solo `{turno_id, inicio, paciente_nombre, motivo}`, sin PHI) para
que secretaría llame a mano (RN-NO-03).

#### Scenario: Turno sin teléfono marca fallida sin encolar

- **WHEN** el barrido encuentra un turno a 48 h sin teléfono válido
- **THEN** existe fila `fallida` y no hay job encolado ni costo

#### Scenario: Pendientes exige rol staff y no expone PHI

- **WHEN** se llama `GET /notificaciones/pendientes` sin Bearer o con rol
  paciente
- **THEN** responde `401/403`; y con rol secretaría responde `200` sin campos
  clínicos en ningún elemento

### Requirement: Reserva online alimenta el barrido y la confirmación dispara plantilla

Los turnos `origen=online` `pendiente` de C-05 SHALL entrar al barrido 48/24 h
sin código extra; `GET /confirmar/:token` exitoso SHALL encolar la plantilla
`confirmacion` como efecto lateral aditivo SIN cambiar su contrato
(`200/404/410` intactos); C-07 SHALL poder añadir `oferta_lista_espera` como
fila seed + tipo de job sin migrar.

#### Scenario: Turno online a 48 h entra al barrido

- **WHEN** se crea una reserva online con `inicio` a 48 h
- **THEN** el próximo barrido la encola como `recordatorio_48h`

#### Scenario: Confirmar por token encola confirmación sin cambiar el contrato

- **WHEN** se confirma un token válido
- **THEN** responde `200` como en C-05 y además existe notificación
  `confirmacion` para ese turno
