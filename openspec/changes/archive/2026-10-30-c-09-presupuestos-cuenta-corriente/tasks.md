# Tasks — c-09-presupuestos-cuenta-corriente

> Convención TDD estricta: cada task empieza con un test en fallo por la razón
> esperada (RED), sigue con el mínimo código (GREEN), triangula con al menos un caso
> distinto y termina con REFACTOR en verde. Chunks ≤ 2 h, en orden de dependencias.
> Constraints y concurrencia siempre contra **Postgres real** del compose, NUNCA
> SQLite. `freezegun` para `presentado_at`, `decidido_at` y `created_at`. Nombres
> `test_<unidad>_<escenario>_<resultado>` (AAA). Datos 100% ficticios. Sin PHI en logs.
> Esquemas `extra='forbid'`. Dinero en `NUMERIC`/`Decimal`. TS sin `any`.
>
> Docker: pedir permiso explícito antes de iniciar Docker Desktop y levantar
> `db+redis`; bajarlos al cerrar (reglas duras). Puerto alternativo si PG18 ocupa
> 5432: `POSTGRES_PORT=5433` y `DATABASE_URL_TEST` acorde.
>
> Antes de apply: confirmar las decisiones **[aprobar]** de `design.md`. Antes de tocar
> la DB, leer las reglas de `postgresql-table-design` y `supabase-postgres-best-practices`.

## 1. Modelos y migración 006 (D-01, D-02, D-11, D-12)

- [x] 1.1 Capturar la línea base: correr `pytest` y los tests de frontend, anotar el conteo y reportar sin arreglar cualquier falla previa. Verificar que `alembic heads` da solo `005_clinica`
- [x] 1.2 Crear `modelos/presupuesto.py` (`Presupuesto`, `ItemPresupuesto`) con los CHECK e índices de D-02 y exportar en `modelos/__init__.py`. RED en `test_c09_modelos.py` (PG real): `test_presupuesto_estado_desconocido_rechazado`, `test_presupuesto_rechazado_sin_motivo_rechazado`, `test_presupuesto_baja_no_borrador_rechazada`, `test_item_sin_hallazgo_rechazado`, `test_item_repetido_rechazado`, `test_item_cantidad_cero_rechazada`
- [x] 1.3 Crear `modelos/cuenta_corriente.py` (`CuentaCorriente`, `Movimiento`) con CHECK de tipo, signo y anulación, índices únicos parciales de cargo y `anula_a_id`, `recibo_id` sin FK y `creado_por` RESTRICT. RED: `test_cuenta_paciente_duplicado_rechazado`, `test_cuenta_sin_columna_saldo`, parametrizado de tipo y signo, `test_movimiento_segundo_cargo_mismo_presupuesto_rechazado`, `test_movimiento_doble_anulacion_rechazada`, `test_movimiento_anulacion_sin_motivo_rechazada`, `test_movimiento_recibo_inexistente_aceptado`
- [x] 1.4 Adjuntar función y trigger de inmutabilidad con `event.listen` en dos sentencias separadas. RED: `test_movimiento_update_rechazado`, `test_movimiento_delete_rechazado`, `test_movimiento_insert_sigue_permitido` (PG real, con `create_all`)
- [x] 1.5 Escribir `alembic/versions/006_presupuestos_cc.py` (`down_revision = "005_clinica"`, tablas, función, trigger, downgrade completo). RED en `test_c09_migracion.py`: `test_c09_cabeza_unica_006_sobre_005`, `test_c09_migracion_declara_checks_e_indices_del_modelo`, `test_c09_trigger_migracion_igual_a_modelo`, `test_c09_downgrade_upgrade_limpio` (PG real con Alembic)
- [x] 1.6 Ajustar por la cabeza nueva: `test_c08_migracion.py` (cabeza y downgrade con revisión explícita), `test_c05_reserva_pg.py` (sumar `006_presupuestos_cc.py`), `db_utils.reset_estado_base` (sumar las 4 tablas y la función). Verificar con los tests de migraciones C-02, C-05, C-07, C-08 y C-09 en verde

## 2. Esquemas (D-04, D-06, D-09)

