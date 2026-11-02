# cuenta-corriente Specification

## Purpose
Dar a la secretaria y al admin la deuda de cada paciente a partir de movimientos
inmutables, con saldo siempre derivado y anulación por contramovimiento (US-030;
RN-CO-02, RN-CO-03), y dejar el contrato de escritura que usa caja en C-10.

## Requirements

### Requirement: Una cuenta corriente por paciente

El sistema SHALL mantener como máximo una cuenta por paciente, creada al generarse el
primer movimiento. Consultar SHALL NOT crear filas.

#### Scenario: Primer cargo crea la cuenta

- **WHEN** se acepta el primer presupuesto de un paciente
- **THEN** existe una cuenta para ese paciente con un movimiento

#### Scenario: Segundo cargo reutiliza la cuenta

- **WHEN** se acepta un segundo presupuesto del mismo paciente
- **THEN** sigue habiendo una sola cuenta, con dos movimientos

#### Scenario: Primer cargo concurrente

- **WHEN** dos presupuestos distintos de un paciente sin cuenta se aceptan a la vez
- **THEN** ambos responden `200` y existe una sola cuenta con dos cargos

#### Scenario: Paciente duplicado

- **WHEN** se inserta directamente una segunda cuenta para el mismo paciente
- **THEN** la DB la rechaza por UNIQUE

### Requirement: Saldo derivado de los movimientos

El saldo SHALL calcularse como la suma de todos los movimientos de la cuenta. Un saldo
positivo SHALL significar deuda del paciente. No SHALL existir columna de saldo ni
operación que lo escriba.

#### Scenario: Suma de cargos, pagos y ajustes

- **WHEN** la cuenta tiene un cargo de 1000.00, un pago de -400.00 y un ajuste de -100.00
- **THEN** `GET /cuentas/:paciente_id` devuelve `saldo` `"500.00"`

#### Scenario: Saldo a favor

- **WHEN** los pagos superan a los cargos
- **THEN** `saldo` es negativo

#### Scenario: Sin columna de saldo

- **WHEN** se inspecciona la tabla `cuenta_corriente`
- **THEN** no tiene columna `saldo`

#### Scenario: El saldo no se envía

- **WHEN** se hace `PUT` o `PATCH` sobre `/cuentas/:paciente_id`
- **THEN** responde `405`

### Requirement: Consulta de la cuenta

`GET /cuentas/:paciente_id` SHALL devolver `paciente_id`, `saldo` y los movimientos del
más reciente al más antiguo, con `tipo`, `monto`, `concepto`, referencias, `motivo`,
`created_at` y `anulado`.

#### Scenario: Paciente sin cuenta

- **WHEN** se consulta un paciente existente sin movimientos
- **THEN** responde `200` con `saldo` `"0.00"` y lista vacía, sin crear filas

#### Scenario: Paciente inexistente

- **WHEN** el paciente no existe
- **THEN** responde `404`

#### Scenario: Paciente dado de baja con movimientos

- **WHEN** se consulta un paciente eliminado que tiene movimientos
- **THEN** responde `200`, porque la deuda se conserva

#### Scenario: Cargo anulado

- **WHEN** un cargo tiene contramovimiento
- **THEN** el cargo se lista con `anulado: true` y el contramovimiento con `anula_a_id`

### Requirement: Signo del monto según el tipo

Los tipos SHALL ser `cargo`, `pago` y `ajuste`. `cargo` SHALL ser positivo, `pago`
negativo y `ajuste` distinto de cero, en montos con dos decimales.

#### Scenario: Monto cero

- **WHEN** se inserta directamente un movimiento con `monto` 0
- **THEN** la DB lo rechaza por CHECK

#### Scenario: Cargo negativo

- **WHEN** se inserta directamente un `cargo` con monto negativo
- **THEN** la DB lo rechaza por CHECK

#### Scenario: Pago positivo

- **WHEN** se inserta directamente un `pago` con monto positivo
- **THEN** la DB lo rechaza por CHECK

#### Scenario: Tipo fuera del catálogo

- **WHEN** se inserta directamente un `tipo` desconocido
- **THEN** la DB lo rechaza por CHECK

### Requirement: Movimientos inmutables

