# Spec Delta — cuenta-corriente

## MODIFIED Requirements

### Requirement: Contrato de escritura para caja

Un movimiento `pago` SHALL nacer con `recibo_id`, y `recibo_id` SHALL referenciar un
recibo existente. Cada recibo SHALL tener un solo `pago`. La única operación que registra
un `pago` SHALL ser `POST /caja/cobrar`.

#### Scenario: Pago cargado directamente

- **WHEN** se inserta directamente un `pago` con `recibo_id` sin recibo existente
- **THEN** la DB lo rechaza por clave foránea

#### Scenario: Pago sin recibo

- **WHEN** se inserta directamente un `pago` sin `recibo_id`
- **THEN** la DB lo rechaza por CHECK

#### Scenario: Segundo pago del mismo recibo

- **WHEN** se inserta directamente otro `pago` con el mismo `recibo_id`
- **THEN** la DB lo rechaza por UNIQUE

#### Scenario: Sin cobro por API

- **WHEN** se buscan las rutas de la aplicación
- **THEN** ninguna ruta de `/cuentas` ni de `/presupuestos` registra un `pago` ni marca
  `cobrado`; solo lo hacen las rutas de `/caja` y `/recibos`

## ADDED Requirements

### Requirement: Pendiente por presupuesto

`GET /cuentas/:paciente_id` SHALL devolver `pendientes`: los presupuestos `aceptado` del
paciente con importe mayor a cero por cobrar, con `presupuesto_id`, `total` y `pendiente`,
derivado de los movimientos. El importe SHALL ser derivado y nunca editable.

#### Scenario: Pendiente parcial

- **WHEN** un presupuesto de 1000.00 tiene un pago de 400.00
- **THEN** `pendientes` lo incluye con `pendiente` `"600.00"`

#### Scenario: Pago anulado

- **WHEN** se anula el recibo de ese pago
- **THEN** `pendiente` vuelve a `"1000.00"`

#### Scenario: Cargo anulado

- **WHEN** se anula el cargo del presupuesto
- **THEN** no aparece en `pendientes`

#### Scenario: Presupuesto cobrado

- **WHEN** el presupuesto llegó a `cobrado`
- **THEN** no aparece en `pendientes`

#### Scenario: Sin cuenta

- **WHEN** el paciente no tiene movimientos
- **THEN** `pendientes` es una lista vacía

### Requirement: Devolución de un saldo a favor

Si se anula el cargo de un presupuesto con pagos, el saldo a favor SHALL resolverse
anulando sus recibos. No SHALL existir otra forma de devolver dinero.

#### Scenario: Saldo a favor por cargo anulado

- **WHEN** se anula el cargo de 1000.00 de un presupuesto con un pago de 400.00
- **THEN** el saldo del paciente es `"-400.00"` y el presupuesto no se puede cobrar

#### Scenario: Devolución

- **WHEN** se anula después el recibo de ese pago
- **THEN** el saldo del paciente vuelve a `"0.00"`

### Requirement: Cobro y anulación de recibos en la cuenta

La pantalla de cuenta corriente SHALL ofrecer a `secretaria` cobrar cada presupuesto
pendiente, y a `admin` anular el recibo de un `pago`. El cobro SHALL mostrarse
deshabilitado, con el motivo en texto, si la caja no está operable.

#### Scenario: Secretaria cobra desde la cuenta

- **WHEN** una secretaria cobra un pendiente con importe y medio
- **THEN** ve el comprobante, y el saldo y los pendientes se actualizan desde el servidor

#### Scenario: Importe inválido

- **WHEN** la secretaria escribe un importe que no es un decimal positivo de hasta dos cifras
- **THEN** el formulario no se envía e indica el error

#### Scenario: Caja bloqueada

- **WHEN** hay una caja pendiente
- **THEN** el cobro está deshabilitado y un texto indica que hay que cerrar la caja anterior

#### Scenario: Consulta de caja fallida

- **WHEN** falla la consulta del estado de la caja
- **THEN** la cuenta se muestra igual, y si el servidor rechaza el cobro se muestra su error

#### Scenario: Admin no cobra

- **WHEN** un admin abre una cuenta con pendientes
- **THEN** no ve la acción de cobrar

#### Scenario: Admin anula un recibo

- **WHEN** un admin anula con motivo un `pago` no anulado
- **THEN** el saldo y los movimientos se actualizan desde el servidor

#### Scenario: Secretaria no anula recibos

- **WHEN** una secretaria ve un `pago`
- **THEN** no tiene acción de anular
