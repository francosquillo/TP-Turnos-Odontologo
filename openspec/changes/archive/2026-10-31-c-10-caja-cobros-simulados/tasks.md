# Tasks — c-10-caja-cobros-simulados

> **Governance CRITICO**: el usuario aprobó el 2026-10-31 D-05, D-06, D-07, D-08, D-09, D-12,
> D-13, D-15, D-16, D-18, D-19 y D-25. Si alguna decisión cambia, actualizar specs, design y
> tasks antes de empezar.
>
> Convención TDD estricta: cada task empieza con un test en fallo por la razón esperada
> (RED), sigue con el mínimo código (GREEN), triangula con al menos un caso distinto y
> termina con REFACTOR en verde. Chunks ≤ 2 h, en orden de dependencias. Constraints,
> triggers y concurrencia siempre contra **Postgres real** del compose, NUNCA SQLite.
> `freezegun` para el día operativo. Nombres `test_<unidad>_<escenario>_<resultado>` (AAA).
> Datos 100% ficticios. Sin PHI en logs. Esquemas `extra='forbid'`. Dinero en
> `NUMERIC`/`Decimal`, y texto en el frontend. TS sin `any`.
>
> Docker: pedir permiso explícito antes de iniciar Docker Desktop y levantar `db+redis`;
> bajarlos al cerrar (reglas duras). Puerto alternativo si PG18 ocupa 5432:
> `POSTGRES_PORT=5433` y `DATABASE_URL_TEST` acorde.
>
> Antes de tocar la DB, leer las reglas de `postgresql-table-design` y
> `supabase-postgres-best-practices`.

## 1. Modelos, triggers y migración 007 (D-01, D-02, D-03, D-14, D-15, D-25)

- [x] 1.1 Capturar la línea base: correr `pytest` y los tests de frontend, anotar el conteo y reportar sin arreglar cualquier falla previa. Verificar que `alembic heads` da solo `006_presupuestos_cc`
- [x] 1.2 Crear `modelos/caja.py` con `Caja` y `MEDIOS`, CHECK e índices de D-02, y exportar en `modelos/__init__.py`. RED en `test_c10_modelos.py` (PG real): `test_caja_fecha_duplicada_rechazada`, `test_caja_segunda_abierta_rechazada`, `test_caja_estado_desconocido_rechazado`, `test_caja_cerrada_incompleta_rechazada`, `test_caja_abierta_con_totales_rechazada`, `test_caja_diferencia_mal_calculada_rechazada`, `test_caja_diferencia_sin_motivo_rechazada`, `test_caja_contado_negativo_rechazado`
- [x] 1.3 Sumar `Recibo` (con `clave_idempotencia`, `uq_recibo_clave_idempotencia` y `ck_recibo_clave_formato`), `ReciboContador` y `MovimientoCaja`. RED: `test_recibo_numero_duplicado_rechazado`, `test_recibo_clave_duplicada_rechazada`, `test_recibo_sin_clave_rechazado`, parametrizado `test_recibo_clave_mal_formada_rechazada` (mayúsculas, UUID v1, texto libre), `test_recibo_monto_no_positivo_rechazado`, `test_recibo_anulado_sin_motivo_rechazado`, parametrizado `test_medio_fuera_de_catalogo_rechazado` para `recibo` y `movimiento_caja` con `tarjeta`, `test_movcaja_monto_cero_rechazado`, `test_movcaja_reversion_sin_motivo_rechazada`, `test_movcaja_segundo_ingreso_rechazado`, `test_movcaja_segunda_reversion_rechazada`, `test_contador_id_distinto_de_1_rechazado`
- [x] 1.4 Adjuntar los triggers de D-14 con `event.listen`, una sentencia por `execute`. RED: `test_movcaja_update_rechazado`, `test_movcaja_delete_rechazado`, `test_movcaja_insert_en_caja_cerrada_rechazado`, `test_caja_delete_rechazado`, `test_caja_cerrada_update_rechazado`, `test_caja_abierta_cierre_permitido`, `test_recibo_delete_rechazado`, parametrizado `test_recibo_update_campo_protegido_rechazado` (incluye `clave_idempotencia`), `test_recibo_anular_con_cambio_de_numero_rechazado`, `test_recibo_desanular_rechazado`, `test_recibo_anulacion_valida_permitida`
- [x] 1.5 Modificar `Movimiento`: FK a `recibo`, índice, `uq_movimiento_pago_recibo` y `ck_movimiento_pago_con_recibo`. Agregar un helper `crear_recibo` a `c10_helpers.py`, que genera una `clave_idempotencia` válida. RED: `test_movimiento_recibo_inexistente_rechazado`, `test_movimiento_pago_sin_recibo_rechazado`, `test_movimiento_segundo_pago_mismo_recibo_rechazado`. Reescribir con recibo real los tests de C-09 que insertan `pago` (`test_c09_modelos.py`, `test_c09_cuenta.py`, `test_c09_repos.py`), sin debilitar sus aserciones, y reemplazar `test_movimiento_recibo_inexistente_aceptado`. Verificar `pytest -k c09` en verde
- [x] 1.6 Escribir `alembic/versions/007_caja_recibos.py` (tablas, funciones, triggers, `clave_idempotencia` con su UNIQUE y su CHECK, restricciones sobre `movimiento`, downgrade completo). RED en `test_c10_migracion.py`: `test_c10_cabeza_unica_007_sobre_006`, `test_c10_migracion_declara_checks_e_indices_del_modelo`, `test_c10_triggers_migracion_iguales_a_modelo`, `test_c10_fk_recibo_existe_tras_upgrade`, `test_c10_downgrade_upgrade_limpio` (PG real con Alembic)
- [x] 1.7 Ajustar por la cabeza nueva: `test_c09_migracion.py` (cabeza y `recibo_fk`), `test_c08_migracion.py`, `test_c07_migracion.py`, `test_c05_reserva_pg.py` (sumar `007_caja_recibos.py`), `db_utils.reset_estado_base` (sumar tablas y funciones nuevas). Actualizar la cadena Alembic en `.claude/skills/tp-verify-docker/references/tp-turnos-config.md`. Verificar los tests de migraciones C-02, C-05, C-07, C-08, C-09 y C-10 en verde

