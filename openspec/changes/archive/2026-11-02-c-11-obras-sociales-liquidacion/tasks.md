# Tasks — c-11-obras-sociales-liquidacion

> **Governance MEDIO**: estas tasks asumen las recomendaciones de D-02, D-03, D-05, D-07, D-10,
> D-11, D-13 y D-16. Confirmarlas antes de empezar; si alguna cambia, actualizar specs, design
> y tasks.
>
> **TDD estricto**: en cada task, primero el test en RED por la razón esperada, después el
> mínimo código en GREEN. Postgres real para constraints y concurrencia, `freezegun` para
> tiempos. Cada task dura 2 h como máximo.
>
> Antes de tocar `aceptar`, `anular_cargo`, `cobrar` o `GET /caja`, capturar el baseline de los
> tests de C-09 y C-10. Si alguno falla, frenar y reportar. **(R)** marca lo recortable.

## 1. Migración y modelos

- [x] 1.1 RED `test_c11_migracion.py`: `008_obras_sociales` es la única cabeza, encadenada a `007_caja_recibos`; DDL igual a los modelos; upgrade y downgrade sin datos. Actualizar los tests de cabeza de C-08, C-09 y C-10 y la lista de `test_c05_reserva_pg.py`. Verificar RED por migración ausente.
  > RED y GREEN de los tests estáticos (cabeza 008 sobre 007, nombres del modelo en la migración, literales) ejecutados y en verde; cabezas de C-08/C-09/C-10 y lista de test_c05 actualizadas. Ejecutado en Postgres 16 y en verde (verify 2026-11-02): upgrade/downgrade contra Postgres (`test_c11_migracion.py`).
- [x] 1.2 GREEN modelos `obra_social.py` (`ObraSocial`, `Plan`, `Arancel` con EXCLUDE) con migración. RED `test_c11_modelos.py`: superposición, precio mayor a cero, unicidad de plan por OS, rangos abiertos. Verificar que pasa contra Postgres.
  > Modelos y migración escritos. Ejecutado en Postgres 16 y en verde (verify 2026-11-02): `test_c11_modelos.py` (requiere Postgres).
- [x] 1.3 Agregar `paciente.plan_id`, `presupuesto.plan_id`, `item_presupuesto.arancel_id` y `cubierto`, con FK indexadas. Test: columnas nulas por defecto y FK RESTRICT; suite C-02, C-09 en verde.
  > Columnas, FK e índices en modelos y migración. Ejecutado en Postgres 16 y en verde (verify 2026-11-02): tests contra Postgres (`test_c11_modelos.py`).
- [x] 1.4 Modelo `liquidacion.py` (`Liquidacion`, `ItemLiquidacion`). Tests: período con día 1, UNIQUE por `item_presupuesto_id`, monto 0 sin arancel, estado fuera de catálogo.
  > Modelo escrito; Ejecutado en Postgres 16 y en verde (verify 2026-11-02): `test_c11_modelos.py` (Postgres).
- [x] 1.5 `movimiento_caja` (D-14). Tests: CHECK de una referencia con 0 y 2 referencias, índices por signo, recibos existentes válidos tras migrar, triggers intactos, downgrade falla con ingreso. Suite `test_c10_modelos.py` en verde.
  > Modelo y migración escritos; Ejecutado en Postgres 16 y en verde (verify 2026-11-02): `test_c11_modelos.py` y la suite `test_c10_modelos.py` (Postgres).
- [x] 1.6 `uq_movimiento_cobertura_presupuesto` en modelo y migración. Test: segundo `ajuste` de cobertura rechazado; el contramovimiento con `anula_a_id` no choca.
  > Índice en modelo y migración; Ejecutado en Postgres 16 y en verde (verify 2026-11-02): `test_c11_modelos.py::test_segundo_ajuste_de_cobertura_rechazado_y_contramovimiento_permitido` (Postgres).

## 2. Catálogo y plan del paciente

- [x] 2.1 RED esquemas (`extra='forbid'`, precio no editable, rangos) y repo `obra_social_repo.py`: `arancel_vigente(plan, codigo, fecha)` con bordes de vigencia inclusivos. GREEN verificado con `test_c11_repos.py`.
  > Esquemas verificados (`test_c11_esquemas.py`, 22 passed). Ejecutado en Postgres 16 y en verde (verify 2026-11-02): `test_c11_repos.py` (Postgres).
- [x] 2.2 `servicios/cobertura_servicio.py`: regla pura de D-04. Tests con arancel menor, igual y mayor, cantidad mayor a 1, centavos y precio 0.
- [x] 2.3 Servicio y router de OS y planes en `/obras-sociales`, `/planes`. Quitar stub `/os` y actualizar `test_routers.py`. Tests API: alta, nombre repetido `409`, baja lógica, roles.
  > Router y servicio escritos, stub `/os` quitado y `test_routers.py` actualizado (en verde); 401/403 verificados en `test_c11_rbac.py`. Ejecutado en Postgres 16 y en verde (verify 2026-11-02): `test_c11_api.py` (alta, 409, baja lógica; Postgres).
