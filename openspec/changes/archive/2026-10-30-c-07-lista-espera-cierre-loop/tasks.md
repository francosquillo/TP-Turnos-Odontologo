# Tasks — c-07-lista-espera-cierre-loop

> Convención TDD estricta (Iron Law): cada task de implementación empieza con un
> test en fallo (RED) que falle por la razón esperada, luego GREEN mínimo, luego
> REFACTOR. Orden por dependencias. Chunks ≤ 2 h. Todo contra Postgres REAL +
> Redis REAL del compose (NUNCA SQLite; los CHECKs parciales, JSONB y las claves
> `SET NX EX` no existen igual en SQLite). Nombres
> `test_<unidad>_<escenario>_<resultado>` (AAA). `freezegun` para la ventana
> 2 h y TZ `America/Argentina/Buenos_Aires`. Governance MEDIO: reutilizar
> `agenda_servicio` (crear/cambiar, sin modificar), `reserva_servicio`
> (token/hash, sin duplicar), `notificacion_servicio + whatsapp_cliente`
> (aviso, sin PHI); datos 100% ficticios. Solo artefactos en esta fase (el apply
> los ejecuta); acá quedan `[ ]` pendientes.

## 1. Modelo + migración 004 + repo + matching FIFO (D-01, D-08)

- [x] 1.1 Verificar head y crear `modelos/espera_entry.py` (columnas
  `paciente_id FK RESTRICT, profesional_id FK nullable RESTRICT, especialidad
  TEXT nullable, preferencia_horaria JSONB nullable, estado CHECK
  activa|ofrecida|convertida|vencida, oferta_expira_en TIMESTAMPTZ nullable,
  token_oferta_hash TEXT nullable, oferta_hueco JSONB nullable, motivo_baja
  TEXT nullable` + CHECK (profesional o especialidad) + CHECK (ofrecida exige
  expira_en + hash) + índices `(paciente_id), (estado), (profesional_id),
  (created_at)`) con tests RED `test_espera_estado_invalido_422` (CHECK
  rechaza `dormida`) y `test_espera_sin_destino_422` (ambos NULL → CHECK) y
  `test_espera_ofrecida_exige_vencimiento_422` que pasen en GREEN al
  implementar (PG real)
- [x] 1.2 Escribir `alembic/versions/004_espera.py` (`down_revision =
  '003_notificacion'` — re-verificar head al inicio del apply; si C-08 ya
  generó `004_*`, renumerar a `005_espera.py` con `down_revision` al head
  real) con test RED `test_c07_migracion_head_encadena_003` (`alembic heads`
  una sola cabeza, cadena incluye `003_notificacion`) que pase en GREEN al
  verificar
- [x] 1.3 Crear `repos/espera_repo.py` (CRUD + `activas_compatibles(hueco,
  especialidades_profesional)` con filtros profesional/especialidad/
  preferencia + `ORDER BY created_at ASC`) con tests RED
  `test_matching_fifo_primero_compatible` (3 activas, la 1ª incompatible por
  franja → elige la 2ª) y `test_matching_sin_preferencia_acepta_todo` que
  pasen en GREEN al implementar

## 2. Servicio oferta: disparar, expirar, cascada (D-02, D-03, D-05)

- [x] 2.1 Implementar `servicios/lista_espera_servicio.py:intentar_ofrecer`
  (primera `activa` compatible → `ofrecida` + `oferta_expira_en = ahora+2h` +
  `token_oferta_hash` + snapshot `oferta_hueco`; sin compatible → no-op con
  log; excluye `ofrecida|convertida|vencida`) con tests RED
  `test_ofrecer_elige_primera_fifo` y `test_ofrecer_sin_compatible_noop`
  (freezegun; PG real) que pasen en GREEN al implementar
- [x] 2.2 Probar cascada con tests RED `test_cascada_rechazo_ofrece_siguiente`
  (rechazo entry 1 → entry 2 `ofrecida` mismo hueco) y
  `test_cascada_hueco_tomado_salta` (hueco ocupado en DB → entry a `vencida
  'hueco_tomado'` y sigue al siguiente en el mismo llamado) que pasen en
  GREEN al implementar
- [x] 2.3 Probar idempotencia con test RED `test_doble_disparo_una_oferta`
  (dos `intentar_ofrecer` mismo hueco seguidos → una sola `ofrecida`; el
  segundo es skip por exclusión de `ofrecidas` + lock `espera:cascada:*`)
  que pase en GREEN al implementar (PG + Redis reales)

## 3. Tokens + aceptar/rechazar + conversión (D-04, D-06)

- [x] 3.1 Implementar token de oferta (reusa `generar_token/hash_token` de
  `reserva_servicio`; expiración = `oferta_expira_en`, sin set Redis) con
  tests RED `test_aceptar_token_desconocido_404`,
  `test_aceptar_token_reusado_410` (entry ya `convertida` → 410, sin mutar)
  y `test_aceptar_token_expirado_410_y_cascada` (freezegun +2h01 → 410 +
  entry `vencida` + siguiente `ofrecida`) que pasen en GREEN al implementar
- [x] 3.2 Implementar conversión dos pasos (`agenda.crear_turno(
  origen="lista_espera", sobre_turno=False)` + `agenda.cambiar_estado→
  confirmado`; entry → `convertida`, hash NULL; encola `confirmacion`) con
  tests RED `test_conversion_crea_confirmado_origen_lista_espera` y
  `test_conversion_hueco_tomado_409_y_cascada` (EXCLUDE/ocupados → 409 +
  `vencida 'hueco_tomado'` + siguiente ofrecida) que pasen en GREEN al
  implementar (PG real, NUNCA `sobre_turno=true`)
