# Proposal — c-10-caja-cobros-simulados (C-10 `caja-cobros-simulados`)

> Nota de nombre: el change canónico en `CHANGES.md` es `C-10 caja-cobros-simulados`.
> El CLI `openspec` exige kebab-case minúsculas, por eso el directorio es
> `openspec/changes/c-10-caja-cobros-simulados/`.
>
> **Governance CRITICO**: no se escribe código sin aprobación humana explícita de las
> decisiones de `design.md`. Las doce se aprobaron el 2026-10-31.

## Why

C-09 dejó la deuda visible, pero nadie puede cobrarla: no existen pagos, recibos ni
caja, y ningún presupuesto llega a `cobrado`. Este change cierra el Flujo 4 y el camino
crítico turno → clínica → cobro (US-031; RN-CO-01, RN-CO-02, RN-CO-04), y usa el
contrato de C-09 (D-16). GATE 6 está abierto: C-09 está archivado.

## What Changes

- Modelos nuevos: `Caja`, `MovimientoCaja`, `Recibo` y el contador de numeración.
- Migración `007_caja_recibos` sobre `006_presupuestos_cc`. Agrega la FK e índice de
  `movimiento.recibo_id`, obliga a que un `pago` nazca con recibo y agrega la clave de
  idempotencia de `recibo`, con UNIQUE y CHECK de formato.
- Cobro simulado con `efectivo`, `transferencia` o `tarjeta_simulada`, sin integración
  con terceros. Un cobro genera, en una sola transacción, recibo + `pago` en la cuenta
  corriente + movimiento de caja.
- Cobro imputado a un presupuesto, total o parcial, sin sobrepago. Saldado el importe,
  el presupuesto pasa a `cobrado`.
- Cobro idempotente (D-25): el cliente envía una clave. Repetirla
  con el mismo contenido devuelve el recibo original, sin filas nuevas ni número nuevo; con
  otro contenido responde `409`.
- Recibos con numeración consecutiva sin huecos, también ante rollbacks y concurrencia.
- Cierre diario con `total_sistema` calculado por el servidor, `total_contado`
  declarado, y motivo obligatorio si hay diferencia.
- Una caja sin cerrar de un día anterior bloquea cobrar y anular recibos hasta cerrarla
  (`409`). Agenda, clínica y presupuestos siguen funcionando.
- Anulación de recibo por contramovimiento con motivo. El número se conserva, y una caja
  cerrada no se modifica: la reversión cae en la caja del día.
- Endpoints: `POST /caja/cobrar`, `POST /caja/cierre`, `POST /recibos/:id/anular`.
- Frontend `features/caja`, y cobro y anulación de recibos desde la cuenta corriente,
  con tokens de `design-system/`.

**Agregados respecto de `CHANGES.md`** (ver `design.md`, sección de diferencias):
`GET /caja`, `GET /recibos?fecha=` y el campo `pendientes` de `GET /cuentas/:paciente_id`.
Sin ellos la pantalla no puede mostrar el bloqueo, los totales ni qué se puede cobrar.

**Fuera de alcance**: pagos reales, MercadoPago y AFIP; PDF del recibo; egresos de caja
y fondo inicial; pagos a cuenta sin presupuesto; cierre automático; reapertura de una
caja; cobertura de obra social (C-11); seed demo (C-12); multi-sede y datos reales.

## Capabilities

### New Capabilities

- `caja`: caja diaria, cobro simulado, cierre con diferencia declarada, bloqueo por
  caja pendiente y pantallas de caja.
- `recibos`: numeración sin huecos, inmutabilidad, consulta y anulación por
  contramovimiento.

### Modified Capabilities

- `cuenta-corriente`: el contrato de escritura para caja pasa a ser definitivo
  (`recibo_id` con FK y `pago` siempre con recibo); suma `pendientes` por presupuesto y
  las acciones de cobro y anulación de recibo en la pantalla.
- `presupuestos`: la máquina de estados suma `aceptado → cobrado` y la reversa por
  anulación de recibo.

## Impact

- **Backend nuevo**: `modelos/caja.py`, `esquemas/caja.py`, `repos/caja_repo.py`,
  `repos/recibo_repo.py`, `servicios/caja_servicio.py`, `api/caja.py`, `api/recibos.py`,
  `alembic/versions/007_caja_recibos.py`.
- **Backend modificado**: `modelos/cuenta_corriente.py` (FK, CHECK e índices),
  `modelos/__init__.py`, `esquemas/cuenta.py`, `repos/cuenta_repo.py`,
  `servicios/cuenta_servicio.py`, `main.py`. `api/cobros.py` sigue como stub.
- **Tests existentes a ajustar**: `test_c09_migracion.py`, `test_c09_modelos.py`,
  `test_c09_cuenta.py`, `test_c09_repos.py`, `test_c09_rbac.py`, `test_c08_migracion.py`,
  `test_c07_migracion.py`, `test_c05_reserva_pg.py`, `test_routers.py`,
  `db_utils.reset_estado_base`. Los que insertan un `pago` sin recibo, o con
  `recibo_id` inexistente, pasan a usar un recibo real.
- **Frontend**: `features/caja` (nuevo), `features/cuenta-corriente`, `App.tsx`,
  `styles/caja.css`.
- **Dependencias**: ninguna nueva.
- **Docs**: correcciones de KB listadas en `design.md`; la línea de cadena Alembic de
  `.claude/skills/tp-verify-docker/references/tp-turnos-config.md`.
- **Downstream**: C-11 decide cómo la cobertura reduce lo pendiente y cómo una
  liquidación entra a caja (`design.md`, D-20; contrato en la sección C-11 de
  `CHANGES.md`). C-12 siembra la demo.
- **Gaps conocidos**: el fix de `GET /health` no afecta a C-10. La agenda muestra horas
  UTC: C-10 no lo corrige, pero fija que el día de caja lo decide solo el servidor.

**Leer antes** (`CHANGES.md`): `knowledge-base/04_modelo_de_datos.md`
§Caja/Recibo; `05_reglas_de_negocio.md` §RN-CO-01..04;
`06_funcionalidades.md` §US-031; `07_flujos_principales.md` §Flujo 4.
