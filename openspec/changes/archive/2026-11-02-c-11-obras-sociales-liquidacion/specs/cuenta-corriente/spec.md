# Delta — cuenta-corriente

## ADDED Requirements

### Requirement: Ajuste de cobertura

Si la cobertura de un presupuesto es mayor a cero, `aceptar` SHALL crear un `ajuste` negativo
por ese importe, con `presupuesto_id`, sin `anula_a_id`, sin recibo y con concepto fijo sin
datos clínicos. El cargo SHALL seguir siendo por el total. Cada presupuesto SHALL tener como
máximo un `ajuste` de cobertura, y la base de datos SHALL garantizarlo. El `ajuste` SHALL NOT
mover caja. No SHALL existir ruta para crearlo por separado.

#### Scenario: Pendiente reducido

- **WHEN** se acepta un presupuesto de 1000.00 con 700.00 cubiertos
- **THEN** la cuenta tiene un cargo de 1000.00 y un `ajuste` de -700.00, y el pendiente es `"300.00"`

#### Scenario: Cobro limitado

- **WHEN** se intenta cobrar más que ese pendiente
- **THEN** responde `422`

#### Scenario: Sin cobertura

- **WHEN** el presupuesto no tiene monto cubierto
- **THEN** no se crea ningún `ajuste`

#### Scenario: Segundo ajuste de cobertura

- **WHEN** se inserta directamente otro `ajuste` de cobertura del mismo presupuesto
- **THEN** la DB lo rechaza por índice único parcial

#### Scenario: La caja no cambia

- **WHEN** se registra el `ajuste` de cobertura con la caja de ayer pendiente
- **THEN** el presupuesto se acepta, y no se crea ningún movimiento de caja

## MODIFIED Requirements

### Requirement: Anulación por contramovimiento

`POST /cuentas/:paciente_id/movimientos/:id/anular` SHALL exigir `motivo` y crear un
`ajuste` por el monto opuesto con `anula_a_id`, sin tocar la fila original. Solo un
`cargo` SHALL poder anularse por este endpoint, y una sola vez. Si el presupuesto tiene un
`ajuste` de cobertura, la misma transacción SHALL crear su contramovimiento. Si alguna
prestación del presupuesto está en una liquidación, SHALL responder `409`.

#### Scenario: Anulación de un cargo

- **WHEN** un admin anula un cargo de 1000.00 con `motivo`
- **THEN** responde `201` con un `ajuste` de -1000.00, y el saldo baja 1000.00

#### Scenario: Cargo con cobertura

- **WHEN** se anula un cargo de 1000.00 con un `ajuste` de cobertura de -700.00 sin pagos
- **THEN** el `ajuste` de cobertura también se revierte, y el saldo queda `"0.00"`

#### Scenario: Prestación liquidada

- **WHEN** se anula el cargo de un presupuesto con un ítem en una liquidación
- **THEN** responde `409` y no se crea ninguna fila

#### Scenario: Liquidación en borrador descartada

- **WHEN** se descarta el `borrador` que contenía el ítem y se anula el cargo
- **THEN** responde `201`

#### Scenario: Sin motivo

- **WHEN** se anula sin `motivo`
- **THEN** responde `422` y no se crea ninguna fila

#### Scenario: Doble anulación

- **WHEN** se anula otra vez el mismo cargo
- **THEN** responde `409`

#### Scenario: Doble anulación concurrente

- **WHEN** dos sesiones anulan el mismo cargo a la vez
- **THEN** una responde `201`, la otra `409` y existe un solo contramovimiento

#### Scenario: Anular un contramovimiento

- **WHEN** se intenta anular un `ajuste`
- **THEN** responde `409`

#### Scenario: Anular un pago

- **WHEN** se intenta anular un `pago`
- **THEN** responde `409`, porque un pago se anula desde su recibo en C-10

#### Scenario: Movimiento de otra cuenta

- **WHEN** el movimiento no pertenece a la cuenta de `paciente_id`
- **THEN** responde `404`

#### Scenario: La base de datos exige motivo

- **WHEN** se inserta directamente un movimiento con `anula_a_id` y sin `motivo`
- **THEN** la DB lo rechaza por CHECK

### Requirement: Contrato de escritura para caja

Un movimiento `pago` SHALL nacer con `recibo_id`, y `recibo_id` SHALL referenciar un
recibo existente. Cada recibo SHALL tener un solo `pago`. La única operación que registra
un `pago` SHALL ser `POST /caja/cobrar`. Ninguna ruta de `/cuentas` SHALL marcar `cobrado`.
En `/presupuestos`, solo `aceptar` SHALL hacerlo, y solo cuando la cobertura salda el importe.

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
- **THEN** ninguna ruta de `/cuentas` ni de `/presupuestos` registra un `pago`, y ninguna acepta un `estado` en su cuerpo
