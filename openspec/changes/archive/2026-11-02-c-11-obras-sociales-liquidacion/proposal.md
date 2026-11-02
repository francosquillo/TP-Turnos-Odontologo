# Proposal — c-11-obras-sociales-liquidacion

## Why

El consultorio no puede saber qué cubre la obra social antes de cobrar, ni presentar y
cobrar una liquidación sin planillas (US-040, US-041, RN-OS-01..03, Flujo 5). C-04, C-09 y
C-10 ya están archivados: falta el catálogo de nomenclador, la cobertura sobre el presupuesto
y el ingreso en caja que C-10 dejó como contrato (`CHANGES.md`, D-20).

Leer antes: `knowledge-base/03_actores_y_roles.md` (matriz),
`04_modelo_de_datos.md` (ObraSocial/Plan/Arancel/Liquidacion), `05_reglas_de_negocio.md`
(RN-OS-01..03), `06_funcionalidades.md` (US-040, US-041), `07_flujos_principales.md`
(Flujo 5).

## What Changes

- Catálogo administrable: obras sociales, planes y aranceles versionados por vigencia, sin
  superposición por plan y código. Baja lógica; un arancel no cambia de precio.
- Plan del paciente: `paciente.plan_id` y `PUT /pacientes/:id/plan`.
- Seed "OS Ficticia Demo" con planes, aranceles y códigos de nomenclador en los tratamientos.
- `GET /validador-cobertura`: muestra cubierto y a cargo con el arancel vigente, en monto y
  en porcentaje.
- Al aceptar un presupuesto de un paciente con plan, se congela la cobertura de cada ítem y
  se registra un `ajuste` negativo que reduce el pendiente. Si lo deja en 0, el presupuesto
  pasa a `cobrado`. Sin plan, `aceptar` funciona igual que hoy.
- Anular un cargo revierte también su `ajuste` de cobertura, y responde `409` si alguna
  prestación del presupuesto ya está en una liquidación.
- Liquidaciones por OS y período: `borrador → presentada → cobrada`. Cada prestación se
  liquida una sola vez, y la que no tiene arancel queda marcada para revisión manual.
- Exportación CSV y PDF, sincrónica, por el volumen de una OS por mes.
- Cobro de la liquidación: ingreso en la caja de hoy, una sola vez y sin recibo, con el
  control de caja de C-10. Reversión con motivo en la caja de hoy.
- **BREAKING (interno)**: `movimiento_caja.recibo_id` pasa a nulable, con `liquidacion_id` y
  un CHECK que exige exactamente una referencia. El stub `GET /os` se reemplaza por
  `/obras-sociales`.
- `GET /caja` suma los ingresos de liquidaciones, y la pantalla de Caja los muestra.
- Registrar un ingreso es parte de la liquidación: **no habilita a admin a cobrar por
  `/caja`**.
- Frontend mínimo: pantalla de Liquidaciones, panel de cobertura en la cuenta corriente e
  ingresos en Caja. El catálogo se administra por API y seed.

## Capabilities

### New Capabilities

- `obras-sociales`: catálogo de OS, planes y aranceles versionados, y validador de cobertura.
- `liquidaciones`: generación por OS y período, estados, revisión manual, exportación, cobro
  en caja y reversión.

### Modified Capabilities

- `caja`: ingreso de liquidación sin recibo, su reversión y su lugar en la consulta y la
  pantalla.
- `presupuestos`: cobertura congelada al aceptar y paso a `cobrado` cuando la cobertura salda
  el pendiente.
- `cuenta-corriente`: `ajuste` de cobertura, su reversión al anular el cargo y el contrato
  sobre quién puede marcar `cobrado`.
- `core-models-identidad-pacientes`: plan del paciente y seed de obra social ficticia.

## Impact

- **Backend**: migración `008_obras_sociales`; modelos `obra_social`, `caja`, `presupuesto`,
  `paciente`; nuevos repos y servicios de cobertura, obras sociales y liquidaciones; routers
  `obras_sociales`, `liquidaciones`, `validador_cobertura`, `pacientes` y `caja`; seed.
- **Refactor acotado**: `aceptar`, `anular_cargo`, `cobrar` (extrae el paso a `cobrado`) y una
  entrada pública al control de caja.
- **Dependencia nueva**: `reportlab`, que obliga a reconstruir las imágenes de `api` y
  `worker`. No toca el worker.
- **Tests existentes por ajustar**: los que fijan la cabeza de Alembic en `007_caja_recibos`,
  la lista de migraciones de `test_c05_reserva_pg.py`, `test_routers.py` por `/os`, y los
  tests de caja si cambian la respuesta de `GET /caja`.
- **Frontend**: `features/liquidaciones`, `features/caja`, `features/cuenta-corriente`,
  `App.tsx`.
- **Docs al archivar**: `CHANGES.md` y `knowledge-base/04` y `07`, según `design.md`.
- **Fuera de alcance**: multi-sede, pagos reales, AFIP, débitos parciales de la OS, pantalla
  de ABM del nomenclador, importación de nomenclador.