## 2. Esquemas (D-03, D-08, D-12, D-17, D-25)

- [x] 2.1 Crear `esquemas/caja.py` (`CobroIn`, `CierreIn`, `AnulacionReciboIn`, `CajaOut`, `EstadoCajaOut`, `ReciboOut`, `CobroOut`), con `medio` como `Literal`, `clave_idempotencia` obligatoria con `Field(pattern=...)`, y reutilizando `Motivo` y `Dinero`. RED en `test_c10_esquemas.py`: `test_cobro_sin_clave_invalido`, parametrizado `test_cobro_clave_mal_formada_invalida`, `test_cobro_salida_sin_clave`, `test_cobro_medio_tarjeta_invalido`, parametrizado `test_cobro_monto_invalido` (0, negativo, tres decimales), `test_cobro_campo_fecha_invalido`, `test_cobro_campo_paciente_invalido`, `test_cierre_con_total_sistema_invalido`, `test_cierre_con_diferencia_invalida`, `test_cierre_contado_negativo_invalido`, `test_anulacion_recibo_sin_motivo_invalida`, `test_importe_serializa_como_texto`
- [x] 2.2 Sumar `PendienteOut` y `pendientes` con valor `[]` a `CuentaOut`. RED: `test_cuenta_pendientes_por_defecto_vacio`, `test_pendiente_serializa_como_texto`. Verificar `test_c09_esquemas.py` sin cambios

## 3. Repos (D-08, D-10, D-11, D-17, D-22, D-25)

