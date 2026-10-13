# Tasks — c-06-notificaciones-whatsapp

> Convención TDD estricta (Iron Law): cada task de implementación empieza con un
> test en fallo (RED) que falle por la razón esperada, luego GREEN mínimo, luego
> REFACTOR. Orden por dependencias. Chunks ≤ 2 h. Todo contra Postgres REAL +
> Redis REAL del compose (NUNCA SQLite; los constraints UNIQUE parcial y las
> claves `SET NX EX` no existen en SQLite). Nombres
> `test_<unidad>_<escenario>_<resultado>` (AAA). `freezegun` para tiempos
> (ventanas 48/24 h) y TZ `America/Argentina/Buenos_Aires`. Governance ALTO:
> secretos solo env (`WHATSAPP_*`, ya en `.env.example` desde C-01), firma HMAC
> obligatoria, NUNCA PHI en plantillas/payloads/logs (datos 100% ficticios).
> Solo artefactos en esta fase (el apply los ejecuta); acá quedan `[ ]`
> pendientes.

## 1. Modelo + migración 003 + seed plantillas (D-01, D-02, D-08)

- [x] 1.1 Verificar numeración y crear `modelos/notificacion.py` (columnas
  `turno_id FK RESTRICT, canal/catalog CHECK, plantilla CHECK, estado CHECK,
  costo NUMERIC nullable, payload JSONB solo variables, intentos, ultimo_error`
  + índices `(turno_id), (estado)` + UNIQUE parcial `(turno_id, plantilla)`
  WHERE `estado != 'fallida'`) con tests RED
  `test_notificacion_canal_invalido_422` (CHECK rechaza `paloma_mensajera`) y
  `test_notificacion_unique_parcial_permite_reintento_tras_fallida` (dos filas
  mismo turno+plantilla con primera `fallida` ok; con primera `encolada` →
  IntegrityError) contra PG real que pasen en GREEN al implementar
- [x] 1.2 Escribir `alembic/versions/003_notificacion.py` (tabla + CHECKs +
  índices + UNIQUE parcial; `down_revision='002_turno'` — si C-08 ya generó
  `003_*`, renombrar a `004_notificacion.py` con `down_revision` al head real;
  verificar head al inicio del apply) con test RED
  `test_c06_migracion_head_encadena_002` (`alembic heads` muestra una sola
  cabeza y la cadena incluye `002_turno`; documenta D-08) que pase en GREEN al
  verificar
- [x] 1.3 Implementar seed idempotente `core/seed_plantillas.py` (5 plantillas
  `recordatorio_48h, recordatorio_24h, confirmacion, hueco_liberado,
  resena_google` en `v1`, upsert por `nombre+version`, render solo con
  variables declaradas) con tests RED
  `test_seed_plantillas_idempotente` (doble seed → 5 filas) y
  `test_render_variable_no_declarada_422` que pasen en GREEN al implementar
- [x] 1.4 Probar garantía sin-PHI con tests RED `test_plantillas_sin_phi`
  (las 5 plantillas + payloads renderizados no matchean lista bloqueada
  clínica ni regex de dígitos largos) y
  `test_payload_no_persiste_cuerpo` (la fila guarda variables, no el texto
  renderizado) que pasen en GREEN al implementar (D-01/D-02)

## 2. Cliente WhatsApp mock/real + fallback stub (D-07, RN-NO-03)

- [x] 2.1 Crear `servicios/whatsapp_cliente.py` (interfaz
  `enviar(destinatario, plantilla, variables)`; `MockWhatsAppCliente` con
  `WHATSAPP_MOCK=true` responde `enviada/mock-uuid/costo 0` sin HTTP;
  `MetaCliente` con `false` exige `TOKEN+PHONE_ID` fail-fast y POST con timeout
  10 s, `costo=COSTO_META_USD_REF=0.026`) con tests RED
  `test_mock_no_hace_http_y_costo_cero` y `test_real_sin_creds_falla_en_arranque`
  que pasen en GREEN al implementar
- [x] 2.2 Implementar fallback stub (tras 3 fallos WhatsApp o sin número: reintenta
  por `email` si existe, si no `sms` stub; muta `canal` en la misma fila con
  `via_fallback:true`, costo 0, traza completa) con tests RED
  `test_fallback_email_tras_3_fallos_whatsapp` y
  `test_fallback_sms_stub_sin_email` que pasen en GREEN al implementar

## 3. Servicio notificaciones: barrido idempotente + costo (D-03, RN-NO-01/02)

- [x] 3.1 Implementar `servicios/notificacion_servicio.py:barrido_recordatorios`
  (busca `pendiente|confirmado` con `inicio` en `[48h±30min]/[24h±30min]`;
  clave Redis `notif:{turno_id}:{tipo}` `SET NX EX 49h`; sin número válido →
  `fallida 'sin_numero_valido'` sin encolar; backoff 3 intentos) con tests RED
  `test_barrido_48h_encola_pendiente_y_confirmado` (freezegun: turnos a 48 h
  exacta generan `recordatorio_48h`; a 12 h no generan nada) y
  `test_barrido_sin_numero_marca_fallida_sin_encolar` que pasen en GREEN al
  implementar (PG + Redis reales)