- [x] 2.1 Crear `esquemas/presupuesto.py` (`ItemIn`, `PresupuestoIn`, `PresupuestoPut`, `RechazoIn`, `ItemOut`, `PresupuestoOut`), reutilizando `Motivo` y `BajaIn`. RED en `test_c09_esquemas.py`: `test_presupuesto_sin_items_invalido`, `test_presupuesto_51_items_invalido`, `test_item_sin_hallazgo_invalido`, `test_item_sin_tratamiento_invalido`, `test_item_con_precio_invalido`, `test_presupuesto_con_total_invalido`, `test_presupuesto_con_estado_cobrado_invalido`, `test_items_repetidos_invalidos`, `test_item_cantidad_100_invalida`, `test_rechazo_sin_motivo_invalido`, `test_importe_serializa_como_texto`
- [x] 2.2 Crear `esquemas/cuenta.py` (`AnulacionIn`, `MovimientoOut`, `CuentaOut`). RED: `test_anulacion_sin_motivo_invalida`, `test_anulacion_campo_extra_invalida`, `test_cuenta_saldo_serializa_como_texto`

## 3. Repos (D-11, D-13)

- [x] 3.1 Crear `repos/presupuesto_repo.py` (`get_para_actualizar` con `FOR UPDATE`, `listar` por paciente y estado sin bajas, reemplazo de ítems, lectura de ítems con tratamiento y hallazgo). RED en `test_c09_repos.py` (PG real): `test_listar_filtra_estado_y_excluye_bajas`, `test_listar_mas_reciente_primero`, `test_reemplazar_items_deja_solo_los_nuevos`, `test_items_indican_hallazgo_no_vigente`
- [x] 3.2 Crear `repos/cuenta_repo.py` (`asegurar` con `ON CONFLICT DO NOTHING`, `saldo`, `movimientos` con `anulado`, `movimiento_para_actualizar`). RED: `test_asegurar_dos_veces_una_fila`, `test_saldo_suma_cargo_pago_ajuste`, `test_saldo_sin_movimientos_cero`, `test_saldo_negativo_a_favor`, `test_movimiento_listado_marca_anulado`

## 4. Servicio de presupuestos (D-03..D-10, D-13)

- [x] 4.1 Crear `servicios/presupuesto_servicio.py` con el alta: permisos, validación de ítems, copia de precio y cálculo de total. RED en `test_c09_servicio.py`: `test_crear_copia_precio_base`, `test_crear_calcula_total`, `test_crear_hallazgo_dado_de_baja_422`, `test_crear_hallazgo_de_otro_paciente_422`, `test_crear_historia_dada_de_baja_422`, `test_crear_tratamiento_inexistente_422`, `test_crear_paciente_eliminado_404`, `test_crear_sin_vinculo_403`, `test_crear_sin_profesional_403`, `test_crear_autor_del_token`, `test_crear_hallazgo_de_otro_profesional_ok`, `test_mismo_hallazgo_en_dos_presupuestos_ok`
- [x] 4.2 Sumar `reemplazar_items` y `dar_de_baja`, solo en `borrador` y solo autor. RED: `test_reemplazar_recalcula_total`, `test_reemplazar_toma_precio_vigente`, `test_reemplazar_presentado_409`, `test_reemplazar_ajeno_403`, `test_baja_borrador_conserva_fila`, `test_baja_presentado_409`, `test_baja_oculta_presupuesto_404`
- [x] 4.3 Sumar `presentar` y `rechazar` con la máquina de estados, usando `freezegun`. RED: `test_presentar_fija_fecha`, `test_presentar_total_cero_422`, `test_presentar_hallazgo_corregido_409`, `test_presentar_dos_veces_409`, `test_rechazar_guarda_motivo_sin_movimientos`, `test_rechazar_borrador_409`, `test_rechazado_es_final_409`
- [x] 4.4 Sumar `aceptar`: lock, revalidación, cuenta y cargo en una transacción. RED: `test_aceptar_genera_cargo_por_total`, `test_aceptar_concepto_sin_phi`, `test_aceptar_guarda_creado_por`, `test_aceptar_hallazgo_dado_de_baja_409_sin_movimiento`, `test_aceptar_borrador_409`, `test_aceptar_repetido_409_un_cargo`, `test_aceptar_ajeno_403_sin_cargo`, `test_catalogo_cambia_tras_presentar_conserva_total`
- [x] 4.5 Probar concurrencia con dos sesiones reales y `asyncio.gather`. RED en `test_c09_concurrencia.py` (PG real): `test_doble_aceptacion_concurrente_un_cargo`, `test_primer_cargo_concurrente_una_cuenta`. Verificar 20 repeticiones seguidas sin fallas
- [x] 4.6 Sumar lectura y vista financiera. RED: `test_listar_secretaria_ok`, `test_listar_odontologo_sin_vinculo_403`, `test_detalle_otro_odontologo_vinculado_ok`, parametrizado `test_detalle_admin_oculta_campo` para `pieza_fdi`, `cara` y `motivo_rechazo`, `test_detalle_admin_conserva_importes`, `test_detalle_corregido_tras_aceptar_no_vigente`