Un movimiento SHALL NOT poder modificarse ni borrarse, tampoco por SQL directo. La
autoría y la fecha SHALL quedar registradas en cada fila (RN-GL-02).

#### Scenario: UPDATE directo

- **WHEN** se ejecuta `UPDATE` sobre una fila de `movimiento`
- **THEN** la DB lo rechaza

#### Scenario: DELETE directo

- **WHEN** se ejecuta `DELETE` sobre una fila de `movimiento`
- **THEN** la DB lo rechaza

#### Scenario: Sin escritura directa por API

- **WHEN** se hace `POST /cuentas/:paciente_id/movimientos`
- **THEN** responde `404`, porque esa ruta no existe

#### Scenario: Autoría del cargo

- **WHEN** se genera un cargo al aceptar
- **THEN** el movimiento guarda `creado_por` con el usuario que aceptó

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

### Requirement: Presupuesto con cargo anulado

Anular el cargo de un presupuesto SHALL conservar su estado `aceptado` y SHALL
reflejarse en el campo derivado `cargo_anulado` de sus respuestas.

#### Scenario: Estado conservado

- **WHEN** se anula el cargo de un presupuesto `aceptado`
- **THEN** el presupuesto sigue `aceptado` con `cargo_anulado: true`

#### Scenario: Los hallazgos pueden presupuestarse de nuevo

- **WHEN** se crea otro presupuesto sobre los mismos hallazgos activos
- **THEN** se acepta como un presupuesto nuevo con su propio cargo

### Requirement: Permisos sobre la cuenta corriente

`secretaria` y `admin` SHALL leer cualquier cuenta. Solo `admin` SHALL anular. El rol
`odontologo` SHALL NOT acceder a `/cuentas`. Sin Bearer válido SHALL responder `401`.

#### Scenario: Secretaria lee

- **WHEN** una secretaria hace `GET /cuentas/:paciente_id`
- **THEN** responde `200`

#### Scenario: Secretaria no anula

- **WHEN** una secretaria intenta anular un cargo
- **THEN** responde `403` y nada cambia

#### Scenario: Odontólogo sin acceso

- **WHEN** un odontólogo consulta `/cuentas/:paciente_id`
- **THEN** responde `403`

#### Scenario: Sin autenticación

- **WHEN** se llama a `/cuentas` sin Bearer
- **THEN** responde `401`

### Requirement: Sin datos clínicos en la cuenta

Los movimientos generados por el sistema SHALL usar un `concepto` fijo, sin piezas,
hallazgos ni tratamientos. Los motivos SHALL NOT escribirse en logs.

#### Scenario: Concepto del cargo

- **WHEN** se genera el cargo del presupuesto 12
- **THEN** `concepto` es `Presupuesto 12`

#### Scenario: Motivo fuera de los logs

- **WHEN** se anula un cargo con un texto marcador en `motivo`
- **THEN** ningún registro de log capturado contiene ese texto

#### Scenario: Frontend sin consola

- **WHEN** se revisa el código de `features/cuenta-corriente`
- **THEN** no contiene llamadas a `console`

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

### Requirement: Pantalla de cuenta corriente

`features/cuenta-corriente` SHALL mostrar con texto si el paciente debe, no debe o
tiene saldo a favor, y sus movimientos. Se SHALL acceder desde la agenda para
`secretaria` y `admin`, y solo `admin` SHALL ver la acción de anular.

#### Scenario: Secretaria ve la deuda

- **WHEN** una secretaria abre la cuenta desde un turno
- **THEN** ve el saldo, y cargos y anulaciones sin acción de anular

#### Scenario: Sin movimientos

- **WHEN** el paciente no tiene movimientos
- **THEN** la pantalla dice que no tiene movimientos

#### Scenario: Odontólogo sin acceso

- **WHEN** un odontólogo ve un turno en la agenda
- **THEN** no tiene acceso a la cuenta corriente

#### Scenario: Admin anula con motivo

- **WHEN** un admin anula un cargo sin escribir motivo
- **THEN** el formulario no se envía e indica que el motivo es obligatorio

#### Scenario: Acceso al presupuesto

- **WHEN** un cargo tiene `presupuesto_id`
- **THEN** se puede abrir ese presupuesto en modo lectura

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