- [x] 3.2 Probar idempotencia con test RED
  `test_doble_barrido_un_solo_envio` (dos barridos seguidos mismo turno →
  1 fila no-`fallida` + 1 envío; el segundo es skip por Redis y por UNIQUE
  parcial) que pase en GREEN con 3.1 + D-01
- [x] 3.3 Probar reintentos y costo con tests RED
  `test_reintento_backoff_3_intentos_luego_fallida` y
  `test_costo_mock_cero_y_real_0026` (mock → 0; HTTP moqueado real → 0.026)
  que pasen en GREEN al implementar

## 4. Worker: extender stub C-01 con `notif_jobs` (D-04)

- [x] 4.1 Crear `worker/notif_jobs.py` (`barrido_recordatorios()` +
  `reintentar_fallidas()`; sin HTTP directo, delega en servicio + cliente) y
  evolucionar `worker/main.py` (mantiene `heartbeat`, suma
  `bucle_notif(3600s)` + barrido de recuperación al arranque `[47h,49h]/
  [23h,25h]`) con test RED `test_notif_jobs_delega_sin_duplicar` (barrido vía
  jobs con Redis real no duplica) que pase en GREEN al implementar

## 5. Webhook firmado + actualización de turnos (D-05, RN-AU-04, RN-TU-03)

- [x] 5.1 Crear `esquemas/webhook.py` (`WebhookIn` estricto `extra='forbid'`,
  preserva cuerpo crudo para HMAC) e implementar `api/webhooks.py`
  (`GET /webhooks/whatsapp` challenge con token env; `POST` verifica
  HMAC-SHA256 `X-Hub-Signature-256` con `WHATSAPP_WEBHOOK_SECRET`, sin Bearer)
  con tests RED `test_webhook_sin_firma_401`, `test_webhook_firma_invalida_401`
  (+ log sin PHI) y `test_webhook_challenge_ok` que pasen en GREEN al
  implementar
- [x] 5.2 Implementar evento `respuesta_paciente` (SI→`pendiente→confirmado` +
  encola `confirmacion`; NO→`pendiente|confirmado→cancelado` con motivo
  `respuesta_paciente`; turno `asistido|ausente|cancelado` → `200` sin mutar)
  reutilizando `cambiar_estado` (sin SQL directo) con tests RED
  `test_webhook_si_confirma_pendiente`, `test_webhook_no_cancela_confirmado`
  (hueco liberado visible para C-07) y `test_webhook_respuesta_idempotente`
  (doble SI → un solo cambio) que pasen en GREEN al implementar
- [x] 5.3 Implementar evento `estado_mensaje`
  (`sent/delivered/read/failed` + `message_id` → `enviada|entregada|leída|
  fallida` sin tocar el turno) con test RED
  `test_webhook_estado_actualiza_sin_tocar_turno` que pase en GREEN al
  implementar
- [x] 5.4 Implementar `GET /notificaciones/pendientes` staff
  (`require_role(secretaria|admin)`, paginado, solo
  `{turno_id, inicio, paciente_nombre, motivo}`, sin PHI) con tests RED
  `test_pendientes_staff_ok_sin_phi` y `test_pendientes_sin_bearer_401` que
  pasen en GREEN al implementar (D-06)

## 6. Conexión C-05 + extensibilidad C-07

- [x] 6.1 Conectar reserva online (crear turno `origen=online pendiente` entra
  al barrido 48/24 h sin código extra; `GET /confirmar/:token` exitoso encola
  `confirmacion` como efecto lateral aditivo sin cambiar su `200/404/410`)
  con test RED `test_reserva_online_entra_al_barrido` (turno online a 48 h →
  barrido lo encola) que pase en GREEN al implementar
- [x] 6.2 Probar extensibilidad C-07 con test RED
  `test_plantilla_hueco_extensible_a_oferta` (render `hueco_liberado` acepta
  variables extra `{expira_en}` declaradas para la futura `oferta_lista_espera`
  sin migrar) que pase en GREEN al verificar (documenta que C-07 solo añade
  fila seed + tipo de job)

## 7. Verificación integral (hacia GATE 5)

- [x] 7.1 Ejecutar suite completa (`docker compose up -d db redis && alembic
  upgrade head && pytest backend/app/tests` + checks frontend) contra
  Postgres/Redis reales y verificar que toda la suite (C-01 + C-02 + C-03 +
  C-04 + C-05 + C-06) está verde sin ningún test de constraints en SQLite —
  requiere Docker Desktop en marcha y permiso explícito (NUNCA verify sin ambos)
  [VERIFICADO 2026-10-13 con Docker: C-06 47/47 (barrido, idempotencia, firma,
  worker, reintentos en PG/Redis reales), migración 002→003 limpia, frontend
  16/16 + tsc limpio; fixes post-verify: test downgrade C-04 + 14 tests fechas
  fijas con freezegun → full suite 239 passed 0 failed 0 skipped]
- [x] 7.2 Correr `cmd /c openspec validate c-06-notificaciones-whatsapp --strict`
  y `cmd /c openspec validate --all --strict` y verificar que
  proposal/design/specs/tasks pasan sin errores (corregir lo que el validador
  reporte)