## 5. Servicio de cuenta corriente (D-11, D-14, D-15)

- [x] 5.1 Crear `servicios/cuenta_servicio.py` con `obtener_cuenta`. RED en `test_c09_cuenta.py`: `test_cuenta_sin_movimientos_no_crea_filas`, `test_cuenta_paciente_inexistente_404`, `test_cuenta_paciente_baja_sin_cuenta_404`, `test_cuenta_paciente_baja_con_movimientos_ok`, `test_cuenta_con_pago_directo_refleja_saldo`
- [x] 5.2 Sumar `anular_cargo`. RED: `test_anular_crea_ajuste_opuesto`, `test_anular_no_toca_original`, `test_anular_guarda_creado_por_y_motivo`, `test_anular_dos_veces_409`, `test_anular_ajuste_409`, `test_anular_pago_409`, `test_anular_de_otra_cuenta_404`, `test_cargo_anulado_presupuesto_sigue_aceptado`, `test_cargo_anulado_expone_flag`, `test_hallazgos_con_cargo_anulado_se_presupuestan_de_nuevo`
- [x] 5.3 Probar la anulación concurrente. RED en `test_c09_concurrencia.py`: `test_doble_anulacion_concurrente_un_contramovimiento`. Verificar 20 repeticiones seguidas sin fallas

## 6. API (D-03, D-09, D-15, D-19, D-20)

- [x] 6.1 Crear `api/presupuestos.py` y registrarlo en `main.py`; sumar el prefijo en `test_routers.py`. RED en `test_c09_api.py`: alta `201`, ítem sin hallazgo `422`, listado sin paciente `422`, detalle `200` y `404`, `PUT` `200` y `409`, `presentar`, `aceptar`, `rechazar` y `baja` con sus códigos, `test_delete_405`, `test_sin_bearer_401`
- [x] 6.2 Crear `api/cuentas.py` y registrarlo en `main.py`. RED: `GET` `200` y `404`, `test_put_y_patch_cuenta_405`, `test_post_movimientos_404`, `anular` `201`, `409` y `422`, `test_sin_bearer_401`
- [x] 6.3 Matriz RBAC parametrizada por rol y endpoint. RED en `test_c09_rbac.py`: secretaria y admin sin escritura `403`, secretaria no anula `403`, odontólogo en `/cuentas` `403`, y `test_no_existe_ruta_de_cobro` recorriendo `app.routes`
- [x] 6.4 Extender el control de PHI. RED en `test_c09_sin_phi.py`: operaciones exitosas y con `422` y `409` con marcadores en los motivos sin rastro en `caplog`, y mensajes de error sin el marcador
- [x] 6.5 Flujo 3 de punta a punta. RED en `test_c09_flujo3.py`: turno → historia → hallazgo → presupuesto → presentar → aceptar → saldo → anular → saldo cero, y variante con rechazo sin movimientos (PG real)

## 7. Frontend compartido (D-21)

- [x] 7.1 Crear `shared/moneda.ts` y sus tests: RED `formatea texto decimal en es-AR`, `negativo`, `cero`. Verificar con Vitest
- [x] 7.2 Extraer `pedir`, `errorDe` y `detalleDe` a `shared/api-json.ts` con test propio y migrar `odontograma/api.ts`. Verificar que todos los tests de odontograma siguen verdes sin modificarlos

## 8. Frontend de presupuestos (D-21; usar `design-system/tokens.css`)