- [x] 2.4 Router `/aranceles`: POST, PATCH solo `vigencia_hasta`, lecturas. Tests: superposición `409`, precio `422`, autor y fecha de cierre, sin DELETE, roles.
  > Router escrito; 401/403 verificados (`test_c11_rbac.py`). Ejecutado en Postgres 16 y en verde (verify 2026-11-02): `test_c11_api.py` (superposición, cierre, autor; Postgres).
- [x] 2.5 `PUT /pacientes/:id/plan`. Tests de los 5 escenarios de la spec, con el stub GET intacto.
  > Ruta escrita; 401/403 verificados. Ejecutado en Postgres 16 y en verde (verify 2026-11-02): `test_c11_api.py` (Postgres).
- [x] 2.6 `GET /validador-cobertura`. Tests de los 7 escenarios, con `freezegun` para la vigencia; verificar que no crea filas.
  > Ruta escrita; 401/403 verificados. Ejecutado en Postgres 16 y en verde (verify 2026-11-02): `test_c11_api.py` (7 escenarios; Postgres).
- [x] 2.7 Seed (D-21). Tests: doble corrida sin duplicar, código existente sin pisar, `EXT-001` sin arancel, sin secretos.
  > Seed escrito; tests estáticos en verde (`test_c11_seed.py`: sin secretos, tablas de datos válidas). Ejecutado en Postgres 16 y en verde (verify 2026-11-02): idempotencia y cobertura contra Postgres.

## 3. Cobertura en presupuesto y cuenta

- [x] 3.1 Refactor: extraer `saldar_si_corresponde` de `cobrar()` a `presupuesto_servicio`. Verificar suite C-10 en verde, sin cambiar tests.
  > Refactor hecho (`saldar_si_corresponde`). Ejecutado en Postgres 16 y en verde (verify 2026-11-02): suite C-10 contra Postgres (no se pudo capturar baseline de C-09/C-10: 670 tests se saltan sin Postgres).
- [x] 3.2 RED `test_c11_aceptar.py`: congelar plan, arancel y `cubierto`; ítem sin arancel; plan inactivo; `decidido_at` a las 23:30 en Buenos Aires. GREEN en `aceptar`, con el paciente sin plan idéntico a hoy.
  > Escrito (`test_c11_aceptar.py`, `aceptar`). Ejecutado en Postgres 16 y en verde (verify 2026-11-02) (Postgres).
- [x] 3.3 `ajuste` de cobertura en el savepoint del cargo: pendiente reducido, cobro limitado a lo pendiente, sin ajuste con cubierto 0, atomicidad ante fallo, aceptación con caja pendiente. Verificar con `test_c11_aceptar.py`.
  > Escrito. Ejecutado en Postgres 16 y en verde (verify 2026-11-02) (Postgres).
- [x] 3.4 Cobertura total: `cobrado` sin recibo y fuera de `pendientes`. Actualizar el docstring y `test_c09_rbac` solo si la spec modificada lo exige.
  > Escrito (cobertura total pasa a `cobrado` vía `saldar_si_corresponde`); docstrings de specs sin cambios de código. Ejecutado en Postgres 16 y en verde (verify 2026-11-02) (Postgres).
- [x] 3.5 `anular_cargo` (D-06): contramovimiento de cobertura en la misma transacción; saldo `0.00`; con pagos, saldo a favor correcto; `409` con ítem liquidado. Suite C-09 en verde.
  > Escrito (`test_c11_anular_cargo.py`). Ejecutado en Postgres 16 y en verde (verify 2026-11-02) (Postgres).

## 4. Liquidaciones

- [x] 4.1 RED `test_c11_liquidacion.py`, repo y `generar`: selección por OS, período y plan, cargo anulado excluido, bordes de mes en Buenos Aires, total calculado. Verificar GREEN contra Postgres.
  > Repo y `generar` escritos; funciones puras verificadas (`test_c11_liquidacion.py`). Ejecutado en Postgres 16 y en verde (verify 2026-11-02): selección y totales contra Postgres.
- [x] 4.2 Filas en revisión y regeneración: arancel retroactivo no libera; prestación ya liquidada `409`; prestación nueva crea otra liquidación; plan cambiado conserva el congelado.
  > Escrito. Ejecutado en Postgres 16 y en verde (verify 2026-11-02) (Postgres).
- [x] 4.3 `presentar` y `descartar`: transiciones, `409`, liberación de prestaciones, anular cargo tras descartar.
  > Escrito. Ejecutado en Postgres 16 y en verde (verify 2026-11-02) (Postgres).
- [x] 4.4 `caja_para_movimiento` pública y `cobrar` (D-12): orden de locks, apertura implícita, caja pendiente, cerrada, borrador, total 0, doble cobro, fallo parcial. Suite C-10 en verde.
  > `caja_para_movimiento` y `cobrar` escritos. Ejecutado en Postgres 16 y en verde (verify 2026-11-02): `test_c11_cobro.py` y suite C-10 (Postgres).