- [x] 3.1 Crear `repos/recibo_repo.py` con `siguiente_numero` (D-10), crear, lock, listar por fecha y `por_clave`. RED en `test_c10_repos.py` (PG real): `test_por_clave_encontrado`, `test_por_clave_inexistente_none`, `test_siguiente_numero_empieza_en_1`, `test_siguiente_numero_consecutivo`, `test_siguiente_numero_rollback_lo_devuelve`, `test_listar_por_fecha_mayor_a_menor`, `test_listar_recibo_anulado_otro_dia_queda_en_su_fecha`
- [x] 3.2 Crear `repos/caja_repo.py`: `asegurar` con `ON CONFLICT DO NOTHING` sin índice, lock, caja pendiente, suma, desglose y alta de movimiento. RED: `test_asegurar_dos_veces_una_fila`, `test_asegurar_con_otra_abierta_no_crea`, `test_pendiente_anterior_encontrada`, `test_pendiente_ignora_hoy`, `test_total_suma_ingresos_y_reversiones`, `test_desglose_por_medio`
- [x] 3.3 Sumar a `repos/cuenta_repo.py` `pendiente_de_presupuesto`, `pendientes_de_paciente` y `pago_de_recibo`. RED: `test_pendiente_cargo_menos_pagos`, `test_pendiente_repone_pago_anulado`, `test_pendiente_cero_con_cargo_anulado`, `test_pendientes_excluye_cobrado_y_saldo_no_positivo`, `test_pago_de_recibo_encontrado`

## 4. Servicio: cobro (D-04, D-05, D-06, D-08, D-09, D-11, D-15, D-25)

- [x] 4.1 Crear `servicios/caja_servicio.py` con `hoy_operativo` y `_caja_operable`. RED en `test_c10_dia.py` con `freezegun`: `test_hoy_operativo_antes_de_medianoche_local`, `test_hoy_operativo_despues_de_medianoche_local`, `test_hoy_operativo_a_las_01_utc_sigue_dia_anterior`, `test_operable_sin_caja`, `test_operable_con_pendiente_409`, `test_operable_hoy_cerrada_409`, `test_operable_hoy_abierta`
- [x] 4.2 Sumar `cobrar`: lock, validación, número, recibo con su clave, `pago`, movimiento de caja. RED en `test_c10_cobro.py`: `test_cobrar_crea_recibo_pago_y_movimiento_enlazados`, `test_cobrar_baja_el_saldo`, `test_cobrar_concepto_sin_phi`, `test_cobrar_guarda_autor`, `test_cobrar_abre_caja_con_abierta_por`, `test_cobrar_paciente_de_baja_ok`, parametrizado `test_cobrar_cada_medio_ok`
- [x] 4.3 Sumar validaciones. RED: `test_cobrar_sobrepago_422`, `test_cobrar_justo_el_pendiente_ok`, parametrizado `test_cobrar_estado_no_aceptado_409`, `test_cobrar_cargo_anulado_409`, `test_cobrar_presupuesto_inexistente_404`, `test_cobrar_presupuesto_de_baja_404`, `test_cobrar_rechazado_no_consume_numero`, `test_cobrar_falla_final_revierte_todo`
- [x] 4.4 Sumar transición a `cobrado`. RED: `test_cobrar_total_marca_cobrado`, `test_cobrar_parcial_sigue_aceptado`, `test_dos_parciales_marcan_cobrado`, `test_cobrar_fallido_no_marca_cobrado`
- [x] 4.5 Sumar el bloqueo al cobro, con `freezegun`. RED: `test_cobrar_con_pendiente_409_sin_filas`, `test_cobrar_con_caja_de_hoy_cerrada_409`, `test_cobrar_dia_sin_caja_previa_ok`, `test_cobrar_cruza_medianoche_otra_caja`, `test_numeracion_continua_entre_dias`
- [x] 4.6 Probar concurrencia con sesiones reales y `asyncio.gather`. RED en `test_c10_concurrencia.py` (PG real): `test_veinte_cobros_concurrentes_numeros_1_a_20`, `test_primer_cobro_concurrente_una_caja`, `test_sobrepago_concurrente_un_ganador`, `test_cobros_con_fallo_intercalado_sin_huecos`. Verificar 20 repeticiones seguidas sin fallas
- [x] 4.7 Sumar la idempotencia secuencial en el orden de D-25 (lectura sin lock, relectura tras el lock de la caja, antes de revalidar su estado). RED en `test_c10_idempotencia.py` y luego GREEN: `test_misma_clave_mismo_contenido_devuelve_original`, `test_misma_clave_no_crea_filas`, `test_misma_clave_no_consume_numero`, `test_misma_clave_monto_equivalente_es_reintento`, parametrizado `test_misma_clave_otro_contenido_409_sin_filas` (presupuesto, monto, medio), `test_otra_clave_mismo_contenido_crea_otro_recibo`, `test_clave_de_cobro_rechazado_sigue_libre`, `test_colision_unique_409_sin_consumir_numero`
- [x] 4.8 Sumar los reintentos tardíos, con `freezegun`. RED en `test_c10_idempotencia.py` y luego GREEN: `test_reintento_caja_cerrada_devuelve_original`, `test_reintento_con_caja_pendiente_devuelve_original`, `test_reintento_hoy_cerrada_devuelve_original`, `test_reintento_recibo_anulado_devuelve_anulado_sin_mover`, `test_reintento_presupuesto_cobrado_devuelve_original`, `test_reintento_no_abre_caja`
- [x] 4.9 Probar concurrencia con la misma clave, con sesiones reales y `asyncio.gather`. RED en `test_c10_concurrencia.py` (PG real) y luego GREEN: `test_misma_clave_concurrente_un_recibo` (un creado y un reintento, un `pago`, un movimiento de caja, contador +1), `test_misma_clave_ocho_sesiones_un_recibo`, `test_misma_clave_otro_contenido_concurrente_un_recibo`, `test_misma_clave_primero_falla_segundo_cobra`, `test_misma_clave_y_cierre_concurrentes_sin_409`, `test_claves_mixtas_numeros_consecutivos`. Verificar 20 repeticiones seguidas sin fallas