- [x] 8.1 Crear `features/presupuestos/{tipos,api}.ts` con guardas de tipo, sin `any`. RED en `api.test.ts`: crear, listar, detalle, reemplazar, presentar, aceptar, rechazar con motivo en el cuerpo, respuesta con forma inesperada, `409` con mensaje del servidor
- [x] 8.2 Crear `PresupuestoForm.tsx`: elegir hallazgos activos por pieza y cara, tratamiento y cantidad. RED: `solo ofrece hallazgos activos`, `sin ítems no envía`, `total del servidor tras guardar`, `muestra error de API`
- [x] 8.3 Crear `PresupuestoDetalle.tsx` y `PresupuestosPanel.tsx`: lista, detalle, acciones por estado, rechazo con motivo. RED: `estado con texto`, `secretaria sin controles`, `solo autor ve acciones`, `rechazo sin motivo no envía`, `409 mantiene la pantalla`, `hallazgo no vigente visible`, `admin sin pieza`
- [x] 8.4 Integrar en `OdontogramaPage` con `lazy` y crear `styles/presupuestos.css` solo con variables de `tokens.css`. RED: `odontologo y secretaria ven presupuestos`, `sin historia no se ofrece`. Sumar `sin-consola.test.ts`. Verificar los tests de odontograma en verde y que el CSS no tenga colores literales

## 9. Frontend de cuenta corriente (D-21; usar `design-system/tokens.css`)

- [x] 9.1 Crear `features/cuenta-corriente/{tipos,api}.ts`. RED en `api.test.ts`: consultar, anular con motivo en el cuerpo, forma inesperada, `403`
- [x] 9.2 Crear `CuentaPage.tsx` y `AnularModal.tsx` (`role="dialog"`, como `CancelarModal`). RED: `debe`, `sin deuda`, `saldo a favor`, `sin movimientos`, `anulado visible`, `secretaria sin anular`, `admin anula con motivo`, `anular sin motivo no envía`, `abre presupuesto en lectura`
- [x] 9.3 Integrar en `TurnoCard`, `AgendaPage` y `App.tsx` (`alAbrirCuenta`, página `cuenta`, `RequireRole`) y crear `styles/cuenta-corriente.css` con tokens. RED: `secretaria y admin ven el acceso`, `odontologo no lo ve`. Sumar `sin-consola.test.ts`. Verificar `tsc` limpio y `vite build` correcto

## 10. Integración

- [x] 10.1 Correr la suite completa de backend y frontend contra PG real, `alembic heads` (solo `006_presupuestos_cc`) y `openspec validate c-09-presupuestos-cuenta-corriente --strict`. Comparar el conteo contra la línea base de 1.1
- [x] 10.2 Revisión manual con la API y Vite levantados: odontólogo arma, presenta y acepta; secretaria ve la deuda; admin anula. Confirmar en DevTools que no hay PHI en consola ni en URLs
  - **Evidencia (2026-10-30, Playwright MCP sobre navegador real, API uvicorn + Vite + PG16/Redis7 de compose, DB temporal `turnos_ui` migrada con Alembic hasta `006_presupuestos_cc`, datos ficticios; capturas en `verify/01..09-*.png`).**
  - Verificado: (1) odontólogo abre historia, registra hallazgo 16 oclusal caries, arma el presupuesto (Obturación simple, total del servidor `$ 18.000,00`), presenta y acepta (01, 02, 03); en la agenda NO ve "Cuenta corriente". (2) Secretaria ve en la agenda "Cuenta corriente", "El paciente debe $ 18.000,00", abre el presupuesto en lectura y no tiene botón Anular (04, 05). (3) Admin ve el presupuesto sin pieza/cara/motivo (06); Confirmar sin motivo no envía ninguna request (07); anula con motivo (`POST .../anular` 201) y queda "sin deuda", con el cargo tachado "Anulado" y el ajuste con su motivo (08, 09).
  - Viewports: 1440x900 y 390x844 (sin scroll horizontal, `scrollWidth == clientWidth` = 390). Capturas a 390: 03, 05, 09; a 1440: 01, 02, 04, 06, 07, 08.
  - Consola y red: 0 errores nuevos de C-09. Únicos 2 errores, preexistentes y ajenos: `GET /favicon.ico` 404 (el repo no tiene favicon) y `POST /auth/refresh` 401 al cargar sin sesión (comportamiento esperado del cliente de auth). Ninguna request falló (todas 2xx). URLs/queries solo con ids opacos (`paciente_id=1`, `/cuentas/1`, `/presupuestos/1`, `/movimientos/1/anular`); ni hallazgo, pieza, motivo ni datos del paciente en consola ni en URLs (el motivo viaja en el cuerpo del POST).
  - NO verificado en navegador: rechazo con motivo y respuesta 409 en pantalla; edición de ítems de un borrador; vista del admin dentro del panel de presupuestos del odontograma; odontólogo a 390x844 durante el armado (solo el estado aceptado a 390); acceso directo por URL a la cuenta (la SPA navega por estado, sin rutas); estados de saldo a favor y de varios movimientos. Los cubren los tests de Vitest y de backend.
  - Observaciones ajenas a C-09, sin tocar: la barra de navegación global está sin estilos; los horarios de la agenda se muestran en UTC (15:00 para un turno de las 12:00 de Buenos Aires); el aviso de alergias es `position: sticky` y se superpone en las capturas de página completa (artefacto de la captura, no del layout); `GET /health` devuelve `postgres: down` con la DB temporal (no investigado).

