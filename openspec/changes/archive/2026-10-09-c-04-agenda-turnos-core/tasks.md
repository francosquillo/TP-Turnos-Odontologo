# Tasks — c-04-agenda-turnos-core

> Convención TDD estricta (Iron Law): cada task de implementación empieza con un
> test en fallo (RED) que falle por la razón esperada, luego GREEN mínimo, luego
> REFACTOR. Orden por dependencias. Chunks ≤ 2 h. Turnos contra Postgres REAL
> del compose (NUNCA SQLite — no soporta EXCLUDE/GiST). Nombres
> `test_<unidad>_<escenario>_<resultado>` (AAA). `freezegun` para tiempos y TZ
> `America/Argentina/Buenos_Aires`. Governance CRITICO: no escribir código
> productivo sin su test en rojo primero. Solo artefactos en esta fase (el apply
> los ejecuta); acá quedan `[ ]` pendientes.

## 1. Migración 002 + modelo Turno con doble EXCLUDE (DD-03, D-01)

- [x] 1.1 Crear migración 002 `turno` (`paciente_id, profesional_id, sillon_id,
  inicio/fin timestamptz, estado, origen, token_confirmacion_hash nullable,
  sobre_turno bool default false, motivo_sobreturno/motivo_cancelacion nullable,
  creado_por nullable, created_at`) + CHECK `fin > inicio` + doble `EXCLUDE`
  parcial profesional/sillón (D-01) + índices `(profesional,inicio)`,
  `(sillon,inicio)`, `estado`, token parcial, con test RED
  `test_c04_migracion_002_aplica_en_pg_real` (aplica upgrade/downgrade contra PG
  real del compose) que pase en GREEN al crear la migración
- [x] 1.2 Crear `modelos/turno.py` (SQLAlchemy 2 async, `Mapped` + type hints,
  enums `estado/origen` como CHECK o `sa.Enum`, `server_default`s) con test RED
  `test_turno_mapeo_redondo_pg` (insert+select por repo contra PG real) que pase
  en GREEN al crear el modelo
- [x] 1.3 Probar EXCLUDE a nivel DB con test RED
  `test_exclude_profesional_rechaza_solape` y
  `test_exclude_sillon_rechaza_solape` (inserts crudos concurrentes, esperan
  `ExclusionViolation`/raise) + `test_exclude_permite_contiguo_y_cancelado`
  (contiguo 10:30→11:00 ok, cancelado no bloquea) que pasen en GREEN con los
  constraints de 1.1 (sin código de app que los enmascare)

## 2. Servicio agenda: huecos, creación y sobreturno (D-02, D-04)

- [x] 2.1 Crear `repos/turno_repo.py` (por profesional/sillón/rango, activos,
  excluir propio id) con test RED `test_turno_repo_rango_por_profesional`
  (seed 3 turnos, filtra rango correctamente) que pase en GREEN al implementar
- [x] 2.2 Implementar cálculo de huecos en `servicios/agenda_servicio.py`
  (lee `agenda_config`, genera slots, resta ocupados profesional+sillón, TZ
  Buenos_Aires) con tests RED `test_huecos_resta_turnos_existentes` y
  `test_huecos_fuera_de_horario_vacio` que pasen en GREEN al implementar
- [x] 2.3 Implementar `crear_turno` (valida FKs, `fin > inicio`, pre-chequeo
  solapamiento → `HuecoOcupadoError` con alternativas; sobreturno solo con
  `sobre_turno=true + motivo`, registra auditoría) con tests RED
  `test_crear_solape_sin_flag_409`, `test_sobreturno_sin_motivo_rechazado` y
  `test_sobreturno_con_motivo_audita` que pasen en GREEN al implementar
- [x] 2.4 Probar carrera concurrente real con test RED
  `test_creacion_concurrente_mismo_hueco_un_ganador` (2 tareas `asyncio`
  contra PG real, una `201` una `HuecoOcupadoError/409`, solo 1 turno persiste)
  que pase en GREEN con 2.3 + D-01 (la DB decide)