## 5. Servicio: cierre (D-07, D-11, D-12)

- [x] 5.1 Sumar `cerrar`. RED en `test_c10_cierre.py`: `test_cerrar_sin_diferencia`, `test_cerrar_calcula_total_del_servidor`, `test_cerrar_incluye_reversiones`, `test_cerrar_diferencia_sin_motivo_422_sigue_abierta`, `test_cerrar_faltante_con_motivo`, `test_cerrar_sobrante_con_motivo`, `test_cerrar_guarda_autor_y_hora`, `test_cerrar_repetido_409`, `test_cerrar_inexistente_404`
- [x] 5.2 Probar cierre de un día anterior y desbloqueo, con `freezegun`. RED: `test_cerrar_dia_anterior_conserva_fecha`, `test_cerrar_pendiente_desbloquea_cobro`, `test_caja_cerrada_hoy_no_se_reabre`
- [x] 5.3 Probar concurrencia (PG real). RED en `test_c10_concurrencia.py`: `test_doble_cierre_concurrente_un_ganador`, `test_cobro_y_cierre_total_consistente`. Verificar 20 repeticiones seguidas sin fallas

## 6. Servicio: anulación de recibo (D-09, D-13)

- [x] 6.1 Sumar `anular_recibo`. RED en `test_c10_anulacion.py`: `test_anular_crea_ajuste_opuesto_con_anula_a_id`, `test_anular_marca_recibo_conserva_numero`, `test_anular_sube_el_saldo`, `test_anular_guarda_motivo_autor_y_fecha`, `test_anular_movimiento_caja_negativo_con_medio_original`, `test_anular_concepto_fijo`, `test_anular_repetido_409`, `test_anular_inexistente_404`, `test_numero_siguiente_tras_anular`
- [x] 6.2 Sumar reglas de caja, con `freezegun`. RED: `test_anular_mismo_dia_misma_caja`, `test_anular_recibo_de_dia_cerrado_no_toca_esa_caja`, `test_anular_abre_caja_de_hoy_con_admin`, `test_anular_con_caja_pendiente_409_sin_cambios`, `test_anular_con_hoy_cerrada_409_sin_cambios`
- [x] 6.3 Sumar reversa de estado y saldo a favor. RED: `test_anular_de_cobrado_vuelve_a_aceptado`, `test_anular_de_aceptado_sigue_aceptado`, `test_cobrar_de_nuevo_tras_anular_marca_cobrado`, `test_cargo_anulado_con_pago_deja_saldo_a_favor_y_no_cobrable`, `test_devolucion_por_anular_recibo_deja_saldo_cero`, `test_cobrado_con_cargo_anulado_sigue_cobrado`, `test_anular_pago_por_ruta_c09_sigue_409`
- [x] 6.4 Probar concurrencia (PG real). RED en `test_c10_concurrencia.py`: `test_doble_anulacion_concurrente_un_contramovimiento`, `test_cobro_y_anulacion_concurrentes_sin_deadlock`. Verificar 20 repeticiones seguidas sin fallas