- [x] 3.3 Implementar rechazo (`aceptar/rechazar/:token` → `vencida` +
  `motivo_baja='rechazo_paciente'` + cascada inmediata) con tests RED
  `test_rechazo_libera_y_ofrece_siguiente` que pasen en GREEN al implementar

## 4. Endpoints staff + públicos + hooks aditivos (D-02)

- [x] 4.1 Crear `esquemas/lista_espera.py` (`extra='forbid'`: `EsperaIn`
  con `profesional_id/especialidad` + `preferencia_horaria`, `EsperaOut` con
  `oferta_expira_en` para el countdown) y `api/lista_espera.py` (`CRUD
  /lista-espera`, `POST /:id/ofrecer` manual, `POST /:id/convertir` staff,
  `POST /aceptar/:token` + `POST /rechazar/:token` públicos sin Bearer) con
  tests RED `test_crud_staff_ok`, `test_crud_sin_bearer_401`,
  `test_ofrecer_manual_staff_ok` que pasen en GREEN al implementar
- [x] 4.2 Enganchar cancelación SIN modificar servicios (llamada aditiva a
  `intentar_ofrecer` tras `cambiar_estado→cancelado` en `PATCH
  /turnos/:id/estado` y en el evento NO de `api/webhooks.py`; el `cancelado`
  nunca se revierte si la oferta falla) con tests RED
  `test_cancelar_por_staff_dispara_oferta` y
  `test_webhook_no_dispara_oferta` (NO→cancelado ofrece al primero) y
  `test_ausente_no_dispara_oferta` (documenta D-02) que pasen en GREEN al
  implementar

## 5. Aviso por canal C-06 + plantilla seed (D-07, RN-NO-04)

- [x] 5.1 Añadir fila seed `oferta_lista_espera v1` en
  `core/seed_plantillas.py` (upsert `nombre+version`; variables `{nombre_pila,
  fecha, hora, expira_en, link_oferta}`; SIN migrar — CHECK C-06 ya la admite)
  + conectar `intentar_ofrecer` al envío (`notificacion_servicio` +
  `whatsapp_cliente`, mock OK) con tests RED `test_seed_oferta_idempotente`
  (doble seed → 6 plantillas) y `test_oferta_encola_notificacion` (ofrecer →
  fila `oferta_lista_espera` `encolada/enviada` para el turno cancelado) que
  pasen en GREEN al implementar
- [x] 5.2 Probar sin-PHI + sin-número con tests RED
  `test_oferta_sin_phi` (plantilla + payload no matchean lista bloqueada) y
  `test_oferta_sin_numero_sigue_en_ui` (teléfono inválido → notif `fallida`
  pero entry `ofrecida` con countdown; secretaría puede `convertir`) que
  pasen en GREEN al implementar

## 6. Worker de vencimientos (D-05)

- [x] 6.1 Crear `worker/espera_jobs.py` (`barrido_vencidas()`: `ofrecidas`
  con `oferta_expira_en <= ahora` → `vencida 'expirada'` + cascada mismo
  hueco, con lock `espera:cascada:* SET NX EX 900s`; degrada sin Redis a
  barrido DB idempotente) y evolucionar `worker/main.py` (mantiene
  `heartbeat + bucle_notif`, suma `bucle_espera(600s)`) con tests RED
  `test_barrido_2h_vence_y_ofrece_siguiente` (freezegun +2h01 → 1ª `vencida`,
  2ª `ofrecida` nueva ventana) y `test_barrido_sin_redis_no_duplica` que
  pasen en GREEN al implementar (PG + Redis reales)

## 7. Frontend lista de espera + página aceptar (D-04)

- [x] 7.1 Crear `features/lista-espera` (cola ordenada FIFO con estados por
  color, botón ofrecer, countdown vivo desde `oferta_expira_en`, botones
  convertir / baja con motivo; rutas staff con guard `secretaria|admin`;
  TS estricto sin `any`) + página pública `pages/lista-espera/:token`
  (detalle mínimo nombre-pila + fecha/hora + countdown + Aceptar/Rechazar;
  maneja `404/409/410` con mensajes honestos + teléfono consultorio) con
  tests RED de componente (cola ordena FIFO; countdown deriva de
  `oferta_expira_en`; aceptar llama `POST aceptar/:token`) que pasen en
  GREEN al implementar (`tsc` limpio)

## 8. Verificación integral (hacia GATE 6)

- [x] 8.1 Escenario E2E Flujo 6 (cancelar turno con 2 en espera →
  oferta a la 1ª con expiración 2 h → expira (freezegun) → cascada a la 2ª →
  acepta por token → turno `confirmado origen=lista_espera` → 3ª cancelación
  sin espera → hueco libre en `GET /disponibilidad` pública) con test RED
  `test_c07_flujo6_cierre_loop_completo` (PG + Redis reales) que pase en
  GREEN al implementar
- [x] 8.2 Ejecutar suite completa (`docker compose up -d db redis && alembic
  upgrade head && pytest backend/app/tests` + checks frontend) contra
  Postgres/Redis reales y verificar que toda la suite (C-01→C-07) está verde
  sin ningún test de constraints en SQLite — requiere Docker Desktop en marcha
  y permiso explícito (NUNCA verify sin ambos)
- [x] 8.3 Correr `cmd /c openspec validate c-07-lista-espera-cierre-loop
  --strict` y `cmd /c openspec validate --all --strict` y verificar que
  proposal/design/specs/tasks pasan sin errores (corregir lo que el validador
  reporte)
