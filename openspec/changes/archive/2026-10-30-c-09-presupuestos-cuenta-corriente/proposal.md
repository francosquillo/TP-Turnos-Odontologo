# Proposal — c-09-presupuestos-cuenta-corriente (C-09 `presupuestos-cuenta-corriente`)

> Nota de nombre: el change canónico en `CHANGES.md` es `C-09 presupuestos-cuenta-corriente`.
> El CLI `openspec` exige kebab-case minúsculas, por eso el directorio es
> `openspec/changes/c-09-presupuestos-cuenta-corriente/`.

## Why

C-08 dejó al odontólogo registrando hallazgos, pero el Flujo 3 se corta ahí: no hay
forma de convertirlos en un presupuesto ni de saber cuánto debe un paciente. Este
change cierra clínica → deuda (US-022, US-030; RN-CL-01, RN-CL-02, RN-CO-02,
RN-CO-03) y deja el contrato que necesitan C-10 (caja) y C-11 (liquidaciones).
GATE 4 está abierto: C-04 y C-08 están archivados. C-09 está en el camino crítico.

## What Changes

- Modelos nuevos: `Presupuesto`, `ItemPresupuesto`, `CuentaCorriente` y `Movimiento`.
- Migración `006_presupuestos_cc` sobre `005_clinica`, verificada contra el código.
- Presupuesto con estados `borrador → presentado → aceptado | rechazado`. `cobrado`
  queda en el catálogo, pero solo lo alcanza C-10.
- Cada ítem referencia un hallazgo activo del paciente y un tratamiento del catálogo.
  Un ítem sin hallazgo responde `422`.
- Precio copiado por el servidor desde `Tratamiento.precio_base`; `total` calculado
  por el servidor. El cliente no envía ninguno de los dos.
- Aceptar genera un único cargo en la cuenta corriente, también ante dos pedidos
  simultáneos.
- Saldo siempre derivado de los movimientos: no existe columna `saldo`. Los
  movimientos son inmutables a nivel base de datos.
- Anulación de un cargo por contramovimiento con motivo.
- Endpoints: `CRUD /presupuestos`, `POST /presupuestos/:id/presentar|aceptar|rechazar`,
  `POST /presupuestos/:id/baja`, `GET /cuentas/:paciente_id` y
  `POST /cuentas/:paciente_id/movimientos/:id/anular`.
- Frontend `features/presupuestos` (desde el odontograma) y
  `features/cuenta-corriente` (desde la agenda), con tokens de `design-system/`.

**Agregados respecto de `CHANGES.md`** (ver `design.md`, sección de diferencias):
`presentar`, `baja` y `anular` no figuran en su lista de endpoints, pero sin ellos no
se puede llegar a `presentado`, borrar un borrador ni hacer un contramovimiento.

**Fuera de alcance**: caja, recibos, cobro, cierre diario y la transición a `cobrado`
(C-10); descuentos o precio manual; cobertura de obra social y arancel (C-11);
ajustes libres de saldo; planes de pago; vencimiento de presupuestos; pantalla de
pacientes (C-12); pagos reales, AFIP, multi-sede y datos reales.

## Capabilities

### New Capabilities

- `presupuestos`: ciclo de vida del presupuesto nacido de hallazgos, con ítems,
  precios congelados, estados, permisos y pantallas desde el odontograma.
- `cuenta-corriente`: cuenta por paciente con movimientos inmutables, saldo derivado,
  contramovimientos y el contrato de escritura que usará C-10.

### Modified Capabilities

Ninguna. `clinica-odontograma-hc` ya garantiza identificadores estables de hallazgos
y tratamientos; C-09 los consume sin cambiar sus requirements. El acceso nuevo en la
pantalla de odontograma se especifica en `presupuestos`.

## Impact

- **Backend**: `modelos/{presupuesto,cuenta_corriente}.py`, `esquemas/{presupuesto,cuenta}.py`,
  `repos/{presupuesto_repo,cuenta_repo}.py`, `servicios/{presupuesto_servicio,cuenta_servicio}.py`,
  `api/{presupuestos,cuentas}.py`, `alembic/versions/006_presupuestos_cc.py`, `main.py`.
  `api/cobros.py` sigue como stub.
- **Tests existentes a ajustar**: `test_c08_migracion.py`, `test_c07_migracion.py`,
  `test_c05_reserva_pg.py`, `test_routers.py`, `db_utils.reset_estado_base`.
- **Frontend**: `features/presupuestos`, `features/cuenta-corriente`, `shared/` (moneda
  y cliente JSON), `App.tsx`, `AgendaPage`, `TurnoCard`, `OdontogramaPage`.
- **Dependencias**: ninguna nueva.
- **Downstream**: C-10 escribe `pago`, llena `recibo_id` y marca `cobrado`; C-11 lee
  ítems y tratamientos.

**Leer antes** (`CHANGES.md`): `knowledge-base/04_modelo_de_datos.md`
§Tratamiento/Presupuesto y §CuentaCorriente; `05_reglas_de_negocio.md` §RN-CL-01,
§RN-CL-02, §RN-CO-02, §RN-CO-03; `06_funcionalidades.md` §US-022, §US-030;
`07_flujos_principales.md` §Flujo 3.