## 7. API, permisos y lecturas (D-16, D-17, D-22, D-23, D-25)

- [x] 7.1 Crear `api/caja.py` (`POST /cobrar`, `POST /cierre`) y registrarlo en `main.py`. RED en `test_c10_api.py`: `test_post_cobrar_201`, `test_post_cobrar_reintento_200_mismo_cuerpo`, `test_post_cobrar_otro_contenido_409`, `test_post_cobrar_sin_clave_422`, `test_post_cobrar_medio_invalido_422`, `test_post_cobrar_error_hace_rollback`, `test_post_cierre_200`, `test_post_cierre_sin_motivo_422`
- [x] 7.2 Sumar `obtener_caja` y `GET /caja`, con `freezegun`. RED: `test_get_caja_sin_movimientos_no_crea_filas`, `test_get_caja_con_desglose`, `test_get_caja_pendiente_no_operable`, `test_get_caja_hoy_cerrada_no_operable`, `test_get_caja_fecha_cerrada_con_totales`, `test_get_caja_fecha_sin_caja`
- [x] 7.3 Crear `api/recibos.py` (`GET ?fecha=`, `POST /:id/anular`) y registrarlo. RED: `test_get_recibos_del_dia`, `test_get_recibos_sin_fecha_422`, `test_post_anular_200`, `test_post_anular_sin_motivo_422`
- [x] 7.4 Sumar `pendientes` a `obtener_cuenta`. RED en `test_c10_api_cuentas.py`: `test_cuenta_pendiente_parcial`, `test_cuenta_pendiente_repuesto_tras_anular`, `test_cuenta_sin_pendiente_con_cargo_anulado`, `test_cuenta_sin_pendiente_cobrado`, `test_cuenta_sin_movimientos_lista_vacia`
- [x] 7.5 Probar la matriz RBAC completa. RED en `test_c10_rbac.py`, parametrizado por rol y ruta según D-16 (incluye `test_admin_no_cobra_403`, `test_admin_reintento_de_clave_existente_403`, `test_admin_no_cierra_403`, `test_secretaria_no_anula_403`, `test_odontologo_sin_acceso_403`, `test_sin_bearer_401`). Actualizar `test_c09_rbac.py` (rutas de cobro solo bajo `/caja` y `/recibos`, sin debilitar las de `/cuentas` y `/presupuestos`) y `test_routers.py`
- [x] 7.6 Probar sin bloqueo fuera de caja. RED en `test_c10_alcance_bloqueo.py`: `test_caja_pendiente_no_bloquea_crear_turno`, `test_caja_pendiente_no_bloquea_aceptar_presupuesto`, `test_caja_pendiente_no_bloquea_anular_cargo`
- [x] 7.7 Probar sin PHI, extendiendo el patrón de C-09. RED en `test_c10_sin_phi.py`: `test_motivo_anulacion_fuera_de_logs`, `test_motivo_diferencia_fuera_de_logs`, `test_rutas_c10_sin_datos_en_url`, `test_recibo_out_sin_campos_clinicos`
- [x] 7.8 Probar el Flujo 4 de punta a punta. RED en `test_c10_flujo4.py` (PG real): aceptar, cobrar parcial, cobrar saldo, `cobrado`, cierre con diferencia, bloqueo al día siguiente con otra caja abierta, anulación con reversión en la caja de hoy. Verificar `pytest` completo en verde

