# Tasks — c-05-reserva-online-publica

> Convención TDD estricta (Iron Law): cada task de implementación empieza con un
> test en fallo (RED) que falle por la razón esperada, luego GREEN mínimo, luego
> REFACTOR. Orden por dependencias. Chunks ≤ 2 h. Todo contra Postgres REAL del
> compose (NUNCA SQLite). Nombres `test_<unidad>_<escenario>_<resultado>` (AAA).
> `freezegun` para tiempos (token 72 h) y TZ `America/Argentina/Buenos_Aires`.
> Governance MEDIO: superficie pública sin auth — no exponer PHI ni agenda ajena
> en ningún test/fixture (datos 100% ficticios). Sin migración SQL en este
> change (columna hash ya existe, expiración derivada — D-02/D-08). Solo
> artefactos en esta fase (el apply los ejecuta); acá quedan `[ ]` pendientes.

## 1. Servicio reserva: token, expiración y paciente mínimo (D-01, D-02, D-05)

- [x] 1.1 Crear `servicios/reserva_servicio.py` con generación de token opaco
  (`secrets.token_urlsafe(32)`) + hash SHA-256 y expiración derivada
  `min(created_at + 72 h, inicio)` (funciones puras `generar_token`,
  `hash_token`, `token_expirado(creado_en, inicio, ahora)`, sin DB) con tests
  RED `test_token_hash_no_expone_plano` (el hash no contiene el token y es
  determinista) y `test_token_expira_72h_o_inicio` (parametrizado freezegun:
  dentro de ventana ok, +73 h expirado, inicio pasado aunque no pasen 72 h
  expirado) que pasen en GREEN al implementar
- [x] 1.2 Implementar match/creación de paciente mínimo por teléfono
  normalizado (solo dígitos, mínimo 8; reutiliza no soft-deleted, si no existe
  crea `nombre+telefono`) con tests RED
  `test_reserva_reutiliza_paciente_por_telefono`,
  `test_reserva_crea_paciente_minimo_si_no_existe` y
  `test_reserva_telefono_invalido_422` (contra PG real, datos ficticios) que
  pasen en GREEN al implementar
- [x] 1.3 Implementar `crear_reserva` (valida hueco ofrecible con
  `calcular_huecos` fresco + delega en `crear_turno(origen="online")` que nace
  `pendiente`; colisión → `HuecoOcupadoError` con alternativas; guarda hash,
  responde datos para `201`) con tests RED
  `test_reserva_crea_pendiente_con_hash` (estado `pendiente`, hash no nulo y
  distinto del plano, `sobre_turno=false`) y
  `test_reserva_hueco_ocupado_409_con_alternativas` que pasen en GREEN al
  implementar
- [x] 1.4 Implementar `confirmar_por_token` (hashea, busca por hash, valida
  expiración D-02 y estado `pendiente`, aplica `cambiar_estado→confirmado` e
  invalida hash a NULL en la misma transacción) con tests RED
  `test_confirmar_token_valido_confirma`,
  `test_confirmar_reuso_token_410` (segundo uso no cambia nada),
  `test_confirmar_expirado_410_con_contacto` (freezegun +73 h) y
  `test_confirmar_desconocido_404` (contra PG real) que pasen en GREEN al
  implementar
- [x] 1.5 Probar carrera concurrente pública con test RED
  `test_reserva_concurrente_mismo_hueco_un_ganador` (2 `POST` lógicos vía
  servicio con `asyncio` contra PG real: un `201` un `HuecoOcupadoError/409`,
  solo 1 turno persiste) que pase en GREEN con 1.3 + EXCLUDE de C-04 (la DB
  decide)

## 2. Esquemas + routers públicos (D-03, D-04, D-06)

- [x] 2.1 Crear `esquemas/reserva.py` (`ReservaIn` con nombre ≥ 2 y teléfono
  válido, `ReservaOut` con token + expira_en, `ConfirmarOut`; `extra='forbid'`)
  con test RED `test_reserva_in_rechaza_campo_extra` (campo extra → 422) y
  `test_reserva_in_nombre_corto_422` que pasen en GREEN al crear los esquemas