## Desviaciones documentadas del ciclo TDD

- **RED reemplazado por mutación (6.3 RBAC, 6.4 PHI, 6.5 flujo 3).** Esos tests se escribieron sobre código ya existente y nunca se vieron fallar. Se compensó con mutaciones temporales, revertidas y confirmadas por `sha1sum`:
  | Mutación | Test que falla |
  |---|---|
  | `AnulacionCuentaDep` admite también `secretaria` | `test_c09_rbac.py::test_secretaria_no_anula_403_y_nada_cambia` (falla con `MissingGreenlet` del camino 403 sin guard, no con un assert de estado) |
  | Endpoint `aceptar` con `LecturaPresupuestoDep` en vez de `EscrituraClinicaDep` | `test_c09_rbac.py::test_secretaria_y_admin_sin_escritura_403[POST-/presupuestos/1/aceptar-None-sec]` y `[...-admin]` |
  | Log con el `motivo` en `rechazar` (`logging`) | `test_c09_sin_phi.py::test_flujo_de_presupuestos_no_loguea_motivos` y `test_codigo_de_presupuestos_y_cuentas_no_usa_logging_ni_print` |
  | `sys.stderr.write(motivo)` en `rechazar` | `test_flujo_de_presupuestos_no_loguea_motivos` |
  | `sys.stderr.write` con pieza/caries/paciente en `aceptar` | SOBREVIVIÓ al test original (solo buscaba marcadores de motivos). Se reforzó el test con `CLINICOS` (caries, ausente, oclusal, mesial, pieza, hallazgo, pieza_fdi) y la mutación ahora falla en `test_flujo_de_presupuestos_no_loguea_motivos` |
  | `aceptar` sin crear el cargo | `test_c09_flujo3.py::test_flujo3_presupuesto_cuenta_corriente_y_anulacion` |
- **4.5, 5.3 (concurrencia) y 8.4 ("sin historia no se ofrece"): sin historia RED registrada** en el apply original; no se reconstruye. 4.5 y 5.3 se compensan con los tests decisivos de bloqueo de abajo (mutación `with_for_update` quitado: ambos fallan). 8.4 queda sin RED ni mutación específica; lo respalda la verificación manual de 10.2 (con historia) y el test de Vitest.
- **Tests decisivos de `FOR UPDATE`** (`test_c09_concurrencia.py`, 20 repeticiones cada uno, PG real, dos sesiones): `test_aceptar_espera_el_lock_de_la_fila_hasta_que_se_libera` y `test_anular_cargo_espera_el_lock_del_movimiento_hasta_que_se_libera`. La sesión A retiene `FOR KEY SHARE` (no `FOR UPDATE`) sobre la fila: ese modo no choca con el UPDATE de columnas no clave ni con el FK de los INSERT de B, pero sí con `FOR UPDATE`; con `FOR UPDATE` en A, B esperaría por el UPDATE/FK aunque se quitara el bloqueo y el test no sería decisivo. Se confirma la espera con `pg_blocking_pids` (sin `sleep` fijo, límite de 5 s). Mutación: quitar `.with_for_update()` de `presupuesto_repo.get_para_actualizar` y de `cuenta_repo.movimiento_para_actualizar` hace fallar ambos tests; restaurado.

## Workflow follow-up

- [x] Correr `tp-verify-docker` en modo `full`, con permiso explícito para Docker. Overlay ya actualizado: `.claude/skills/tp-verify-docker/references/tp-turnos-config.md` lista `006_presupuestos_cc`; no se tocó en el archive.
- [x] Al archivar: marcar C-09 en `CHANGES.md`, sumar la migración `006`, `presentar`, `baja` y `anular` al Scope, y agregar la fila de cuenta corriente en `knowledge-base/03_actores_y_roles.md`.
- [x] Registrar para C-10 el contrato de D-16 (nota en la sección [C-10] de `CHANGES.md`).