## 8. Frontend: caja (D-17, D-24, D-25)

- [x] 8.1 Crear `features/caja/tipos.ts` y `api.ts` con validadores sin `any`. RED en `api.test.ts`: `consultarCaja`, `listarRecibos`, `cobrar` (envía `clave_idempotencia` en el cuerpo, acepta `201` y `200`), `cerrarCaja`, `anularRecibo`, respuesta inválida, motivo solo en el cuerpo. Sumar `formatearFecha` por corte de texto. RED: `2026-10-31` da `31/10/2026` en cualquier zona horaria
- [x] 8.2 Crear `CajaPage` y `styles/caja.css` con tokens. RED en `CajaPage.test.tsx`: fecha y estado, desglose por medio, sin caja, bloqueo con fecha pendiente, caja cerrada con diferencia y sin acciones, error de carga
- [x] 8.3 Crear `CierreForm`. RED: envía `caja_id` y contado como texto, importe inválido no se envía, `422` pide motivo sin perder el importe, cierre exitoso refresca desde el servidor, admin no lo ve
- [x] 8.4 Crear `RecibosLista`. RED: lista con anulado y motivo, selector de fecha, admin ve Anular con `MotivoForm`, motivo vacío no se envía, secretaria sin acción, error `409` visible
- [x] 8.5 Agregar la página a `App.tsx` con `lazy` y `RequireRole`. RED: admin y secretaria entran, odontólogo no. Crear `sin-consola.test.ts` de `features/caja`. Verificar `npx tsc --noEmit` y `npx vitest run`

## 9. Frontend: cobro desde la cuenta corriente (D-24, D-25)

- [x] 9.1 Crear `CobroModal` y `ComprobanteRecibo`. RED en `CobroModal.test.tsx`: importe inválido no se envía, sin `number` en el importe, tres medios simulados, botón deshabilitado al enviar, `422` y `409` visibles, comprobante con número y leyenda de pago simulado
- [x] 9.2 Sumar la clave de D-25 a `CobroModal`. RED en `CobroModal.test.tsx` y luego GREEN: una clave UUID v4 por apertura, reintento con la misma clave tras fallo de red y tras `500`, importe y medio congelados tras un resultado incierto, Cerrar refresca la cuenta, `4xx` vuelve a habilitar los campos y conserva la clave, otra apertura genera otra clave, `200` muestra el comprobante igual que `201`, recibo devuelto anulado se indica con texto
- [x] 9.3 Modificar `CuentaPage` y tipos con `pendientes`, para secretaria con `Promise.all` de cuenta y caja. RED en `CuentaPage.test.tsx`: secretaria ve Cobrar por pendiente, cobro exitoso refresca saldo y pendientes, caja bloqueada deshabilita con texto, falla de caja no rompe la cuenta, admin sin Cobrar. Mantener verdes los tests previos
- [x] 9.4 Sumar anular recibo en `CuentaPage` con `MotivoForm`. RED: admin ve Anular en `pago` no anulado, no en uno anulado, secretaria sin acción, motivo vacío no se envía, éxito refresca desde el servidor, `409` visible. Verificar `npx tsc --noEmit`, `npx vitest run` y `npm run build`

## 10. Cierre documental e integración

- [x] 10.1 Terminar la KB según "Diferencias" de `design.md`: PDF en `02`; cierres en `08`
- [x] 10.2 Ejecutar `openspec validate c-10-caja-cobros-simulados --strict` y `pytest` más `vitest` completos, y revisar la lista de reglas duras de `tp-turnos-config.md` (Docker con permiso explícito previo)

## Workflow follow-up

- Verify en modo `full` con `tp-verify-docker`, con permiso explícito para usar Docker.
- Tras verify en verde, y a pedido del usuario, archivar el change y marcar `[x]` C-10 en `CHANGES.md`.
- Commit solo a pedido explícito, con commits convencionales.