- [x] 2.2 Implementar `POST /reservas` público (sin `require_role`, sin
  sobreturno por esta vía, `creado_por=NULL`; `201` con token una única vez)
  con tests RED `test_post_reserva_ok_201`,
  `test_post_reserva_fuera_horario_no_crea` y
  `test_post_reserva_sin_bearer_ok` (público de verdad: sin Authorization
  responde `201`, no `401`) que pasen en GREEN al implementar
- [x] 2.3 Implementar `GET /confirmar/:token` + alias `POST /confirmar/:token`
  (válido → `200` solo con datos propios; reusado/expirado → `410` con
  contacto; desconocido → `404` genérico; cancelado por secretaría → `410`
  honesto) con tests RED `test_confirmar_endpoint_200_actualiza_agenda`,
  `test_confirmar_reuso_410`, `test_confirmar_expirado_410_contacto` y
  `test_confirmar_desconocido_404` que pasen en GREEN al implementar
- [x] 2.4 Implementar variante pública de `GET /disponibilidad` (sin auth,
  `profesional_id` requerido, solo `[{inicio, fin}]` sin datos de pacientes;
  staff intacta con `401` sin Bearer) con tests RED
  `test_disponibilidad_publica_sin_bearer_200_sin_pacientes`,
  `test_disponibilidad_publica_sin_profesional_422` y
  `test_disponibilidad_publica_mismos_huecos_que_staff` que pasen en GREEN al
  implementar

## 3. Frontend público (D-07)

- [x] 3.1 Implementar `pages/Reservas.tsx` real (reemplaza stub: paso 1
  profesional/día → disponibilidad pública, paso 2 grilla de huecos, paso 3
  nombre+teléfono → `POST /reservas`, éxito con aviso WhatsApp + link demo;
  tipado estricto, cero `any`, PascalCase, `fetch` sin Bearer), verificado con
  test RED de render (Vitest/Testing Library: elige hueco, completa formulario
  mínimo y envía → muestra éxito; formulario incompleto bloquea el submit) que
  pase en GREEN al implementar
- [x] 3.2 Implementar manejo `409` con re-oferta en Reservas (ante `409` con
  alternativas → panel de huecos sin perder nombre/teléfono), verificado con
  test RED (mock `409` con alternativas → UI lista alternativas y conserva el
  formulario) que pase en GREEN al implementar
- [x] 3.3 Implementar `pages/Confirmar.tsx` real (reemplaza stub: lee `:token`,
  `cargando|confirmado|expirado|invalido`; expirado/inválido con teléfono del
  consultorio desde env/constante ficticia) + `GET /` landing pública (links a
  `/reservas` y `/seguridad`) + rutas en `App.tsx` fuera del guard de roles,
  verificado con tests RED (token válido → éxito; token expirado → contacto
  visible; `/` renderiza links) que pasen en GREEN al implementar

## 4. Verificación integral (salida de GATE 3 → GATE 4)

- [x] 4.1 Verificar cero-migración y columna compartida: test RED
  `test_c05_sin_migracion_nueva` (ningún archivo de migración nuevo; turnos
  staff mantienen hash NULL — escenario del delta `agenda-turnos-core`) que
  pase en GREEN al verificar (documenta D-08; si la revisión humana de D-02
  pide columna explícita, esta task se reabre con migración)
- [x] 4.2 Ejecutar suite completa (`docker compose up -d db redis && alembic
  upgrade head && pytest backend/app/tests` + checks frontend) contra
  Postgres/Redis reales y verificar que toda la suite (C-01 + C-02 + C-03 +
  C-04 + C-05) está verde sin ningún test de constraints en SQLite — requiere
  Docker Desktop en marcha y permiso explícito (NUNCA verify sin ambos)
- [x] 4.3 Correr `cmd /c openspec validate c-05-reserva-online-publica --strict`
  y `cmd /c openspec validate --all --strict` y verificar que
  proposal/design/specs/tasks pasan sin errores (corregir lo que el validador
  reporte)