## 3. Esquemas + routers protegidos (D-03, D-06, D-07)

- [x] 3.1 Crear `esquemas/turno.py` (`TurnoIn/TurnoOut/EstadoPatch/ReprogramarIn`,
  `extra='forbid'`, `fin > inicio`, motivo obligatorio condicional) con test RED
  `test_turno_in_rechaza_campo_extra` (campo extra → 422) que pase en GREEN al
  crear los esquemas
- [x] 3.2 Implementar `CRUD /turnos` real (reemplaza stub, `require_role`
  según D-07, `origen=secretaria` nace `confirmado`) con tests RED
  `test_post_turno_ok_201`, `test_post_turno_solapado_409_con_alternativas` y
  `test_get_turnos_sin_bearer_401` que pasen en GREEN al implementar
- [x] 3.3 Implementar `PATCH /turnos/:id/estado` (máquina D-03, motivo
  obligatorio al cancelar, terminales bloqueados) con tests RED
  `test_confirmar_pendiente_ok`, `test_cancelar_sin_motivo_422` y
  `test_transicion_terminal_422` (tabla parametrizada de transiciones) que pasen
  en GREEN al implementar
- [x] 3.4 Implementar `PATCH /turnos/:id` reprogramación (excluye propio id,
  revalida como creación, colisión → `409` + alternativas, turno conserva horario
  original) con tests RED `test_reprogramar_a_ocupado_409_conserva_horario` y
  `test_reprogramar_a_libre_ok` que pasen en GREEN al implementar

## 4. Disponibilidad + agenda por vistas (D-04)

- [x] 4.1 Implementar `GET /disponibilidad` (filtros profesional/desde/hasta/
  sillon/duración, respeta `agenda_config` + RN-TU-01/05, RBAC staff) con tests
  RED `test_disponibilidad_respeta_horario_y_turnos` y
  `test_disponibilidad_fuera_horario_vacia` que pasen en GREEN al implementar
- [x] 4.2 Implementar `GET /agenda?vista=dia|semana|mes` (agregación ordenada
  por `inicio` con paciente/profesional/sillón) con tests RED
  `test_agenda_dia_lista_ordenada` y `test_agenda_vista_invalida_422` que pasen
  en GREEN al implementar

## 5. Frontend features/agenda (D-08)

- [x] 5.1 Implementar `features/agenda` vistas día/semana/mes + colores por
  estado + crear (click hueco libre) + cancelar con modal de motivo (tipado
  estricto, cero `any`, PascalCase, `fetchConAuth` de C-03), verificado con test
  RED de render (Vitest/Testing Library o Playwright según convención del repo:
  agenda día muestra turnos con color por estado; cancelar sin motivo bloquea el
  submit) que pase en GREEN al implementar
- [x] 5.2 Implementar drag para reprogramar con rollback (optimista, ante `409`
  restaura horario original y muestra alternativas de la API), verificado con
  test RED (mock `409` con alternativas → UI restaura + lista alternativas) que
  pase en GREEN al implementar

## 6. Verificación integral GATE 3 (entrada)

- [x] 6.1 Fijar formato demo de `agenda_config` en seed/fixtures (slots + TZ
  documentados, reutilizable por C-05) con test RED
  `test_agenda_config_demo_parsea` que pase en GREEN al fijarlo
- [x] 6.2 Ejecutar suite completa (`docker compose up -d db redis && alembic
  upgrade head && pytest backend/app/tests` + checks frontend) contra
  Postgres/Redis reales y verificar que toda la suite (C-01 + C-02 + C-03 + C-04)
  está verde sin ningún test de constraints en SQLite — pre-GATE 3
- [x] 6.3 Correr `openspec validate --change c-04-agenda-turnos-core --strict`
  y verificar que proposal/design/specs/tasks pasan sin errores (corregir lo que
  el validador reporte)