- [x] 4.5 **(R)** `revertir-cobro` (D-13): caja de hoy, medio original, caja cerrada intacta, motivo obligatorio, doble reversión, cobrar tras revertir.
  > Escrito (R). Ejecutado en Postgres 16 y en verde (verify 2026-11-02) (Postgres).
- [x] 4.6 `test_c11_concurrencia.py`: doble generación y doble cobro en dos sesiones reales; un solo resultado de cada uno.
  > Escrito (`test_c11_concurrencia.py`). Ejecutado en Postgres 16 y en verde (verify 2026-11-02) (Postgres).
- [x] 4.7 Router `/liquidaciones` y RBAC: lista, detalle, odontólogo filtrado **(R)**, secretaria `403`, `401`; admin sigue con `403` en `POST /caja/cobrar` y `POST /caja/cierre`.
  > Router escrito; RBAC 401/403 y superficie de rutas verificados sin DB (`test_c11_rbac.py`, 52 passed). Ejecutado en Postgres 16 y en verde (verify 2026-11-02): lista/detalle/odontólogo filtrado (Postgres).
- [x] 4.8 `GET /caja` con `ingresos_liquidacion` (D-15): signo, sin datos de pacientes, cierre que lo incluye, medio en desglose. Tests C-10 actualizados por el campo nuevo.
  > `ingresos_liquidacion` escrito. Ejecutado en Postgres 16 y en verde (verify 2026-11-02): `test_c11_cobro.py` (Postgres).
- [x] 4.9 Sin PHI: `test_c11_sin_phi.py` con motivo marcador fuera de logs y errores fijos.
  > Defensas estáticas verificadas (`test_c11_sin_phi.py`: sin logging, sin campos clínicos, query params). Ejecutado en Postgres 16 y en verde (verify 2026-11-02): el test con `caplog` sobre HTTP real (Postgres).

## 5. Exportación

- [x] 5.1 `liquidacion_export.py`: modelo de filas por plan con subtotales. Tests con datos en memoria que no incluyen pieza, hallazgo ni notas.
- [x] 5.2 CSV: separador, BOM, inyección de fórmulas, total igual a la liquidación. Ruta `export.csv` con adjunto y `403` por rol.
  > CSV verificado con datos en memoria (BOM, separador, fórmulas, total). Ejecutado en Postgres 16 y en verde (verify 2026-11-02): ruta `export.csv` con adjunto (Postgres); el 403 por rol sí verificado.
- [x] 5.3 **(R)** PDF: agregar `reportlab` a `requirements.txt` y verificar la versión instalada; Platypus con subtotales y leyenda; `asyncio.to_thread`. Test: empieza con `%PDF`, con adjunto `application/pdf`.
  > `reportlab==5.1.0` agregado a `requirements.txt` (instalado: 5.1.0) y PDF verificado con datos en memoria (`%PDF`, subtotales, total). Ejecutado en Postgres 16 y en verde (verify 2026-11-02): ruta `export.pdf` con adjunto (Postgres).

## 6. Frontend

- [x] 6.1 `features/liquidaciones/api.ts` y `tipos.ts`, con guardas y descarga por `Blob`. Tests de `api.test.ts` y `sin-consola.test.ts`.
- [x] 6.2 Pantalla: lista, generar y detalle por plan con revisión indicada por texto. Tests de componentes.
- [x] 6.3 Acciones: presentar, descartar, cobrar con medio, exportar, y revertir **(R)**. Test: `409` sin perder el medio; odontólogo solo lectura **(R)**; secretaria sin pantalla.
- [x] 6.4 Navegación en `App.tsx`. Test de visibilidad por rol.
- [x] 6.5 `PanelCobertura` en cuenta corriente: plan y validador. Tests con los tres estados y sin aritmética de dinero en el cliente.
- [x] 6.6 Ingresos en `CajaPage`, con guardas en `api.ts`. Tests: lista aparte de recibos; día sin ingresos.

## 7. Cierre

- [x] 7.1 Test E2E del Flujo 5, `test_c11_flujo5.py`: plan, aceptar, cobrar a cargo, generar, presentar, exportar, cobrar y cerrar caja, con saldo y totales exactos.
  > Escrito (`test_c11_flujo5.py`). Ejecutado en Postgres 16 y en verde (verify 2026-11-02) (Postgres).
- [x] 7.2 Corregir `knowledge-base/04` (plan del paciente, prestación, snapshot) y `07` (revisión y reversión). Verificar con `git diff` que coinciden con `design.md`.
- [x] 7.3 Verify completo con `tp-verify-docker` modo `full`, previo permiso explícito del usuario para iniciar Docker Desktop y con `docker compose build` por `reportlab`: alembic, pytest, frontend y `openspec validate --all --strict` en verde.
  > Verify full #2 (2026-11-02), una sola corrida: backend 1344/1344 sin reintentos, vitest 396/396, tsc y build OK, `docker compose build api` OK (reportlab), migración limpia 001→008, seed idempotente, `openspec validate --all --strict` 13/13.
